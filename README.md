# Grafo de conocimiento: lecciones aprendidas de transporte (INE/TSP)

Prototipo de grafo de conocimiento construido a partir de las 80 lecciones aprendidas curadas de transporte del BID (INE/TSP), cruzado con el mapa de evidencia de transporte de 3ie y con un análisis exploratorio de texto (NLP). Repositorio **privado**: el contenido son lecciones operativas internas del Banco, no datos públicos.

> Este es un prototipo de exploración, no una herramienta validada. Ver las advertencias en `docs/` y en la propia nota metodológica antes de citar cualquier número.

## Cómo ver el grafo

Los archivos de `grafo/` son HTML autocontenidos: se descargan y se abren directamente en el navegador, sin instalar nada.

- **`grafo/grafo_lecciones_transporte.html`** — grafo completo de las 80 lecciones, con la capa de evidencia de 3ie y la capa de análisis de texto (provisional).
- **`grafo/grafo_caminos_rurales.html`** — el mismo grafo filtrado al subsector de caminos rurales.
- Los `.xlsx` correspondientes traen las mismas tablas en formato de planilla (nodos, aristas, matrices de cruce, evidencia).

Para publicarlo como página web con un link (GitHub Pages), ver la sección **Publicar con GitHub Pages** más abajo.

## Estructura del repositorio

```
grafo/                    El grafo terminado: HTML interactivo + Excel (general y caminos rurales)
datos/                    Datos fuente: las 80 lecciones curadas y el mapa de evidencia de 3ie (711 estudios)
scripts/                  Scripts que construyen el grafo a partir de los datos (ver abajo)
analisis_texto/           Pipeline de NLP (embeddings, clustering, NMF, regresiones) y su corrida provisional
docs/                      Nota metodológica y sets de preguntas y respuestas para evaluar búsqueda híbrida
capturas/                 Capturas de pantalla del grafo, para este README
```

### `scripts/` — cómo se construyó el grafo

Los scripts documentan el proceso tal como se corrió durante la sesión de trabajo; no son un pipeline empaquetado de un solo comando (tienen rutas relativas a una carpeta de trabajo local). El orden es:

1. `egm_load.py` + `egm_tag.py` — cargan el mapa de evidencia de 3ie y clasifican los 711 estudios por tema, resultado, país y diseño con reglas de palabras clave (la exportación de 3ie no trae esa codificación).
2. `build.py` — lee `datos/Curated-Lessons-Learned-TSP.csv`, etiqueta cada lección (problema, consecuencia, práctica, etapa, actor) y arma los nodos y aristas base del grafo.
3. `add_evidence.py` — cruza los subsectores de las lecciones con los temas del mapa de evidencia.
4. `add_nlp.py` / `add_nlp_excel.py` — agregan al grafo los clusters y subtemas del análisis de texto (`analisis_texto/`).
5. `build_html.py` / `filtered.py` — usan `template.html` para generar los HTML finales (general y caminos rurales) y los Excel.

Para volver a correrlos hace falta reconstruir las rutas de trabajo (una carpeta `out/` con los JSON intermedios, la librería vis-network vendorizada, etc.). Se incluyen como documentación del método, no como un pipeline listo para ejecutar.

### `analisis_texto/` — análisis de lenguaje natural

`pipeline_lecciones.py` sí es un script de línea de comandos autocontenido:

```
pip install -r requirements.txt
python pipeline_lecciones.py --csv ../datos/Curated-Lessons-Learned-TSP.csv --backend sbert --out resultados
```

Hace preprocesamiento (corrección de encoding, lematización), embeddings semánticos multilingües (Sentence-BERT, Reimers & Gurevych 2019), reducción de dimensionalidad con UMAP, clustering por densidad con HDBSCAN, subtemas con NMF y un análisis de rasgos discursivos con regresiones logísticas.

`corrida_provisional_LSA/` es una corrida ya hecha con un sustituto léxico (TF-IDF + SVD) en lugar de SBERT, porque el entorno donde se generó no tenía acceso a Hugging Face. Está marcada como provisional en todos los archivos; los resultados con SBERT pueden diferir.

### `docs/`

- **Nota metodológica** (`.docx`): qué es el grafo, de dónde sale cada dato, cómo se construyó, cómo leerlo, qué tener en cuenta y cómo validarlo, más una sección sobre estrategia de recuperación (RAG vs. grafo) para un eventual uso a escala del Banco.
- **Sets de preguntas y respuestas** (`.xlsx` y `.jsonl`): preguntas factuales y de razonamiento, y preguntas centradas en metadatos, con respuesta esperada y conjunto de referencia, pensadas para evaluar una búsqueda híbrida (léxica + vectorial + grafo) sobre este corpus.

## Publicar con GitHub Pages (opcional)

Si en algún momento el repo pasa a público y se quiere un link directo al grafo (sin que la otra persona tenga que descargar el HTML):

1. En GitHub: **Settings → Pages → Source** → rama `main`, carpeta `/grafo` (o `/` moviendo antes el HTML a la raíz).
2. GitHub genera un link tipo `https://<usuario>.github.io/<repo>/grafo_lecciones_transporte.html`.

GitHub Pages no funciona en un repositorio privado salvo con un plan de pago (GitHub Pro/Team/Enterprise); en un repo privado gratuito el link no es accesible para otras personas.

## Advertencias

Este prototipo tiene limitaciones que se detallan en la nota metodológica (`docs/`): es un corpus chico (80 lecciones), las etiquetas de problema/práctica/etapa/actor son un vocabulario propuesto sin validar por especialistas, el subsector es una etiqueta heredada de las operaciones (no siempre del contenido de la lección), la clasificación de los 711 estudios de evidencia es aproximada, y la capa de análisis de texto usa una representación léxica provisional en lugar de embeddings semánticos. No citar cifras de este prototipo como definitivas sin esa validación.
