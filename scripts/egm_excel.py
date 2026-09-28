# -*- coding: utf-8 -*-
import json, pandas as pd, collections
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
G=json.load(open('out/graph_ev.json',encoding='utf-8')); EV=G['evidence']; NODE={n['id']:n for n in G['nodes']}
TH,OU,DE,CO=EV['themes'],EV['outcomes'],EV['designs'],EV['countries']; S=EV['studies']
les=collections.defaultdict(set)
for e in G['edges']:
    if e['origen'].startswith('L') and e['destino'].startswith(('SS:','PA:')): les[e['destino']].add(e['origen'])
EVSS=collections.defaultdict(list)
for ss,ks in EV['ssmap'].items():
    for k in ks: EVSS[k].append(ss)
# en la ruta EN_PAÍS no existe en graph (se deriva de operaciones): recalcularlo
opc={e['origen']:e['destino'] for e in G['edges'] if e['relacion']=='EJECUTADA_EN'}
for e in G['edges']:
    if e['origen'].startswith('L') and e['destino'].startswith('OP:'): les[opc[e['destino']]].add(e['origen'])
ops_of_lesson=collections.defaultdict(set)
for ed in G['edges']:
    if ed['origen'].startswith('L') and ed['destino'].startswith('OP:'): ops_of_lesson[ed['origen']].add(ed['destino'])
nops=lambda ls: len({o for l in ls for o in ops_of_lesson[l]})
rel=collections.defaultdict(set)
for ed in G['edges']:
    if ed['origen'].startswith('L') and ed['destino'][:3] in ('PB:','PR:'): rel[ed['origen']].add(ed['destino'])
def theme_lessons(k):
    tp=EV['topic'].get(str(k))
    if tp: return {l for l in rel if rel[l]&set(tp['pb']+tp['pr'])},'contenido del tema (tipo de problema/práctica)'
    cs=EV['core'].get(str(k),[])
    if cs: return {l for ss in cs for l in les[ss]},'lecciones de operaciones del subsector propio: '+'; '.join(NODE[s]['etiqueta'] for s in cs)
    return set(),'sin equivalente en las lecciones'
# hoja 1: estudios
E=pd.DataFrame([dict(titulo=s['t'],anio=s['y'],tipo_publicacion=s['tp'],intervenciones='; '.join(TH[i] for i in s['iv']),resultados='; '.join(OU[i] for i in s['ou']),
  diseno='; '.join(DE[i] for i in s['de']),paises='; '.join(CO[i] for i in s['co']),regiones='; '.join(s['rg']),con_paises_ALC='sí' if s['alc'] else 'no',enlace=s['u']) for s in S])
def matrix(sts):
    rows=[]
    for k,t in enumerate(TH):
        cl,basis=theme_lessons(k); bl={l for ss in EVSS[k] for l in les[ss]}
        r={'tema_de_intervencion':t,'lecciones':len(cl) if cl or basis[0]!='s' else None,'operaciones_de_las_que_se_extrajeron':nops(cl) if cl or basis[0]!='s' else None,'base_del_conteo':basis,'lecciones_subsectores_amplios':len(bl) if EVSS[k] else None,'operaciones_subsectores_amplios':nops(bl) if EVSS[k] else None,'estudios':sum(1 for s in sts if k in s['iv'])}
        for j,o in enumerate(OU): r[o]=sum(1 for s in sts if k in s['iv'] and j in s['ou'])
        rows.append(r)
    return pd.DataFrame(rows).sort_values('estudios',ascending=False)
M=matrix(S); MA=matrix([s for s in S if s['alc']])
# brechas por subsector
TL=len({l for v in les.values() for l in v if False}) or 80
rows=[]
for ss,ks in EV['ssmap'].items():
    st=[s for s in S if set(s['iv'])&set(ks)]; l=len(les[ss]); pl=round(100*l/80); pe=round(100*len(st)/len(S))
    lect='Sin estudios en el mapa' if not st else 'Pocas lecciones para comparar' if l<3 else 'Más presencia en las lecciones' if pl-pe>=10 else 'Más presencia en la evidencia' if pe-pl>=10 else 'Presencia similar'
    rows.append(dict(subsector=NODE[ss]['etiqueta'],lecciones=l,operaciones_del_subsector=nops(les[ss]),pct_de_las_lecciones=pl,estudios_afines=len(st),pct_de_los_estudios=pe,estudios_ALC=sum(s['alc'] for s in st),lectura=lect,temas_de_evidencia='; '.join(TH[k] for k in ks)))
for n in NODE.values():
    if n['tipo']=='Subsector' and n['id'] not in EV['ssmap']: rows.append(dict(subsector=n['etiqueta'],lecciones=len(les[n['id']]),operaciones_del_subsector=nops(les[n['id']]),pct_de_las_lecciones=round(100*len(les[n['id']])/80),lectura='Sin tema equivalente en el mapa de evidencia'))
B=pd.DataFrame(rows).sort_values('lecciones',ascending=False)
# país
rows=[]
for p in EV['idb']:
    pid=[k for k,n in NODE.items() if n['tipo']=='País' and n['etiqueta']==p]; l=len(les[pid[0]]) if pid else 0
    st=[s for s in S if CO.index(p) in s['co']] if p in CO else []
    tt=collections.Counter(TH[i] for s in st for i in s['iv']).most_common(3)
    rows.append(dict(pais=p,lecciones=l,operaciones_que_citan=len({o for o in NODE if o.startswith('OP:') and NODE[o].get('pais')==p and any(o in ops_of_lesson[x] for x in les[pid[0]])}) if pid else 0,estudios=len(st),temas_mas_estudiados='; '.join(f'{a} ({b})' for a,b in tt)))
P=pd.DataFrame(rows).sort_values(['lecciones','estudios'],ascending=False)
for path in ['/mnt/user-data/outputs/grafo_lecciones_transporte.xlsx']:
    with pd.ExcelWriter(path,engine='openpyxl',mode='a',if_sheet_exists='replace') as w:
        for nm,d in [('Brechas_subsector',B),('Matriz_evidencia',M),('Matriz_evidencia_ALC',MA),('Evidencia_pais',P),('Evidencia_estudios',E)]: d.to_excel(w,sheet_name=nm,index=False)
    wb=load_workbook(path); hf=Font(name='Arial',bold=True,color='FFFFFF',size=10); fill=PatternFill('solid',fgColor='1F3A5F'); bf=Font(name='Arial',size=10)
    for nm in ['Brechas_subsector','Matriz_evidencia','Matriz_evidencia_ALC','Evidencia_pais','Evidencia_estudios']:
        ws=wb[nm]
        for row in ws.iter_rows():
            for c in row: c.font=bf; c.alignment=Alignment(wrap_text=True,vertical='top')
        for c in ws[1]: c.font=hf; c.fill=fill; c.alignment=Alignment(wrap_text=True,vertical='bottom')
        ws.freeze_panes='B2' if nm.startswith('Matriz') else 'A2'; ws.auto_filter.ref=ws.dimensions
        for i,col in enumerate(ws.columns,1):
            m=max((len(str(c.value)) if c.value is not None else 0) for c in list(col)[:200]); ws.column_dimensions[get_column_letter(i)].width=min(max(11,m*0.9),70) if not nm.startswith('Matriz') or i==1 else 14
    wb.save(path); print(path, wb.sheetnames)
#print(B[['subsector','lecciones','estudios_afines','estudios_ALC','lectura']].to_string()); print(P.head(8).to_string()); print(M.iloc[:5,:6].to_string())
