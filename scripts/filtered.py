import json, itertools, collections, pandas as pd, sys
sys.path.insert(0,'.')
G=json.load(open('out/graph_nlp.json',encoding='utf-8'))
NODE={n['id']:n for n in G['nodes']}
sel=[n['id'] for n in G['nodes'] if n['tipo']=='Lección' and 'Caminos rurales' in ''.join(NODE[e['destino']]['etiqueta'] for e in G['edges'] if e['origen']==n['id'] and e['destino'].startswith('SS:'))]
S=set(sel); print(len(sel),'lecciones')
base=[e for e in G['edges'] if e['origen'] in S]
ops={e['destino'] for e in base if e['destino'].startswith('OP:')}
base+=[e for e in G['edges'] if e['origen'] in ops and e['relacion']=='EJECUTADA_EN']
ids=set(S)|{e['destino'] for e in base}|{e['origen'] for e in base}
ssids={i for i in ids if i.startswith('SS:')}
tev=[e for e in G['edges'] if e['relacion']=='TIENE_EVIDENCIA' and e['origen'] in ssids]
base+=tev; ids|={e['destino'] for e in tev}
nodes=[n for n in G['nodes'] if n['id'] in ids]
EVD=dict(G['evidence']); TH=EVD['themes']
EVD['focus']=[TH.index(x) for x in ['Caminos rurales','Carreteras, autopistas y redes viales','Mantenimiento vial','Seguridad vial']]
def tgt(l,pre,rels): return [e['destino'] for e in base if e['origen']==l and e['relacion'] in rels and e['destino'].startswith(pre)]
mit,gen,prc=collections.Counter(),collections.Counter(),collections.Counter()
for l in sel:
    pb=tgt(l,'PB:',{'IDENTIFICA','PREVIENE'}); pr=tgt(l,'PR:',{'RECOMIENDA'}); cs=tgt(l,'CS:',{'REGISTRA'})
    for p,r in itertools.product(pb,pr): mit[(r,p)]+=1
    for p,c in itertools.product(pb,cs): gen[(p,c)]+=1
    for a,b in itertools.combinations(sorted(pr),2): prc[(a,b)]+=1
der=[dict(origen=a,destino=b,relacion='MITIGA',peso=w) for (a,b),w in mit.items()]+[dict(origen=a,destino=b,relacion='GENERA',peso=w) for (a,b),w in gen.items()]+[dict(origen=a,destino=b,relacion='SE_COMBINA_CON',peso=w) for (a,b),w in prc.items()]
sim=[e for e in G['sim'] if e['origen'] in S and e['destino'] in S]
F=dict(nodes=nodes,edges=base,derived=der,sim=sim,evidence=EVD,nlp=G.get('nlp'))
t=open('template.html',encoding='utf-8').read()
def rep(a,b):
    global t
    assert a in t,a; t=t.replace(a,b)
rep('<title>Grafo de lecciones de transporte</title>','<title>Grafo caminos rurales</title>')
rep('Grafo de conocimiento: lecciones aprendidas de transporte','Grafo de conocimiento: caminos rurales')
rep('Prototipo construido con las 80 lecciones curadas de INE/TSP.','Subconjunto de las 80 lecciones curadas de INE/TSP etiquetadas con el subsector caminos rurales.')
rep('thr = 3;','thr = 1;'); rep('id="th" min="1" max="5" value="3"','id="th" min="1" max="5" value="1"'); rep('<b id="thv">3</b>','<b id="thv">1</b>')
rep('data-q="expropiación">Buscar: expropiación<small>Lecciones sobre derechos de vía y expropiaciones</small>','data-q="seguridad vial">Buscar: seguridad vial<small>Accidentes y auditorías en zonas rurales</small>')
rep('data-q="Haití">Buscar: Haití<small>Lecciones de operaciones en un país</small>','data-q="El Salvador">Buscar: El Salvador<small>Lecciones de operaciones en un país</small>')
vis=open('vis/node_modules/vis-network/standalone/umd/vis-network.min.js',encoding='utf-8').read().replace('</script','<\\/script')
open('/mnt/user-data/outputs/grafo_caminos_rurales.html','w',encoding='utf-8').write(t.replace('__VIS__',vis).replace('__DATA__',json.dumps(F,ensure_ascii=False).replace('</','<\\/')))
# Excel
from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter
L=pd.read_csv('out/lecciones_extraidas.csv'); L=L[L.id.isin(S)]
lc=collections.defaultdict(list)
for e in base:
    if e['destino'].startswith('OP:'): lc[e['destino']].append(NODE[e['origen']]['codigo'].split('-')[-1])
O=pd.DataFrame([dict(operacion=NODE[o]['etiqueta'],nombre=NODE[o]['nombre'],pais=NODE[o]['pais'],n_lecciones=len(v),lecciones=', '.join(sorted(v,key=int))) for o,v in lc.items()]).sort_values(['n_lecciones','operacion'],ascending=[False,True])
lab={n['id']:n['etiqueta'] for n in nodes}
E=pd.DataFrame(base+der+sim); E['origen_etiqueta']=E.origen.map(lab); E['destino_etiqueta']=E.destino.map(lab); E=E[['origen','origen_etiqueta','relacion','destino','destino_etiqueta','peso']]
Nn=pd.DataFrame(nodes).reindex(columns=['id','tipo','etiqueta','codigo','subtipo','nombre','pais','problema_resumen','recomendacion_resumen','n_estudios','n_estudios_alc'])
X='/mnt/user-data/outputs/grafo_caminos_rurales.xlsx'
with pd.ExcelWriter(X,engine='openpyxl') as w:
    RS=pd.DataFrame([dict(titulo=s_['t'],anio=s_['y'],resultados='; '.join(EVD['outcomes'][i] for i in s_['ou']),diseno='; '.join(EVD['designs'][i] for i in s_['de']),paises='; '.join(EVD['countries'][i] for i in s_['co']),con_paises_ALC='sí' if s_['alc'] else 'no',enlace=s_['u']) for s_ in EVD['studies'] if TH.index('Caminos rurales') in s_['iv']]).sort_values(['con_paises_ALC','anio'],ascending=[False,False])
    for nm,d in [('Lecciones',L),('Operaciones',O),('Nodos',Nn),('Aristas',E),('Evidencia_caminos_rurales',RS)]: d.to_excel(w,sheet_name=nm,index=False)
wb=load_workbook(X); hf=Font(name='Arial',bold=True,color='FFFFFF',size=10); fill=PatternFill('solid',fgColor='1F3A5F'); bf=Font(name='Arial',size=10)
for ws in wb:
    for row in ws.iter_rows():
        for c in row: c.font=bf; c.alignment=Alignment(wrap_text=True,vertical='top')
    for c in ws[1]: c.font=hf; c.fill=fill
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    for i,col in enumerate(ws.columns,1):
        m=max((len(str(c.value)) if c.value is not None else 0) for c in list(col)[:200]); ws.column_dimensions[get_column_letter(i)].width=min(max(10,m*0.95),60)
ws=wb['Lecciones']
for i,c in enumerate(ws[1],1):
    if c.value in ('hallazgo','recomendacion'): ws.column_dimensions[get_column_letter(i)].width=70
wb.save(X); print(len(O),'operaciones',len(nodes),'nodos',len(base)+len(der)+len(sim),'aristas')
