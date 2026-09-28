# -*- coding: utf-8 -*-
"""Agrega al grafo (graph_ev.json -> graph_nlp.json) los resultados del análisis de texto: cluster semántico y subtema NMF de cada lección."""
import json, sys, pandas as pd
XL = sys.argv[1] if len(sys.argv) > 1 else 'nlp/out_lsa/resultados_nlp_lecciones.xlsx'
G = json.load(open('out/graph_ev.json', encoding='utf-8'))
x = pd.ExcelFile(XL); L = pd.read_excel(x, 'Lecciones'); T = pd.read_excel(x, 'NMF_subtemas'); R = pd.read_excel(x, 'Resumen', index_col=0)['valor']
backend = str(R['backend']); prov = backend == 'lsa'
by_code = {n['codigo']: n['id'] for n in G['nodes'] if n['tipo'] == 'Lección'}
assert set(L['id']) <= set(by_code), 'ids de lección sin nodo'
# clusters: letras por tamaño (dominante = A); ruido aparte
sizes = L[L.cluster >= 0].cluster.value_counts()
letter = {c: chr(65 + i) for i, c in enumerate(sizes.index)}
nodes, edges = [], []
for c, n in sizes.items():
    nodes.append(dict(id=f'NC:{c}', tipo='Cluster NLP', etiqueta=f'Cluster {letter[c]}' + (' (dominante)' if letter[c] == 'A' else ''), n_lecciones=int(n)))
if (L.cluster == -1).any():
    nodes.append(dict(id='NC:-1', tipo='Cluster NLP', etiqueta='Sin cluster (ruido)', n_lecciones=int((L.cluster == -1).sum())))
for _, r in T.iterrows():
    terms = [t.strip() for t in str(r['terminos']).split(',')]
    nodes.append(dict(id=f"NS:{int(r['subtema'])}", tipo='Subtema NLP', etiqueta=f"Subtema {int(r['subtema'])}: " + ', '.join(terms[:3]), terminos=', '.join(terms), n_lecciones=int(r['n_lecciones'])))
for _, r in L.iterrows():
    lid = by_code[r['id']]
    edges.append(dict(origen=lid, destino=f'NC:{int(r.cluster)}', relacion='EN_CLUSTER_NLP', peso=1))
    if pd.notna(r['subtema_nmf']): edges.append(dict(origen=lid, destino=f"NS:{int(r['subtema_nmf'])}", relacion='EN_SUBTEMA_NLP', peso=1))
G['nodes'] += nodes; G['edges'] += edges
G['nlp'] = dict(backend=backend, provisional=prov,
    aviso=('Resultado provisional: se calculó con una representación léxica (TF-IDF + SVD), no con embeddings multilingües SBERT. ' if prov else 'Embeddings multilingües SBERT. ') +
          'Con solo 80 textos los clusters son inestables; léase como exploración.',
    metodo='Embeddings → UMAP → HDBSCAN (número de clusters endógeno); subtemas por NMF dentro del cluster dominante.')
json.dump(G, open('out/graph_nlp.json', 'w', encoding='utf-8'), ensure_ascii=False)
print(len(nodes), 'nodos NLP', len(edges), 'aristas NLP', 'backend', backend)
L.assign(lid=L['id'].map(by_code))[['id']].to_csv('/dev/null')
