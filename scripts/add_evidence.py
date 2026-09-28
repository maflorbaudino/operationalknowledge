# -*- coding: utf-8 -*-
import json, pandas as pd, collections, re
from egm_tag import INT, OUT, DES, C
d = pd.read_pickle('egm_tagged.pkl')
INT_L = list(INT) + ['Infraestructura de transporte (general)']
OUT_L = list(OUT) if 'Delincuencia y seguridad ciudadana' in OUT else list(OUT)
DES_L = list(DES)
CO_L = sorted({c for L in d.paises for c in L})
IDB = ['Brasil','Colombia','Haití','Honduras','Nicaragua','Argentina','Bolivia','El Salvador','Perú','Panamá','Guyana','Paraguay','Bahamas','Uruguay','Jamaica','Ecuador','Guatemala','Belice','Costa Rica','República Dominicana','Surinam']
def url(r):
    u = str(r.ris_url or '').strip()
    if u.startswith('http'): return u
    u = '' if pd.isna(r.Url) else str(r.Url).strip()
    if u.startswith('http'): return u
    doi = str(r.DOI).strip()
    return 'https://doi.org/' + doi if doi.startswith('10.') else ''
studies = []
for i, r in d.iterrows():
    studies.append(dict(t=re.sub(r'\s+', ' ', r.Title).strip(), y=int(r.year) if pd.notna(r.year) else None, u=url(r),
        iv=[INT_L.index(x) for x in r.intervenciones], ou=[OUT_L.index(x) for x in r.resultados], de=[DES_L.index(x) for x in r.disenos],
        co=[CO_L.index(x) for x in r.paises], alc=int('ALC' in r.regiones), rg=r.regiones,
        tp='' if pd.isna(r.Publication_Of_Type) else r.Publication_Of_Type))
# subsector (id del grafo) -> temas de evidencia con los que se compara
T = {i: k for i, k in enumerate(INT_L)}
def ix(*names): return [INT_L.index(n) for n in names]
SS = {
 'SS:MAJOR HIGHWAYS': ix('Carreteras, autopistas y redes viales','Puentes, túneles y conectividad de redes','Infraestructura de transporte (general)'),
 'SS:SECONDARY ROADS': ix('Carreteras, autopistas y redes viales','Caminos rurales'),
 'SS:RURAL ROADS': ix('Caminos rurales'),
 'SS:ROAD MAINTENANCE': ix('Mantenimiento vial'),
 'SS:ROAD SAFETY': ix('Seguridad vial'),
 'SS:URBAN TRANSPORT INFRASTRUCTURE': ix('Transporte público (bus, BRT, metro, tranvía, teleférico)','Transporte no motorizado (bicicleta, peatonal)','Gestión de tráfico, congestión y estacionamiento'),
 'SS:PUBLIC TRANSPORT (BUS / TRAIN / CABLE': ix('Transporte público (bus, BRT, metro, tranvía, teleférico)','Subsidios y tarifas de transporte','Servicios de movilidad (taxi, ride-hailing, compartida)'),
 'SS:NON-MOTORIZED URBAN TRANSPORT': ix('Transporte no motorizado (bicicleta, peatonal)'),
 'SS:TRANSPORT NETWORKS CONNECTIVITY': ix('Puentes, túneles y conectividad de redes','Infraestructura de transporte (general)','Ferrocarril interurbano y alta velocidad'),
 'SS:LOGISTIC PLANNING, MULTIMODAL TRANSPORT AND LOGISTIC PLATFORMS': ix('Puertos, logística y transporte de carga','Ferrocarril interurbano y alta velocidad','Aviación y aeropuertos'),
 'SS:REFORM / MODERNIZATION OF THE STATE': ix('Reforma institucional, APP y gobernanza'),
}
CORE = {
 INT_L.index('Transporte público (bus, BRT, metro, tranvía, teleférico)'): ['SS:PUBLIC TRANSPORT (BUS / TRAIN / CABLE'],
 INT_L.index('Carreteras, autopistas y redes viales'): ['SS:MAJOR HIGHWAYS','SS:SECONDARY ROADS'],
 INT_L.index('Caminos rurales'): ['SS:RURAL ROADS'],
 INT_L.index('Mantenimiento vial'): ['SS:ROAD MAINTENANCE'],
 INT_L.index('Seguridad vial'): ['SS:ROAD SAFETY'],
 INT_L.index('Transporte no motorizado (bicicleta, peatonal)'): ['SS:NON-MOTORIZED URBAN TRANSPORT'],
 INT_L.index('Puertos, logística y transporte de carga'): ['SS:LOGISTIC PLANNING, MULTIMODAL TRANSPORT AND LOGISTIC PLATFORMS'],
 INT_L.index('Puentes, túneles y conectividad de redes'): ['SS:TRANSPORT NETWORKS CONNECTIVITY'],
 INT_L.index('Reforma institucional, APP y gobernanza'): ['SS:REFORM / MODERNIZATION OF THE STATE'],
}
TOPIC = {
 INT_L.index('Seguridad vial'): dict(pb=['PB:VIA'], pr=['PR:R24']),
 INT_L.index('Mantenimiento vial'): dict(pb=['PB:MAN'], pr=['PR:R15','PR:R16']),
 INT_L.index('Reforma institucional, APP y gobernanza'): dict(pb=['PB:MER'], pr=['PR:R28']),
}
G = json.load(open('out/graph.json', encoding='utf-8'))
NODE = {n['id']: n for n in G['nodes']}
cnt = collections.Counter()
for s in studies:
    for k in s['iv']: cnt[k] += 1
for k, name in enumerate(INT_L):
    G['nodes'].append(dict(id=f'EV:{k}', tipo='Evidencia', etiqueta=name, n_estudios=cnt[k], n_estudios_alc=sum(1 for s in studies if k in s['iv'] and s['alc'])))
for ss, ks in SS.items():
    for k in ks:
        G['edges'].append(dict(origen=ss, destino=f'EV:{k}', relacion='TIENE_EVIDENCIA', peso=cnt[k]))
G['evidence'] = dict(topic=TOPIC, core=CORE, themes=INT_L, outcomes=OUT_L, designs=DES_L, countries=CO_L, idb=IDB, ssmap=SS, studies=studies,
    source='3ie Development Evidence Portal · Evidence Gap Map de transporte (exportación de 711 registros)')
json.dump(G, open('out/graph_ev.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(len(studies), 'estudios', len(G['nodes']), 'nodos', len(G['edges']), 'aristas', len(json.dumps(G['evidence']))//1024, 'KB evidencia')
# tabla de brechas (también para Excel)
les = collections.defaultdict(set)
for e in G['edges']:
    if e['origen'].startswith('L') and e['destino'].startswith('SS:'): les[e['destino']].add(e['origen'])
rows = []
for ss, ks in SS.items():
    st = [s for s in studies if set(s['iv']) & set(ks)]
    rows.append(dict(subsector=NODE[ss]['etiqueta'], lecciones=len(les[ss]), estudios=len(st), estudios_alc=sum(s['alc'] for s in st)))
print(pd.DataFrame(rows).sort_values('lecciones', ascending=False).to_string())
sin = [NODE[n]['etiqueta'] for n in NODE if n.startswith('SS:') and n not in SS]
print('Subsectores sin tema:', sin)
print('Temas sin subsector:', [INT_L[k] for k in range(len(INT_L)) if not any(k in v for v in SS.values())])
