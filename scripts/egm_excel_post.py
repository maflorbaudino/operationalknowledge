import json
from openpyxl import load_workbook
from openpyxl.styles import Font, Alignment
G=json.load(open('out/graph_ev.json',encoding='utf-8')); NODE={n['id']:n for n in G['nodes']}
p='/mnt/user-data/outputs/grafo_lecciones_transporte.xlsx'
wb=load_workbook(p); bf=Font(name='Arial',size=10); al=Alignment(wrap_text=True,vertical='top')
# limpiar filas de una corrida anterior (idempotente)
def drop(ws,col,val):
    for r in range(ws.max_row,1,-1):
        if ws.cell(r,col).value==val: ws.delete_rows(r)
drop(wb['Nodos'],2,'Evidencia'); drop(wb['Aristas'],3,'TIENE_EVIDENCIA'); drop(wb['Esquema'],2,'TIENE_EVIDENCIA')
lm=wb['Léeme']
if lm.max_row>7: lm.delete_rows(8,lm.max_row-7)
def add(ws,rows):
    for r in rows: ws.append(r)
    for row in ws.iter_rows(min_row=ws.max_row-len(rows)+1):
        for c in row: c.font=bf; c.alignment=al
ev=[n for n in G['nodes'] if n['tipo']=='Evidencia']
add(wb['Nodos'],[[n['id'],'Evidencia',n['etiqueta'],None,None,None,None,f"{n['n_estudios']} estudios ({n['n_estudios_alc']} con países de ALC)",None,None,None] for n in ev])
te=[e for e in G['edges'] if e['relacion']=='TIENE_EVIDENCIA']
add(wb['Aristas'],[[e['origen'],NODE[e['origen']]['etiqueta'],'TIENE_EVIDENCIA',e['destino'],NODE[e['destino']]['etiqueta'],e['peso']] for e in te])
add(wb['Esquema'],[['Subsector','TIENE_EVIDENCIA','Evidencia','El tema del mapa de evidencia 3ie es afín al subsector (correspondencia definida a mano; peso = n.º de estudios del tema)']])
add(lm,[[''],['Capa de evidencia externa: mapa de evidencia de transporte de 3ie (Development Evidence Portal), exportación de 711 registros (CSV + RIS). La exportación NO trae la codificación del mapa (intervención, resultado, país), por lo que se clasificó automáticamente con reglas de palabras clave sobre título, resumen y palabras clave. Los conteos son aproximados y deben validarse contra la matriz oficial del portal.'],
 ['Hojas de evidencia: Brechas_subsector (lecciones vs estudios por subsector), Matriz_evidencia y Matriz_evidencia_ALC (tema de intervención x resultado, con lecciones al lado), Evidencia_pais (países BID: lecciones vs estudios), Evidencia_estudios (los 711 estudios con sus etiquetas y enlace).'],
 ['Cómo se cuentan las lecciones por tema: para seguridad vial, mantenimiento vial y reforma/APP, las lecciones cuyo contenido trata el tema (según el tipo de problema y práctica asignados al leerlas). Para los demás temas, las lecciones de operaciones de ese subsector, cuyo contenido suele ser de gestión de proyectos y no trata la modalidad; por eso hay que leerlas como «experiencia en operaciones de ese subsector», no como «lecciones sobre» el tema. La lectura del cruce compara el peso de cada subsector entre lecciones y estudios (10 puntos o más de diferencia; con menos de 3 lecciones no se compara).'],
 ['La correspondencia subsector-tema es una decisión de diseño (por ejemplo, Transporte público se compara con buses/BRT/metro, tarifas y movilidad compartida). Un estudio puede contarse en varios temas y resultados, y los subsectores comparten temas, así que los totales no se suman.']])
lm.column_dimensions['A'].width=120
wb.save(p); print('post ok',len(ev),len(te),wb['Nodos'].max_row,wb['Aristas'].max_row)
