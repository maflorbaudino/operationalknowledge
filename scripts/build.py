# -*- coding: utf-8 -*-
import pandas as pd, re, json, itertools, collections, sys
sys.path.insert(0, '/tmp/claude-0/-home-claude/bc7375d9-8385-5523-8bb6-2b2f061d324b/scratchpad')
from annot import *
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

SRC = '/root/.claude/uploads/bc7375d9-8385-5523-8bb6-2b2f061d324b/6421f4c8-Curated-Lessons-Learned-TSP.csv'
OUT = '/tmp/claude-0/-home-claude/bc7375d9-8385-5523-8bb6-2b2f061d324b/scratchpad/out'
import os; os.makedirs(OUT, exist_ok=True)

df = pd.read_csv(SRC)
clean = lambda s: re.sub(r'\s+', ' ', str(s).replace('\xa0', ' ')).strip()

COUNTRY = {'BR':'Brasil','CO':'Colombia','HA':'Haití','HO':'Honduras','NI':'Nicaragua','AR':'Argentina','BO':'Bolivia',
           'ES':'El Salvador','PE':'Perú','PN':'Panamá','GY':'Guyana','PR':'Paraguay','BH':'Bahamas','UR':'Uruguay',
           'JA':'Jamaica','EC':'Ecuador','GU':'Guatemala','BL':'Belice','CR':'Costa Rica','DR':'República Dominicana','SU':'Surinam'}
SUBSEC = {'TRANSPORT':'Transporte (general)','MAJOR HIGHWAYS':'Carreteras principales','URBAN TRANSPORT INFRASTRUCTURE':'Infraestructura de transporte urbano',
          'TRANSPORT NETWORKS CONNECTIVITY':'Conectividad de redes de transporte','RURAL ROADS':'Caminos rurales','SECONDARY ROADS':'Caminos secundarios',
          'PRIVATE FIRMS AND SME DEVELOPMENT':'Desarrollo de empresas privadas y PYME','INDIGENOUS PEOPLES DEVELOPMENT':'Desarrollo de pueblos indígenas',
          'LOGISTIC PLANNING, MULTIMODAL TRANSPORT AND LOGISTIC PLATFORMS':'Planificación logística y transporte multimodal',
          'PUBLIC TRANSPORT (BUS / TRAIN / CABLE':'Transporte público','NON-MOTORIZED URBAN TRANSPORT':'Transporte urbano no motorizado',
          'REFORM / MODERNIZATION OF THE STATE':'Reforma y modernización del Estado','ROAD MAINTENANCE':'Mantenimiento vial','ROAD SAFETY':'Seguridad vial'}
CATES = {'Legislation and regulation':'Legislación y regulación','Public governance and politics':'Gobernanza pública y política',
 'Business environment':'Entorno empresarial','Social and cultural context':'Contexto social y cultural',
 'Natural environment and human health':'Entorno natural y salud','Economic environment':'Entorno económico',
 'Organizational capacity':'Capacidad organizacional','Technical Design':'Diseño técnico','Engagement and coordination':'Coordinación y participación',
 'Human Resources and Other Assets':'Recursos humanos y otros activos','Scope and Planning':'Alcance y planificación',
 'Operational Design':'Diseño operativo','Monitoring and Evaluation Strategy':'Estrategia de monitoreo y evaluación'}
MODAL = {'Specific Investment Operation':'Operación de inversión específica','Global of Multiple Works Operation':'Obras múltiples (GOM)',
 'Technical Cooperation Loan':'Préstamo de cooperación técnica','Immediate Response Facility for Emergencies':'Facilidad de respuesta inmediata',
 'Programmatic Policy Base Loan':'Préstamo programático de reforma','Policy Based Loan':'Préstamo en apoyo de reformas','Performance Driven Loan':'Préstamo por resultados'}

nodes = {}  # id -> dict
edges = []  # dict(source,target,rel,weight)
def node(nid, typ, label, **kw):
    if nid not in nodes: nodes[nid] = dict(id=nid, tipo=typ, etiqueta=label, **kw)
    return nodes[nid]
_seen_e = set()
def edge(s, t, rel, w=1):
    if (s, t, rel) in _seen_e: return
    _seen_e.add((s, t, rel)); edges.append(dict(origen=s, destino=t, relacion=rel, peso=w))

# Nombres de operaciones (solo filas donde numeros y nombres alinean)
opname = {}
for _, r in df.iterrows():
    on = [x.strip() for x in r['Oper Numbers'].split(';')]; nm = [clean(x) for x in str(r['Oper Names']).split(';')]
    if len(on) == len(nm):
        for a, b in zip(on, nm): opname.setdefault(a, b)

lessons_rows = []
for i, r in df.iterrows():
    n = int(r['Curated Lesson Learned ID'].split('-')[-1]); lid = f'L{n}'
    tipo, P, C, R, E, AC, prob, rec = A[n]
    P, C, R, E, AC = [x.split() for x in (P, C, R, E, AC)]
    text = clean(r['Lesson Learned'])
    m = re.search(r'Recomendaci[oó]n(?:es)?:', text)
    hallazgo = clean(re.sub(r'^"?Hallazgos?:', '', text[:m.start()])) if m else text
    recomend = clean(text[m.end():]).strip('"') if m else ''
    cat = clean(r['Risk Category Name'])
    node(lid, 'Lección', f'CLL-TSP-{n}', codigo=r['Curated Lesson Learned ID'], subtipo='Buena práctica' if tipo == 'B' else 'Problema o riesgo',
         problema_resumen=prob, recomendacion_resumen=rec, hallazgo=hallazgo, recomendacion=recomend,
         fuente_riesgo=r['Risk Source'], categoria_riesgo=cat, subcategoria_riesgo=clean(r['Risk Subcategory']),
         instrumento=r['Instrument'], enlaces=r['Source Links'])
    # taxonomía del Banco
    node('RC:'+cat, 'Categoría de riesgo (BID)', CATES.get(cat, cat)); edge(lid, 'RC:'+cat, 'CLASIFICADA_COMO')
    # operaciones y países
    ops = [x.strip() for x in r['Oper Numbers'].split(';')]
    for o in ops:
        cc = o[:2]; node('OP:'+o, 'Operación', o, nombre=opname.get(o, ''), pais=COUNTRY.get(cc, cc))
        node('PA:'+cc, 'País', COUNTRY.get(cc, cc)); edge(lid, 'OP:'+o, 'EXTRAÍDA_DE'); edge('OP:'+o, 'PA:'+cc, 'EJECUTADA_EN')
    for s in r['Subsector'].split(';'):
        s = clean(s); node('SS:'+s, 'Subsector', SUBSEC.get(s, s)); edge(lid, 'SS:'+s, 'EN_SUBSECTOR')
    for m_ in r['Modality'].split(';'):
        m_ = clean(m_); node('MO:'+m_, 'Modalidad', MODAL.get(m_, m_)); edge(lid, 'MO:'+m_, 'MODALIDAD')
    for p in P: node('PB:'+p, 'Problema', PROBLEMS[p]); edge(lid, 'PB:'+p, 'IDENTIFICA' if tipo == 'P' else 'PREVIENE')
    for c in C: node('CS:'+c, 'Consecuencia', CONSEQ[c]); edge(lid, 'CS:'+c, 'REGISTRA')
    for x in R: node('PR:'+x, 'Práctica', PRACTICES[x]); edge(lid, 'PR:'+x, 'RECOMIENDA')
    for e in E: node('ET:'+e, 'Etapa', STAGES[e]); edge(lid, 'ET:'+e, 'ACTÚA_EN_ETAPA')
    for a in AC: node('AC:'+a, 'Actor', ACTORS[a]); edge(lid, 'AC:'+a, 'DIRIGIDA_A')
    lessons_rows.append(dict(id=lid, codigo=r['Curated Lesson Learned ID'], tipo='Buena práctica' if tipo == 'B' else 'Problema o riesgo',
        problemas='; '.join(PROBLEMS[p] for p in P), consecuencias='; '.join(CONSEQ[c] for c in C), practicas='; '.join(PRACTICES[x] for x in R),
        etapas='; '.join(STAGES[e] for e in E), actores='; '.join(ACTORS[a] for a in AC), problema_resumen=prob, recomendacion_resumen=rec,
        categoria_riesgo_bid=CATES.get(cat, cat), subcategoria_riesgo_bid=clean(r['Risk Subcategory']),
        paises='; '.join(sorted({COUNTRY.get(o[:2], o[:2]) for o in ops})), operaciones=r['Oper Numbers'],
        hallazgo=hallazgo, recomendacion=recomend))

# ---- aristas derivadas (agregadas entre lecciones) ----
LES = [k for k, v in nodes.items() if v['tipo'] == 'Lección']
def links(lid, prefix, rel_set):
    return [e['destino'] for e in edges if e['origen'] == lid and e['relacion'] in rel_set and e['destino'].startswith(prefix)]
mit = collections.Counter(); gen = collections.Counter(); prc = collections.Counter()
for l in LES:
    pb = links(l, 'PB:', {'IDENTIFICA', 'PREVIENE'}); pr = links(l, 'PR:', {'RECOMIENDA'}); cs = links(l, 'CS:', {'REGISTRA'})
    for p_, r_ in itertools.product(pb, pr): mit[(r_, p_)] += 1
    for p_, c_ in itertools.product(pb, cs): gen[(p_, c_)] += 1
    for a_, b_ in itertools.combinations(sorted(pr), 2): prc[(a_, b_)] += 1
derived = [dict(origen=a, destino=b, relacion='MITIGA', peso=w) for (a, b), w in mit.items()] + \
          [dict(origen=a, destino=b, relacion='GENERA', peso=w) for (a, b), w in gen.items()] + \
          [dict(origen=a, destino=b, relacion='SE_COMBINA_CON', peso=w) for (a, b), w in prc.items()]

# ---- similitud textual entre lecciones (TF-IDF) ----
stop = set('de la que el en y a los del se las por un para con no una su al lo como más pero sus le ya o este sí porque esta entre cuando muy sin sobre también me hasta hay donde quien desde todo nos durante todos uno les ni contra otros ese eso ante ellos e esto mí antes algunos qué unos yo otro otras otra él tanto esa estos mucho quienes nada muchos cual poco ella estar estas algunas algo nosotros es son ser han fue ha proyectos proyecto operaciones programas programa asegurar garantizar mediante través'.split())
docs = [clean(x['hallazgo'] + ' ' + x['recomendacion']) for x in lessons_rows]
tf = TfidfVectorizer(stop_words=list(stop), sublinear_tf=True, min_df=2, max_df=0.4, ngram_range=(1, 2)); X = tf.fit_transform(docs)
S = cosine_similarity(X); sim = []
seen = set()
for i in range(len(docs)):
    for j in sorted(range(len(docs)), key=lambda j: -S[i, j])[:4]:
        if j != i and S[i, j] >= 0.22 and (min(i, j), max(i, j)) not in seen:
            seen.add((min(i, j), max(i, j))); sim.append(dict(origen=lessons_rows[i]['id'], destino=lessons_rows[j]['id'], relacion='SIMILAR_A', peso=round(float(S[i, j]), 3)))
print('similares', len(sim))

# ---- guardar ----
pd.DataFrame(list(nodes.values())).to_csv(f'{OUT}/nodos.csv', index=False)
pd.DataFrame(edges + derived + sim).to_csv(f'{OUT}/aristas.csv', index=False)
pd.DataFrame(lessons_rows).to_csv(f'{OUT}/lecciones_extraidas.csv', index=False)
json.dump(dict(nodes=list(nodes.values()), edges=edges, derived=derived, sim=sim), open(f'{OUT}/graph.json', 'w'), ensure_ascii=False)
print(collections.Counter(v['tipo'] for v in nodes.values())); print(len(edges), 'aristas base', len(derived), 'derivadas')
