# Análisis de texto de las 80 lecciones curadas de transporte

## Cómo correrlo (en tu computadora, con acceso a Hugging Face)

```
pip install -r requirements.txt
python pipeline_lecciones.py --csv Curated-Lessons-Learned-TSP.csv --backend sbert --out resultados
# cuando tengas la tabla operación -> año (CSV con columnas: operacion,anio):
python pipeline_lecciones.py --csv Curated-Lessons-Learned-TSP.csv --backend sbert --years anios.csv --out resultados
```

Con `--backend lsa` corre sin descargar ningún modelo (es lo que se usó en la carpeta `corrida_provisional_LSA`).
Con `--years`, el año de cada lección es el de la **operación más antigua** que la cita (regla editable en `load_and_preprocess`), y se agregan las especificaciones con efectos fijos de año y de quinquenio.

## Qué hace cada etapa

1. **Preprocesamiento.** `ftfy` (mojibake) + Unicode NFC + espacios no separables y comillas/guiones tipográficos; separación Hallazgo/Recomendación; segmentación en oraciones; lematización con `simplemma` (es) y lista propia de palabras vacías. El CSV no tenía mojibake; 29 textos se modificaron solo por normalización de espacios/comillas.
2. **Embeddings.** `paraphrase-multilingual-mpnet-base-v2` (Sentence-BERT, Reimers & Gurevych 2019) sobre el texto original de cada lección. Sustituto provisional: TF-IDF de lemas (1-2 gramas) + SVD de 25 dimensiones (LSA).
3. **UMAP** (coseno, n_neighbors=10, 5 dimensiones para clusterizar; una proyección aparte de 2 dimensiones para el gráfico).
4. **HDBSCAN** (`eom`, min_cluster_size=5; -1 = ruido). El número de clusters sale de la densidad, no se impone. La configuración base se fijó antes de ver resultados; hay un barrido de n_neighbors × min_cluster_size × 5 semillas de UMAP (hoja `Sensibilidad_HDBSCAN`).
5. **NMF** sobre TF-IDF de lemas dentro del cluster dominante. k entre 2 y 8; se elige el de mayor coherencia NPMI entre los k estables (similitud entre semillas ≥ 0,85) y parsimoniosos (k ≤ n/8).
6. **Rasgos discursivos** por oración, con léxicos y reglas (ver abajo), y **regresiones logísticas** `rasgo ~ cluster dominante + sección + FE sector (+ FE año)` con errores estándar agrupados por lección; robustez a nivel lección, sin el ruido de HDBSCAN y reclusterizando sin los términos de los léxicos.

### Rasgos discursivos (definiciones operativas)

- **Prescriptivo**: la oración empieza con un infinitivo (o lo tiene tras un inciso inicial, "En la fase de diseño, considerar…") o contiene modalidad deóntica ("debe", "se recomienda", "es necesario/importante + verbo", "hay que"…).
- **Atribución de responsabilidad**: marcadores explícitos ("responsable", "a cargo de", "roles", "por parte de"…), o un déficit/capacidad adjudicado a un actor ("la baja capacidad del organismo ejecutor"), o un actor con verbo de deber/falla ("el organismo ejecutor debe…").
- **Menciona actor** (variable más amplia y secundaria): la oración nombra un actor institucional (organismo/unidad ejecutora, Banco, contratista, supervisor, ministerio…), sin que necesariamente se le atribuya algo.

Los léxicos son una primera versión y **no están validados**: la hoja `Validacion_manual` trae 80 oraciones al azar (40 por sección) con dos columnas vacías para que las codifiques y calcules precisión/recall.

## Resultados de la corrida provisional (LSA, sin año)

- **Clusters.** HDBSCAN encuentra 2 clusters: uno dominante de 51 lecciones, uno de 10 (seguridad vial, capacitación, estimación de costos) y 19 lecciones sin cluster (24 %). El barrido muestra que **la estructura es frágil**: con 80 textos, entre 0 y 12 clusters según los hiperparámetros, y el acuerdo con la configuración base cambia con la semilla de UMAP (ARI medio 0,60 en la propia configuración base). Tomarlo como una exploración, no como una tipología.
- **Subtemas NMF (k = 6) en el cluster dominante.** (1) mantenimiento y contratos de largo plazo (4 lecciones); (2) decisión, comunicación y planificación operativa (9); (3) gestión ambiental y social, supervisión (9); (4) unidades ejecutoras, capacitación y personal (10); (5) adquisiciones, plazos y previsión financiera (10); (6) criterios técnicos, diseño y calidad (9).
- **Discurso.** El 95 % de las oraciones de Recomendación y el 5 % de las de Hallazgo son prescriptivas: **el lenguaje prescriptivo lo define la sección**, no el cluster (OR ≈ 1,1; IC 0,35–3,4). La atribución explícita de responsabilidad es rara (18 de 298 oraciones, 6 %), por lo que las regresiones sobre ella son imprecisas (OR 4,7; IC 1,0–21,7). Mencionar a un actor es más frecuente en el cluster dominante (OR 4,5; IC 2,0–10,1), pero esa relación es en buena parte léxica: al reclusterizar sin las palabras de los léxicos baja a OR 3,4 y a nivel lección desaparece (OR 1,4; IC 0,4–5,0).

## Límites a tener presentes

- **Es LSA, no SBERT.** La representación provisional es léxica; los clusters de SBERT serán distintos y probablemente más semánticos. Ninguna cifra de arriba debe citarse como resultado del análisis final.
- **n = 80 lecciones** (298 oraciones): UMAP/HDBSCAN/NMF son inestables y las regresiones tienen poca potencia; los IC son anchos.
- **Circularidad**: si los léxicos comparten palabras con lo que define el cluster, la asociación es mecánica. Por eso se reporta la versión sin léxico.
- **Sector**: la columna Sector es casi constante (TRANSPORT en 71/80); se usó un agrupamiento propio del campo Subsector en 5 grupos (Vial; Urbano y transporte público; Logística y conectividad; Institucional y desarrollo productivo/social; General), con desempate por el grupo menos frecuente. Es una propuesta a revisar: hay lecciones con hasta 5 etiquetas de subsector.
- **Año**: aún no incluido; las especificaciones con FE de año se activan al pasar `--years`. Con ~100 operaciones y pocas lecciones por año, conviene mirar también la versión por quinquenio.
- La corrida con años sintéticos usada para probar el código no se reporta.
