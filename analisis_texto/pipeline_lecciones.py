# -*- coding: utf-8 -*-
"""
Pipeline de análisis de texto de las lecciones aprendidas curadas de transporte (INE/TSP).

Etapas
  1. Preprocesamiento: corrección de encoding, separación Hallazgo/Recomendación, oraciones, lematización (simplemma).
  2. Representación semántica: embeddings multilingües de oración (Reimers & Gurevych, 2019; backend "sbert")
     o, si no hay acceso al modelo, un sustituto LSA sobre TF-IDF de lemas (backend "lsa").
  3. Reducción de dimensionalidad con UMAP.
  4. Clustering por densidad con HDBSCAN (número de clusters endógeno) y análisis de sensibilidad.
  5. Subtemas del cluster dominante con NMF sobre TF-IDF de lemas.
  6. Rasgos discursivos (lenguaje prescriptivo, atribución de responsabilidad) por oración, con
     regresiones logísticas con efectos fijos por sector (y por año, si se aporta la tabla operación -> año)
     y errores estándar agrupados por lección.

Uso
  python pipeline_lecciones.py --csv Curated-Lessons-Learned-TSP.csv --backend sbert --out resultados
  python pipeline_lecciones.py --csv ... --backend lsa                       # sustituto sin descargar modelos
  python pipeline_lecciones.py --csv ... --backend sbert --years anios.csv   # anios.csv: columnas operacion,anio

Dependencias: pandas numpy scikit-learn umap-learn hdbscan simplemma ftfy statsmodels matplotlib openpyxl
              y, para el backend sbert, sentence-transformers.
"""
import argparse, json, os, re, sys, unicodedata, warnings, collections
import numpy as np, pandas as pd

SEED = 42
warnings.filterwarnings('ignore')

# ----------------------------------------------------------------------------------------------
# 1. PREPROCESAMIENTO
# ----------------------------------------------------------------------------------------------
def fix_text(s):
    """Corrige mojibake (ftfy), normaliza Unicode (NFC), espacios no separables y comillas/guiones tipográficos."""
    import ftfy
    s0 = str(s)
    moji = ftfy.fix_encoding(s0) != s0          # mojibake real (p. ej. 'JosÃ©')
    s = ftfy.fix_text(s0, normalization='NFC')
    s = s.replace('\xa0', ' ').replace('​', '')
    s = re.sub(r'[“”«»]', '"', s); s = re.sub(r'[‘’]', "'", s); s = re.sub(r'[–—]', '-', s)
    s = re.sub(r'[ \t]+', ' ', s)
    s = re.sub(r'\s*\n\s*', '\n', s).strip()
    return s, dict(cambio=(s != s0), mojibake=moji)

def split_sections(text):
    """Separa 'Hallazgo:' de 'Recomendación:'."""
    m = re.search(r'Recomendaci[oó]n(?:es)?\s*:', text)
    if not m: return re.sub(r'^"?Hallazgos?\s*:', '', text).strip(), ''
    hall = re.sub(r'^"?Hallazgos?\s*:', '', text[:m.start()]).strip()
    rec = text[m.end():].strip().strip('"')
    return re.sub(r'\s+', ' ', hall), re.sub(r'\s+', ' ', rec)

SENT_SPLIT = re.compile(r'(?<=[.!?;])\s+(?=[A-ZÁÉÍÓÚÑ¿¡"(])')
def sentences(text):
    out = []
    for part in re.split(r'\n+', text):
        for s in SENT_SPLIT.split(part):
            s = s.strip(' .;')
            if len(s.split()) >= 3: out.append(s)
    return out

STOP = set('''a al algo algunas algunos ante antes aquel aquella aquellas aquellos aqui asi aun aunque bajo cada casi como con contra cual cuales cuando de del desde donde dos durante e el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta estaba estan estar este esto estos fue fueron ha haber habia han hasta hay la las le les lo los mas me mi mientras muy nada ni no nos nuestra nuestro o os otra otras otro otros para pero poco por porque que quien quienes se sea sean segun ser si sido sin sobre solo son su sus tambien tanto te tiene tienen todo todos tras tu tus un una unas uno unos y ya
ademas asi cabe dado debido dentro etc ejemplo forma medio mediante parte puede pueden podria podrian pues respecto tal tales tipo vez veces via vista sido siendo estar estan estado estados hacer hace hacen cada cual cuyo cuya cuyos cuyas dicho dicha dichos dichas mismo misma mismos mismas
uno dos tres primero segundo ambos otro'''.split())
DOMAIN_STOP = set('proyecto programa operacion lecciones leccion hallazgo recomendacion ejecucion'.split())  # se usan solo en NMF

_nfd = lambda s: ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
def lemmatize(text, drop_domain=False):
    import simplemma
    toks = re.findall(r"[a-záéíóúñü]+", text.lower())
    out = []
    for t in toks:
        if len(t) < 3: continue
        l = simplemma.lemmatize(t, lang='es')
        base = _nfd(l)
        if base in STOP or _nfd(t) in STOP: continue
        if drop_domain and base in DOMAIN_STOP: continue
        out.append(base)
    return out

SUBSECTOR_ES = {'TRANSPORT': 'Transporte (general)', 'MAJOR HIGHWAYS': 'Carreteras principales', 'URBAN TRANSPORT INFRASTRUCTURE': 'Infraestructura de transporte urbano',
    'TRANSPORT NETWORKS CONNECTIVITY': 'Conectividad de redes de transporte', 'RURAL ROADS': 'Caminos rurales', 'SECONDARY ROADS': 'Caminos secundarios',
    'PRIVATE FIRMS AND SME DEVELOPMENT': 'Desarrollo de empresas privadas y PYME', 'INDIGENOUS PEOPLES DEVELOPMENT': 'Desarrollo de pueblos indígenas',
    'LOGISTIC PLANNING, MULTIMODAL TRANSPORT AND LOGISTIC PLATFORMS': 'Planificación logística y transporte multimodal',
    'PUBLIC TRANSPORT (BUS / TRAIN / CABLE': 'Transporte público', 'NON-MOTORIZED URBAN TRANSPORT': 'Transporte urbano no motorizado',
    'REFORM / MODERNIZATION OF THE STATE': 'Reforma y modernización del Estado', 'ROAD MAINTENANCE': 'Mantenimiento vial', 'ROAD SAFETY': 'Seguridad vial'}
# Agrupación propuesta (a revisar): 5 grupos de "sector"
GROUP_OF = {'MAJOR HIGHWAYS': 'Vial', 'SECONDARY ROADS': 'Vial', 'RURAL ROADS': 'Vial', 'ROAD MAINTENANCE': 'Vial', 'ROAD SAFETY': 'Vial',
    'URBAN TRANSPORT INFRASTRUCTURE': 'Urbano y transporte público', 'PUBLIC TRANSPORT (BUS / TRAIN / CABLE': 'Urbano y transporte público', 'NON-MOTORIZED URBAN TRANSPORT': 'Urbano y transporte público',
    'LOGISTIC PLANNING, MULTIMODAL TRANSPORT AND LOGISTIC PLATFORMS': 'Logística y conectividad', 'TRANSPORT NETWORKS CONNECTIVITY': 'Logística y conectividad',
    'REFORM / MODERNIZATION OF THE STATE': 'Institucional y desarrollo productivo/social', 'PRIVATE FIRMS AND SME DEVELOPMENT': 'Institucional y desarrollo productivo/social',
    'INDIGENOUS PEOPLES DEVELOPMENT': 'Institucional y desarrollo productivo/social', 'TRANSPORT': 'General'}
# desempate: gana el grupo menos frecuente en el corpus (Vial domina por MAJOR HIGHWAYS)
GROUP_PRIORITY = ['Institucional y desarrollo productivo/social', 'Urbano y transporte público', 'Logística y conectividad', 'Vial', 'General']
def sector_group(subsectors):
    tags = [GROUP_OF[s] for s in subsectors if s in GROUP_OF and s != 'TRANSPORT']
    if not tags: return 'General'
    c = collections.Counter(tags); top = max(c.values())
    return next(g for g in GROUP_PRIORITY if c.get(g, 0) == top)

def load_and_preprocess(csv_path, years_path=None):
    raw = pd.read_csv(csv_path)
    rows, nfix, nmoji = [], 0, 0
    for _, r in raw.iterrows():
        txt, ch = fix_text(r['Lesson Learned']); nfix += ch['cambio']; nmoji += ch['mojibake']
        hall, rec = split_sections(txt)
        subs = [re.sub(r'\s+', ' ', fix_text(x)[0]).strip() for x in str(r['Subsector']).split(';')]
        ops = [x.strip() for x in str(r['Oper Numbers']).split(';')]
        n = int(str(r['Curated Lesson Learned ID']).split('-')[-1])
        rows.append(dict(id=r['Curated Lesson Learned ID'], n=n, hallazgo=hall, recomendacion=rec, texto=(hall + ' ' + rec).strip(),
                         subsectores=subs, grupo_sector=sector_group(subs), operaciones=ops, paises=sorted({o[:2] for o in ops}),
                         fuente_riesgo=r['Risk Source'], categoria_riesgo=r['Risk Category Name']))
    df = pd.DataFrame(rows)
    df['lemas'] = df['texto'].apply(lemmatize)
    df['lemas_txt'] = df['lemas'].apply(' '.join)
    if years_path:
        y = pd.read_csv(years_path); y.columns = [c.strip().lower() for c in y.columns]
        ymap = dict(zip(y['operacion'].astype(str).str.strip(), y['anio'].astype(int)))
        # año de la lección = año de la operación más antigua citada (documentado; se puede cambiar)
        df['anio'] = df['operaciones'].apply(lambda L: min([ymap[o] for o in L if o in ymap], default=np.nan))
    else:
        df['anio'] = np.nan
    return df, dict(n_textos_con_mojibake=int(nmoji), n_textos_normalizados=int(nfix))


# ----------------------------------------------------------------------------------------------
# 2. EMBEDDINGS  (sbert = Reimers & Gurevych 2019  |  lsa = sustituto TF-IDF + SVD, sin descarga)
# ----------------------------------------------------------------------------------------------
SBERT_MODEL = 'paraphrase-multilingual-mpnet-base-v2'

def embed(df, backend='sbert', lsa_dims=25):
    """Devuelve matriz (n x d) con filas normalizadas (norma L2 = 1)."""
    if backend == 'sbert':
        from sentence_transformers import SentenceTransformer
        m = SentenceTransformer(SBERT_MODEL)
        # se usa el texto original (sin lematizar): los transformers se benefician del contexto y la morfología
        E = m.encode(df['texto'].tolist(), batch_size=16, show_progress_bar=False, normalize_embeddings=True)
        return np.asarray(E)
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD
    from sklearn.preprocessing import normalize
    X = TfidfVectorizer(min_df=2, max_df=0.6, sublinear_tf=True, ngram_range=(1, 2)).fit_transform(df['lemas_txt'])
    k = min(lsa_dims, X.shape[1] - 1, X.shape[0] - 1)
    Z = TruncatedSVD(k, random_state=SEED).fit_transform(X)
    return normalize(Z)

# ----------------------------------------------------------------------------------------------
# 3-4. UMAP + HDBSCAN
# ----------------------------------------------------------------------------------------------
def run_umap(E, n_neighbors=10, n_components=5, min_dist=0.0, seed=SEED):
    import umap
    return umap.UMAP(n_neighbors=n_neighbors, n_components=n_components, min_dist=min_dist, metric='cosine', random_state=seed).fit_transform(E)

def run_hdbscan(U, min_cluster_size=5, min_samples=None):
    import hdbscan
    c = hdbscan.HDBSCAN(min_cluster_size=min_cluster_size, min_samples=min_samples, metric='euclidean',
                        cluster_selection_method='eom', prediction_data=False).fit(U)
    return c.labels_, c.probabilities_

def sensitivity(E, base=(10, 5), grid_nn=(5, 8, 10, 15), grid_mcs=(3, 4, 5, 6, 8), seeds=(0, 1, 2, 3, 4)):
    """Barrido de hiperparámetros y de semillas de UMAP. La configuración base se fija ex ante (no se elige por resultados)."""
    from sklearn.metrics import adjusted_rand_score as ari
    U0 = run_umap(E, base[0]); L0, _ = run_hdbscan(U0, base[1])
    rows = []
    for nn in grid_nn:
        for mcs in grid_mcs:
            for sd in seeds:
                U = run_umap(E, nn, seed=SEED + sd); L, _ = run_hdbscan(U, mcs)
                k = len(set(L)) - (1 if -1 in L else 0)
                rows.append(dict(n_neighbors=nn, min_cluster_size=mcs, semilla=sd, n_clusters=k, pct_ruido=float((L == -1).mean() * 100),
                                 tam_mayor=int(np.bincount(L[L >= 0]).max()) if k else 0, ARI_vs_base=float(ari(L0, L))))
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------------------------
# 5. NMF: subtemas dentro del cluster dominante
# ----------------------------------------------------------------------------------------------
def _npmi_coherence(top_terms, binary_doc_term, vocab_idx, eps=1e-12):
    """Coherencia NPMI media de los términos top de cada tema (co-ocurrencia a nivel documento)."""
    N = binary_doc_term.shape[0]; scores = []
    for terms in top_terms:
        idx = [vocab_idx[t] for t in terms]; s = []
        for i in range(len(idx)):
            for j in range(i + 1, len(idx)):
                a, b = binary_doc_term[:, idx[i]], binary_doc_term[:, idx[j]]
                pa, pb, pab = a.mean(), b.mean(), (a & b).mean()
                if pab == 0: s.append(-1.0); continue
                s.append(np.log(pab / (pa * pb) + eps) / (-np.log(pab) + eps))
        scores.append(np.mean(s))
    return float(np.mean(scores))

def nmf_topics(texts_lem, ks=(2, 3, 4, 5, 6, 7, 8), n_top=8, seeds=range(12)):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import NMF
    docs = [' '.join(t for t in d.split() if t not in DOMAIN_STOP) for d in texts_lem]
    vec = TfidfVectorizer(min_df=3, max_df=0.7, sublinear_tf=True); X = vec.fit_transform(docs)
    vocab = np.array(vec.get_feature_names_out()); vidx = {t: i for i, t in enumerate(vocab)}
    B = (X.toarray() > 0)
    rows, models = [], {}
    for k in ks:
        comps = []
        for sd in seeds:
            m = NMF(k, init='random', random_state=sd, max_iter=2000, tol=1e-5).fit(X); comps.append(m.components_)
            if sd == 0: models[k] = m
        # estabilidad: similitud coseno media entre cada tema (semilla s) y su mejor pareja en la semilla 0 (inicialización aleatoria)
        def unit(A): return A / (np.linalg.norm(A, axis=1, keepdims=True) + 1e-12)
        ref = unit(comps[0]); stab = np.mean([np.mean(np.max(unit(c) @ ref.T, axis=1)) for c in comps[1:]])
        top = [list(vocab[np.argsort(-w)[:n_top]]) for w in models[k].components_]
        rows.append(dict(k=k, coherencia_npmi=_npmi_coherence(top, B, vidx), estabilidad_semillas=float(stab),
                         error_reconstruccion=float(models[k].reconstruction_err_)))
    sel = pd.DataFrame(rows)
    # k elegido: mayor coherencia NPMI entre los k estables (>= 0.85) y parsimoniosos (k <= n/8); si ninguno cumple, el más estable
    # restricción de parsimonia: al menos ~8 documentos por subtema en promedio (k <= n/8)
    ok = sel[(sel.estabilidad_semillas >= 0.85) & (sel.k <= max(2, len(docs) // 8))]
    k_star = int(ok.loc[ok.coherencia_npmi.idxmax(), 'k']) if len(ok) else int(sel.loc[sel.estabilidad_semillas.idxmax(), 'k'])
    m = models[k_star]; W = m.transform(X)
    top = pd.DataFrame([dict(subtema=i + 1, terminos=', '.join(vocab[np.argsort(-w)[:n_top]])) for i, w in enumerate(m.components_)])
    return dict(seleccion=sel, k=k_star, W=W, top=top, vocab=vocab)


# ----------------------------------------------------------------------------------------------
# 6. RASGOS DISCURSIVOS (léxicos por oración) + REGRESIONES LOGÍSTICAS
# ----------------------------------------------------------------------------------------------
def _norm(s): return _nfd(s.lower())

NOT_VERBS = set('''mujer mujeres lugar lugares militar particular calendar pilar ejemplar regular popular secular similar familiar
titular singular polar molecular vascular muscular circular ver mar par par mayor mejor peor menor superior inferior interior exterior
posterior anterior ulterior senior junior motor sector doctor factor actor director inspector ejecutor prestador contratador
tener ser poder saber querer haber hacer deber dar ir ver'''.split())
# 'tener/ser/...' se excluyen como apertura de oración: 'Ser' o 'Tener' rara vez son una prescripción explícita

_ADJ = r'(necesari|fundamental|imprescindible|indispensable|esencial|recomendable|conveniente|clav|importante|prioritari)\w*'
# el adjetivo deóntico solo cuenta si introduce una acción ("es importante reforzar…", "es necesario que…"); "es clave para el uso" es descriptivo
DEONTIC = [r'\bse debe(n|ria|rian)?\b', r'\bdebe(n|ria|rian)?\b', r'\bes ' + _ADJ + r' (que|[a-z]{3,}(ar|er|ir))\b',
           r'\bresulta ' + _ADJ + r' (que|[a-z]{3,}(ar|er|ir))\b', r'\bse recomienda\w*', r'\bconviene\b',
           r'\bhay que\b', r'\bse requiere(n)?\b', r'\bse necesita(n)?\b', r'\bes (preciso|obligatori)\w*', r'\bse sugiere\b', r'\bse aconseja\b']
RESP_LEX = [r'\bresponsab\w+', r'\ba cargo de\b', r'\bencargad\w+', r'\batribuibl\w+', r'\bincumpl\w+', r'(?<!si )\bcorresponde(n)? (a|al|a la|a los|a las)\b',
            r'\bcompetencia(s)? (de|del)\b', r'\bpor parte (de|del)\b', r'\brinde(n)? cuentas\b', r'\broles?\b', r'\bfalta de (compromiso|liderazgo|apropiacion)\b']
# Actores institucionales a los que el texto puede atribuir una función o una falla (no incluye beneficiarios ni comunidades)
ACTORS = (r'(unidad(es)? (ejecutora|ejecutoras|ejecutores|gestora|gestoras|coordinadora|coordinadoras)|organismo(s)? (ejecutor|ejecutores)|entidad(es)? (ejecutora|ejecutoras|responsables?)|'
          r'agencia(s)? (ejecutora|ejecutoras|responsables?)|ministerio(s)?|ejecutor(es|a|as)?|equipo(s)? (ejecutor|ejecutores|responsables?|encargado)|gobierno(s)?|autoridad(es)?|'
          r'banco|prestatari[oa]s?|contratista(s)?|consultor(es|a|as)?|firma(s)? (consultora|consultoras|contratista)|supervisor(es|a|as)?|operador(es|a|as)?|organo(s)?|constructor(es|a|as)?|concesionari[oa]s?|municipi(o|os)|municipalidad(es)?)')
_ACTOR = re.compile(r'\b' + ACTORS + r'\b')
_DEF = re.compile(r'\b(capacidad|debilidad(es)?|limitacion(es)?|obsolescencia|falta|ausencia|rotacion|desempeno|experiencia|competencia|flexibilidad|liderazgo|compromiso|apropiacion|carencia|insuficiencia)\b(\s+\w+){0,9}?\s+(del|de la|de los|de las|de)\s+(\w+\s+){0,1}?' + ACTORS + r'\b')
# variante estricta: actor + verbo de deber/falla en la misma proposición
ACTOR_DUTY = re.compile(r'\b' + ACTORS + r'\b(\s+\w+){0,5}?\s+(debe(n)?|deberia(n)?|no |asum\w+|incumpl\w+|fall\w+|omit\w+|dej\w+ de|tuvo|tuvieron|tiene(n)? que|es (el )?responsable|son (los )?responsables|a cargo)', re.I)
IMPERS = re.compile(r'\bse (\w+ )?(?!debe|requier|recomiend|necesit|sugier|aconsej)\w+(a|e|an|en|o|ia|ian)\b', re.I)  # 'se' impersonal / pasiva refleja (control)

_DEON = re.compile('|'.join(DEONTIC)); _RESP = re.compile('|'.join(RESP_LEX))
def flags_sentence(s):
    t = _norm(s); first = re.findall(r'[a-z]+', t)[:1]
    inf = bool(first) and re.fullmatch(r'[a-z]{4,}(ar|er|ir)(se)?(lo|la|los|las|le|les)?', first[0]) is not None and first[0] not in NOT_VERBS
    m2 = re.match(r'^[^,]{3,70},\s*([a-z]{4,}(?:ar|er|ir))(?:se)?\b', t)         # "En la fase de diseño, considerar…"
    inf = inf or (m2 is not None and m2.group(1) not in NOT_VERBS)
    deon = bool(_DEON.search(t))
    resp = bool(_RESP.search(t)); actor = bool(_ACTOR.search(t)); duty = bool(ACTOR_DUTY.search(t)); dfc = bool(_DEF.search(t))
    return dict(prescr_inf=inf, prescr_deon=deon, prescriptivo=inf or deon, atrib_resp=resp, atrib_deficit=dfc, atrib_deber=duty, menciona_actor=actor, atribucion=resp or dfc or duty,
                impersonal=bool(re.search(r'\bse [a-z]+', t)))

def sentence_table(df):
    rows = []
    for _, r in df.iterrows():
        for sec, txt in (('Hallazgo', r['hallazgo']), ('Recomendación', r['recomendacion'])):
            for i, s in enumerate(sentences(txt)):
                rows.append(dict(id=r['id'], seccion=sec, n_oracion=i + 1, oracion=s, **flags_sentence(s)))
    return pd.DataFrame(rows)


def lesson_table(df, S, labels):
    """Nivel lección: cluster, y proporciones/indicadores de rasgos."""
    g = S.groupby('id')
    T = df[['id', 'grupo_sector', 'anio']].copy()
    T['cluster'] = labels
    for c in ['prescriptivo', 'atribucion', 'menciona_actor', 'prescr_deon', 'atrib_resp']:
        T['p_' + c] = T['id'].map(g[c].mean())
    T['n_oraciones'] = T['id'].map(g.size())
    T['hall_prescriptivo'] = T['id'].map(S[S.seccion == 'Hallazgo'].groupby('id')['prescriptivo'].max()).fillna(False).astype(int)
    T['algun_atribucion'] = T['id'].map(g['atribucion'].max()).astype(int)
    T['algun_actor'] = T['id'].map(g['menciona_actor'].max()).astype(int)
    return T

def fit_logit(formula, data, groups):
    import statsmodels.formula.api as smf
    m = smf.logit(formula, data=data).fit(disp=0, maxiter=200, cov_type='cluster', cov_kwds={'groups': data[groups]})
    return m

def _row(m, term, spec, y, n, ncl, note=''):
    b, se, p = m.params[term], m.bse[term], m.pvalues[term]
    if not np.isfinite(se) or abs(b) > 8 or se > 8:      # separación (casi) perfecta: la estimación no es interpretable
        return dict(resultado=y, especificacion=spec, n_obs=n, n_lecciones=ncl, nota='no estimable: separación casi perfecta (pocos casos positivos)')
    ci = m.conf_int().loc[term]
    return dict(resultado=y, especificacion=spec, n_obs=n, n_lecciones=ncl, coef_logit=b, ee_agrupado=se, OR=np.exp(b), OR_ic95_bajo=np.exp(ci[0]), OR_ic95_alto=np.exp(ci[1]), p_valor=p, nota=note)

def regressions(df, S, labels, dominant, use_year=False):
    """Rasgo discursivo ~ cluster dominante, con efectos fijos de sector (y de año si hay tabla operación->año).
    Oración: y_ij ~ dominante_i + sección_ij + FE sector (+ FE año), EE agrupados por lección.
    Lección (robustez): y_i ~ dominante_i + FE sector (+ FE año)."""
    T = lesson_table(df, S, labels)
    T['dominante'] = (T['cluster'] == dominant).astype(int)
    Sd = S.merge(T[['id', 'dominante', 'grupo_sector', 'anio', 'cluster']], on='id')
    Sd['es_recom'] = (Sd['seccion'] == 'Recomendación').astype(int)
    for c in ['prescriptivo', 'atribucion', 'menciona_actor']: Sd[c] = Sd[c].astype(int)
    fe = ' + C(grupo_sector)'; specs = [('FE sector', fe)]
    if use_year and T['anio'].notna().all():
        T['anio'] = T['anio'].astype(int); Sd['anio'] = Sd['anio'].astype(int)
        T['lustro'] = (T['anio'] // 5) * 5; Sd['lustro'] = (Sd['anio'] // 5) * 5
        specs = [('FE sector', fe), ('FE sector + año', fe + ' + C(anio)'), ('FE sector + lustro', fe + ' + C(lustro)')]
    rows = []
    for y, sec in [('prescriptivo', ' + es_recom'), ('atribucion', ' + es_recom'), ('menciona_actor', ' + es_recom')]:
        for name, f in specs:
            for lab, D, T_ in [('todas las lecciones', Sd, T), ('sin ruido HDBSCAN', Sd[Sd.cluster >= 0], T[T.cluster >= 0])]:
                try:
                    m = fit_logit(f'{y} ~ dominante{sec}{f}', D, 'id'); rows.append(_row(m, 'dominante', f'Oración | {name} | {lab}', y, int(m.nobs), D['id'].nunique()))
                except Exception as e:
                    rows.append(dict(resultado=y, especificacion=f'Oración | {name} | {lab}', nota=f'no estimable: {type(e).__name__}'))
    # nivel lección
    for y, lab_y in [('hall_prescriptivo', 'Hallazgo con lenguaje prescriptivo'), ('algun_atribucion', 'alguna oración atribuye responsabilidad'), ('algun_actor', 'alguna oración menciona un actor')]:
        for name, f in specs:
            try:
                m = fit_logit(f'{y} ~ dominante{f}', T, 'id'); rows.append(_row(m, 'dominante', f'Lección | {name} | todas', lab_y, int(m.nobs), T['id'].nunique()))
            except Exception as e:
                rows.append(dict(resultado=lab_y, especificacion=f'Lección | {name} | todas', nota=f'no estimable: {type(e).__name__}'))
    return pd.DataFrame(rows), T, Sd


# ----------------------------------------------------------------------------------------------
# Robustez: clustering sin los términos de los léxicos de atribución (evita circularidad léxica)
# ----------------------------------------------------------------------------------------------
LEX_STEMS = ('ejecutor', 'ejecutora', 'unidad', 'organismo', 'responsable', 'responsabilidad', 'encargar', 'rol', 'gobierno', 'ministerio', 'contratista',
             'consultor', 'consultora', 'supervisor', 'autoridad', 'banco', 'prestatario', 'agencia', 'entidad', 'gestora', 'operador', 'funcion', 'equipo')
def drop_lexicon(df):
    d = df.copy(); d['lemas_txt'] = d['lemas'].apply(lambda L: ' '.join(t for t in L if t not in LEX_STEMS)); return d

# ----------------------------------------------------------------------------------------------
# Figuras
# ----------------------------------------------------------------------------------------------
INK, INK2, GRID, SURF = '#0b0b0b', '#52514e', '#e4e3df', '#fcfcfb'
CAT = ['#2a78d6', '#eb6834', '#1baf7a']      # slots 1-3 de la paleta (validan todos los pares); más de 3 clusters se pliegan a "otros"
NOISE = '#9a998f'
MARKERS = ['o', 's', '^']

def _style(ax):
    ax.set_facecolor(SURF); ax.tick_params(colors=INK2, labelsize=9)
    for s in ('top', 'right'): ax.spines[s].set_visible(False)
    for s in ('left', 'bottom'): ax.spines[s].set_color(GRID)
    ax.grid(color=GRID, lw=0.6); ax.set_axisbelow(True)

def fig_umap(E, labels, dominant, path, backend, seed=SEED, n_neighbors=10):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    Z = run_umap(E, n_neighbors, n_components=2, seed=seed)
    fig, ax = plt.subplots(figsize=(7.2, 5), facecolor=SURF); _style(ax)
    ids = [c for c in sorted(set(labels)) if c >= 0]
    order = [dominant] + [c for c in ids if c != dominant]
    shown = order[:3]
    ax.scatter(*Z[labels == -1].T, s=34, c=NOISE, marker='x', lw=1.2, label=f'Ruido (n={int((labels == -1).sum())})')
    for i, c in enumerate(shown):
        m = labels == c
        ax.scatter(*Z[m].T, s=42, c=CAT[i], marker=MARKERS[i], edgecolor=SURF, lw=1.2, label=f'Cluster {c}{" (dominante)" if c == dominant else ""} (n={int(m.sum())})')
    rest = [c for c in order[3:]]
    if rest:
        m = np.isin(labels, rest); ax.scatter(*Z[m].T, s=34, c='#c9c8be', marker='D', edgecolor=SURF, lw=1.2, label=f'Otros clusters (n={int(m.sum())})')
    ax.set_xlabel('UMAP 1', color=INK2); ax.set_ylabel('UMAP 2', color=INK2)
    ax.set_title(f'Lecciones en el espacio semántico (UMAP 2D), backend: {backend}', color=INK, fontsize=11, loc='left')
    ax.legend(frameon=False, fontsize=9, labelcolor=INK2, loc='best')
    fig.tight_layout(); fig.savefig(path, dpi=160, facecolor=SURF); plt.close(fig); return Z

def fig_sens(S, path):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    from matplotlib.colors import LinearSegmentedColormap
    g = S.groupby(['n_neighbors', 'min_cluster_size']).agg(ruido=('pct_ruido', 'mean'), k=('n_clusters', 'mean')).reset_index()
    P = g.pivot(index='n_neighbors', columns='min_cluster_size', values='ruido'); K = g.pivot(index='n_neighbors', columns='min_cluster_size', values='k')
    fig, ax = plt.subplots(figsize=(7.2, 4.2), facecolor=SURF)
    cm = LinearSegmentedColormap.from_list('s', ['#e8f0fb', '#2a78d6', '#0d2f5c'])
    im = ax.imshow(P.values, cmap=cm, vmin=0, vmax=100, aspect='auto')
    ax.set_xticks(range(P.shape[1])); ax.set_xticklabels(P.columns); ax.set_yticks(range(P.shape[0])); ax.set_yticklabels(P.index)
    for i in range(P.shape[0]):
        for j in range(P.shape[1]):
            v = P.values[i, j]; ax.text(j, i, f'{K.values[i, j]:.1f} cl.\n{v:.0f}% ruido', ha='center', va='center', fontsize=8, color='white' if v > 45 else INK)
    ax.set_xlabel('min_cluster_size (HDBSCAN)', color=INK2); ax.set_ylabel('n_neighbors (UMAP)', color=INK2)
    ax.set_title('Sensibilidad: clusters (promedio de 5 semillas) y % de lecciones sin cluster', color=INK, fontsize=10.5, loc='left')
    for s in ax.spines.values(): s.set_visible(False)
    ax.tick_params(colors=INK2, labelsize=9); fig.colorbar(im, ax=ax, label='% ruido').outline.set_visible(False)
    fig.tight_layout(); fig.savefig(path, dpi=160, facecolor=SURF); plt.close(fig)

def fig_nmf(nmf, W, path, n_docs_by_topic=None, n_top=8):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    k = nmf['k']; comp = nmf['comp']; vocab = nmf['vocab']
    cols = 3; rows = int(np.ceil(k / cols)); fig, axes = plt.subplots(rows, cols, figsize=(10.5, 2.6 * rows), facecolor=SURF)
    for i, ax in enumerate(np.atleast_1d(axes).ravel()):
        if i >= k: ax.axis('off'); continue
        _style(ax); idx = np.argsort(-comp[i])[:n_top][::-1]
        ax.barh(vocab[idx], comp[i][idx], color=CAT[0], height=0.55)
        ax.set_title(f'Subtema {i + 1} (n={n_docs_by_topic[i]} lecciones)', fontsize=9.5, color=INK, loc='left'); ax.grid(axis='y', visible=False)
    fig.suptitle('Subtemas NMF dentro del cluster dominante: términos de mayor peso', color=INK, fontsize=11, x=0.01, ha='left')
    fig.tight_layout(); fig.savefig(path, dpi=160, facecolor=SURF); plt.close(fig)

def _short(r):
    y = {'prescriptivo': 'Prescriptivo', 'atribucion': 'Atribución', 'menciona_actor': 'Menciona actor'}.get(r.resultado, 'Hallazgo prescriptivo' if r.resultado.startswith('Hallazgo') else ('Lección: atribuye' if 'atribuye' in r.resultado else 'Lección: menciona actor'))
    e = r.especificacion.replace('Oración', 'Oración').replace(' | clusters sin términos del léxico', ' | sin léxico').replace('todas las lecciones', 'todas').replace('sin ruido HDBSCAN', 'sin ruido')
    return f'{y}: {e}'

def fig_or(R, path):
    import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
    D = R.dropna(subset=['OR']).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(9.4, 0.4 * len(D) + 1.6), facecolor=SURF); _style(ax); ax.grid(axis='y', visible=False)
    y = np.arange(len(D))[::-1]
    for yi, (_, r) in zip(y, D.iterrows()):
        ax.plot([r.OR_ic95_bajo, r.OR_ic95_alto], [yi, yi], color=CAT[0], lw=1.6)
        ax.plot(r.OR, yi, 'o', color=CAT[0], ms=7, mec=SURF, mew=1.5)
    ax.axvline(1, color=INK2, lw=1, ls='--'); ax.set_xscale('log')
    ax.set_yticks(y); ax.set_yticklabels([_short(r) for _, r in D.iterrows()], fontsize=8, color=INK2)
    ax.set_xlabel('Odds ratio (escala log), IC 95% con EE agrupados por lección', color=INK2, fontsize=9)
    ax.set_title('Rasgo discursivo ~ cluster dominante', color=INK, fontsize=11, loc='left')
    fig.tight_layout(); fig.savefig(path, dpi=160, facecolor=SURF); plt.close(fig)

# ----------------------------------------------------------------------------------------------
# MAIN
# ----------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', required=True); ap.add_argument('--backend', default='sbert', choices=['sbert', 'lsa'])
    ap.add_argument('--years', default=None, help='CSV con columnas operacion,anio'); ap.add_argument('--out', default='resultados')
    ap.add_argument('--n_neighbors', type=int, default=10); ap.add_argument('--min_cluster_size', type=int, default=5)
    a = ap.parse_args(); os.makedirs(a.out, exist_ok=True)
    from sklearn.metrics import adjusted_rand_score as ari

    df, info = load_and_preprocess(a.csv, a.years); print('preproceso', info)
    E = embed(df, a.backend)
    U = run_umap(E, a.n_neighbors); L, prob = run_hdbscan(U, a.min_cluster_size)
    cnt = np.bincount(L[L >= 0]) if (L >= 0).any() else np.array([0]); dom = int(cnt.argmax())
    print('clusters', dict(zip(*np.unique(L, return_counts=True))), 'dominante', dom)
    Sens = sensitivity(E, base=(a.n_neighbors, a.min_cluster_size))
    # circularidad léxica: reagrupar sin los términos de los léxicos (solo tiene efecto con backend lsa; con sbert se re-embebe el texto original,
    # por lo que este control se hace excluyendo esos términos del texto solo para LSA)
    if a.backend == 'lsa':
        E2 = embed(drop_lexicon(df), 'lsa'); L2, _ = run_hdbscan(run_umap(E2, a.n_neighbors), a.min_cluster_size); ari_lex = float(ari(L, L2))
    else:
        L2, ari_lex = None, np.nan
    S = sentence_table(df)
    R, T, Sd = regressions(df, S, L, dom, use_year=df['anio'].notna().all())
    if L2 is not None and (L2 >= 0).any():
        dom2 = int(np.bincount(L2[L2 >= 0]).argmax()); R2, _, _ = regressions(df, S, L2, dom2, use_year=df['anio'].notna().all())
        R2['especificacion'] = R2['especificacion'] + ' | clusters sin términos del léxico'; R = pd.concat([R, R2[R2['especificacion'].str.contains('FE sector \\|')]], ignore_index=True)
    # NMF en el cluster dominante
    mask = (L == dom); sub = df[mask].reset_index(drop=True)
    nm = nmf_topics(sub['lemas_txt'].tolist()); from sklearn.decomposition import NMF  # noqa
    # componentes del modelo elegido (semilla 0, misma configuración) para el gráfico
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [' '.join(t for t in d.split() if t not in DOMAIN_STOP) for d in sub['lemas_txt']]
    vec = TfidfVectorizer(min_df=3, max_df=0.7, sublinear_tf=True); X = vec.fit_transform(docs)
    mdl = NMF(nm['k'], init='random', random_state=0, max_iter=2000, tol=1e-5).fit(X); Wm = mdl.transform(X); nm['comp'] = mdl.components_; nm['vocab'] = np.array(vec.get_feature_names_out())
    topic = Wm.argmax(1) + 1; ntop = [int((topic == i + 1).sum()) for i in range(nm['k'])]
    nm['top']['n_lecciones'] = ntop
    sub_map = dict(zip(sub['id'], topic)); df['cluster'] = L; df['prob_cluster'] = prob; df['subtema_nmf'] = df['id'].map(sub_map)
    # figuras
    fig_umap(E, L, dom, f'{a.out}/fig1_umap_clusters.png', a.backend); fig_sens(Sens, f'{a.out}/fig2_sensibilidad.png')
    fig_nmf(nm, Wm, f'{a.out}/fig3_subtemas_nmf.png', ntop); fig_or(R, f'{a.out}/fig4_regresiones_OR.png')
    # Excel
    val = S.groupby('seccion', group_keys=False).apply(lambda g: g.sample(min(len(g), 40), random_state=SEED)).reset_index(drop=True)
    val['prescriptivo_manual (0/1)'] = ''; val['atribucion_manual (0/1)'] = ''
    tab = df[['id', 'grupo_sector', 'subsectores', 'operaciones', 'anio', 'cluster', 'prob_cluster', 'subtema_nmf', 'texto']].copy()
    tab['subsectores'] = tab['subsectores'].apply('; '.join); tab['operaciones'] = tab['operaciones'].apply('; '.join)
    with pd.ExcelWriter(f'{a.out}/resultados_nlp_lecciones.xlsx', engine='openpyxl') as xw:
        pd.DataFrame([dict(backend=a.backend, n_lecciones=len(df), n_oraciones=len(S), n_neighbors=a.n_neighbors, min_cluster_size=a.min_cluster_size,
                           n_clusters=int(len(set(L)) - (1 if -1 in L else 0)), n_ruido=int((L == -1).sum()), cluster_dominante=dom, tam_dominante=int(cnt.max()),
                           k_nmf=nm['k'], ARI_sin_lexico=ari_lex, anio_disponible=bool(df['anio'].notna().all()), **info)]).T.rename(columns={0: 'valor'}).to_excel(xw, sheet_name='Resumen')
        tab.to_excel(xw, sheet_name='Lecciones', index=False); Sens.to_excel(xw, sheet_name='Sensibilidad_HDBSCAN', index=False)
        Sens.groupby(['n_neighbors', 'min_cluster_size']).agg(n_clusters=('n_clusters', 'mean'), pct_ruido=('pct_ruido', 'mean'), tam_mayor=('tam_mayor', 'mean'), ARI_vs_base=('ARI_vs_base', 'mean')).round(2).reset_index().to_excel(xw, sheet_name='Sensibilidad_resumen', index=False)
        nm['seleccion'].to_excel(xw, sheet_name='NMF_seleccion_k', index=False); nm['top'].to_excel(xw, sheet_name='NMF_subtemas', index=False)
        R.to_excel(xw, sheet_name='Regresiones', index=False)
        S.drop(columns=[]).to_excel(xw, sheet_name='Oraciones', index=False); val.to_excel(xw, sheet_name='Validacion_manual', index=False)
    R.to_csv(f'{a.out}/regresiones.csv', index=False); print('listo ->', a.out)
    return df, S, R, nm, Sens

if __name__ == '__main__':
    main()
