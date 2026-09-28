import json, pandas as pd
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment, PatternFill
from openpyxl.utils import get_column_letter
G=json.load(open('out/graph_nlp.json',encoding='utf-8')); NODE={n['id']:n for n in G['nodes']}; NLP=G['nlp']
XL='nlp/out_lsa/resultados_nlp_lecciones.xlsx'
p='/mnt/user-data/outputs/grafo_lecciones_transporte.xlsx'
wb=load_workbook(p); bf=Font(name='Arial',size=10); al=Alignment(wrap_text=True,vertical='top')
def drop(ws,col,vals):
    for r in range(ws.max_row,1,-1):
        if ws.cell(r,col).value in vals: ws.delete_rows(r)
drop(wb['Nodos'],2,{'Cluster NLP','Subtema NLP'}); drop(wb['Aristas'],3,{'EN_CLUSTER_NLP','EN_SUBTEMA_NLP'}); drop(wb['Esquema'],2,{'EN_CLUSTER_NLP','EN_SUBTEMA_NLP'})
lm=wb['Léeme']
for r in range(lm.max_row,0,-1):
    if str(lm.cell(r,1).value or '').startswith(('Capa NLP','Hojas NLP','Advertencia NLP')): lm.delete_rows(r)
def add(ws,rows):
    for r in rows: ws.append(r)
    for row in ws.iter_rows(min_row=ws.max_row-len(rows)+1):
        for c in row: c.font=bf; c.alignment=al
nl=[n for n in G['nodes'] if n['tipo'] in ('Cluster NLP','Subtema NLP')]
add(wb['Nodos'],[[n['id'],n['tipo'],n['etiqueta'],None,None,None,None,(n.get('terminos') or '')+(' | ' if n.get('terminos') else '')+f"{n['n_lecciones']} lecciones (resultado provisional)",None,None,None] for n in nl])
ed=[e for e in G['edges'] if e['relacion'] in ('EN_CLUSTER_NLP','EN_SUBTEMA_NLP')]
add(wb['Aristas'],[[e['origen'],NODE[e['origen']]['etiqueta'],e['relacion'],e['destino'],NODE[e['destino']]['etiqueta'],1] for e in ed])
add(wb['Esquema'],[['Lección','EN_CLUSTER_NLP','Cluster NLP','Grupo semántico que arrojó HDBSCAN sobre el texto de la lección (provisional)'],
                   ['Lección','EN_SUBTEMA_NLP','Subtema NLP','Subtema NMF, solo para las lecciones del cluster dominante (provisional)']])
add(lm,[[''],[f"Capa NLP (análisis de texto): cada lección tiene un cluster semántico (HDBSCAN) y, si está en el cluster dominante, un subtema (NMF). {NLP['aviso']}"],
 ['Hojas NLP: NLP_lecciones (cluster, subtema y sector agrupado por lección) y NLP_subtemas (términos principales). El script y la corrida completa están en la carpeta analisis_texto_lecciones.'],
 ['Advertencia NLP: los clusters dependen de los hiperparámetros y de la semilla; con 80 textos son una exploración, no una clasificación. Se regeneran corriendo el script con embeddings SBERT y volviendo a construir el grafo.']])
wb.save(p)
# hojas nuevas
x=pd.ExcelFile(XL); L=pd.read_excel(x,'Lecciones'); T=pd.read_excel(x,'NMF_subtemas')
lab={int(n['id'].split(':')[1]):n['etiqueta'] for n in G['nodes'] if n['tipo']=='Cluster NLP'}
A=pd.DataFrame(dict(leccion=L['id'],sector_agrupado=L['grupo_sector'],subsectores=L['subsectores'],operaciones=L['operaciones'],cluster=L['cluster'].map(lab),
    prob_cluster=L['prob_cluster'].round(2),subtema=L['subtema_nmf'].map(lambda v: f"Subtema {int(v)}" if pd.notna(v) else '')))
B=T.rename(columns={'terminos':'términos_principales'})
with pd.ExcelWriter(p,engine='openpyxl',mode='a',if_sheet_exists='replace') as w:
    A.to_excel(w,sheet_name='NLP_lecciones',index=False); B.to_excel(w,sheet_name='NLP_subtemas',index=False)
wb=load_workbook(p); hf=Font(name='Arial',bold=True,color='FFFFFF',size=10); fill=PatternFill('solid',fgColor='1F3A5F')
for nm in ['NLP_lecciones','NLP_subtemas']:
    ws=wb[nm]
    for row in ws.iter_rows():
        for c in row: c.font=bf; c.alignment=al
    for c in ws[1]: c.font=hf; c.fill=fill
    ws.freeze_panes='A2'; ws.auto_filter.ref=ws.dimensions
    for i,col in enumerate(ws.columns,1): ws.column_dimensions[get_column_letter(i)].width=min(max(10,max(len(str(c.value or '')) for c in list(col)[:100])*0.95),60)
wb['Léeme'].column_dimensions['A'].width=120
wb.save(p); print('ok',len(nl),len(ed),wb['Nodos'].max_row,wb['Aristas'].max_row,wb.sheetnames[-3:])
