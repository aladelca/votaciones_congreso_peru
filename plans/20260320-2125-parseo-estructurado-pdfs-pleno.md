# Parseo estructurado de datos de PDFs del Pleno del Congreso del Perú

## Goal

- Diseñar e implementar la siguiente fase del repositorio: convertir los PDFs ya descubiertos y descargados del Pleno en datos estructurados y trazables, sin depender de OCR puro ni de un único proveedor externo.

## Request Snapshot

- User request: "ahora haz el plan para comenzar a parsear los datos, qué herramientas crees que necesitamos? tal vez llamadas a openai api? o podríamos usar algun servicio de aws, no quiero confiar solamente en ocr"
- Owner or issue: `congreso-votaciones-9jz`
- Plan file: `plans/20260320-2125-parseo-estructurado-pdfs-pleno.md`
- Scope anchor: sesiones del Pleno únicamente

## Current State

- El repositorio ya resuelve la página pública del Pleno, expande el índice, genera manifiestos y descarga PDFs de forma incremental.
- El contrato actual termina en `ManifestRecord`; todavía no existe un modelo para el contenido interno del PDF.
- `README.md` declara explícitamente que el contenido de los PDFs aún no se parsea.
- Existe un corpus local suficiente para comenzar una fase de parseo con muestras reales del Pleno.
- La fase actual ya dejó artefactos importantes que esta siguiente iteración debe reutilizar:
  - `data/raw/pleno/pdfs/` como fuente primaria de documentos
  - `data/manifests/pleno_pdfs_index.jsonl` como inventario canónico
  - CLI y servicios en `src/congreso_votaciones/` como punto de entrada natural

## Local Findings

- El corpus real del Pleno es mixto, no uniforme.
- En una inspección local sobre PDFs ya descargados:
  - varios documentos parecen ser escaneos o PDFs imagen, sin capa textual confiable;
  - varios documentos recientes son mixtos, con imágenes y algo de texto nativo;
  - al menos algunos PDFs recientes parecen nativos digitales y sí exponen texto estructurable.
- Conclusión operativa:
  - un pipeline basado solo en OCR perderá precisión y encarecerá innecesariamente los documentos digitales;
  - un pipeline basado solo en extracción nativa fallará sobre escaneos y documentos híbridos;
  - la arquitectura correcta para este repositorio es híbrida y con ruteo por documento o por página.

## Desired Outcome

- Obtener datasets estructurados y auditables por sesión del Pleno, listos para análisis posteriores.
- Poder responder al menos estas preguntas con datos persistidos:
  - qué sesión corresponde a cada PDF;
  - qué congresistas asistieron;
  - qué congresistas votaron;
  - cuál fue el sentido del voto por congresista y por votación, cuando el PDF lo contenga;
  - qué partes fueron inferidas con alta confianza, cuáles con baja y de qué fuente salieron.
- Mantener trazabilidad por valor extraído:
  - documento origen
  - página origen
  - bloque o tabla origen
  - método de extracción
  - score de confianza

## Scope

### In scope

- Perfilado de PDFs del Pleno para clasificar documentos `digital`, `scanned` o `mixed`.
- Extracción base de texto, tablas y layout desde PDFs del Pleno.
- OCR como fallback selectivo, no como ruta única.
- Normalización semántica de tablas y filas parlamentarias a un esquema estable.
- Uso opcional y controlado de modelos o servicios externos para resolver casos ambiguos o de baja confianza.
- Persistencia de resultados estructurados, evidencia intermedia y métricas de calidad.
- Nuevos comandos CLI para parsear, reparsear y evaluar.
- Suite de fixtures y pruebas con muestras reales del Pleno.

### Out of scope

- Comisión Permanente.
- Explotación analítica final, dashboard o API pública.
- Fine-tuning desde la primera iteración.
- Automatización de etiquetado humano en interfaz web.
- Extracción universal de cualquier PDF del Congreso fuera del Pleno.

## Core Decision

- No confiar solamente en OCR.
- No delegar todo el parseo a un LLM.
- No depender exclusivamente de AWS Textract.
- Recomendación principal:
  - usar extracción local determinista como camino base;
  - usar OCR solo cuando el perfil del PDF o la confianza lo exijan;
  - usar OpenAI API para normalización semántica y resolución de ambigüedades bajo esquema estricto;
  - mantener AWS Textract como backend opcional para documentos escaneados difíciles o si se necesita operación administrada en AWS.

## Recommended Stack

### Base local y determinista

- `PyMuPDF` (`fitz`)
  - para inspección rápida de páginas, texto, bloques, imágenes embebidas y geometría.
- `pdfplumber`
  - para extracción de texto con coordenadas y tablas simples.
- `pypdf`
  - para metadata básica y utilidades livianas.
- `pandas`
  - para normalizar tablas y filas extraídas.
- `rapidfuzz`
  - para reconciliar encabezados variables, nombres de congresistas y etiquetas de voto.
- `pydantic`
  - para contratos estrictos de salida y validación de parseos.

### OCR local

- `ocrmypdf`
  - para generar una capa OCR reutilizable sobre PDFs escaneados.
- `tesseract`
  - motor OCR base, preferiblemente con paquetes `spa` y `eng`.
- `unstructured` no es prioridad inicial
  - agrega complejidad temprano y no sustituye bien el control fino que aquí necesitamos.

### Tablas y layout

- `camelot`
  - útil para PDFs digitales con líneas o estructura tabular reconocible.
- `tabula-py`
  - backend alternativo a validar si `camelot` falla en ciertos PDFs.
- Regla recomendada:
  - empezar con `pdfplumber` + `PyMuPDF`;
  - introducir `camelot` solo en el subflujo de PDFs digitales donde aporte señal real.

### Normalización con LLM

- OpenAI Responses API
  - usarla solo después de la extracción base, nunca como primer paso ciego.
- Casos en los que sí agrega valor:
  - convertir tablas o bloques ruidosos a JSON estricto;
  - reconciliar encabezados variables;
  - vincular secciones como asistencia, votaciones y resultados a un esquema común;
  - producir una explicación estructurada de por qué un parseo quedó con baja confianza.
- Casos en los que no conviene usarla:
  - OCR primario de miles de páginas si el texto ya existe;
  - parseo sin esquema ni validación;
  - extracción masiva sin evaluación previa de costos.

### Servicio administrado opcional

- AWS Textract
  - encaja como backend opcional para PDFs escaneados, formularios y tablas difíciles.
- Casos donde sí conviene:
  - lotes grandes de escaneos de baja calidad;
  - necesidad de layout administrado con `TABLES`, `FORMS`, `QUERIES` y `LAYOUT`;
  - operación alineada a una arquitectura ya montada en AWS.
- Casos donde no conviene como primera decisión:
  - cuando el corpus tiene suficientes PDFs digitales para resolverse localmente;
  - cuando se quiere mantener costos bajos y reproducibilidad offline;
  - cuando todavía no existe un set de evaluación que justifique el gasto.

## Why This Recommendation

- El repositorio ya tiene una base offline y reproducible; conviene preservarla.
- El corpus es mixto; por eso un solo backend no será suficiente.
- La parte difícil del problema no es solo leer caracteres:
  - es identificar bloques parlamentarios;
  - distinguir tablas de asistencia contra tablas de votación;
  - normalizar nombres, encabezados y sentidos de voto;
  - detectar cuándo un documento fue parseado con suficiente confianza.
- OpenAI API es más valiosa en la capa de normalización semántica y control estructurado que en la capa de OCR puro.
- AWS Textract es más valioso como fallback operacional para documentos escaneados complejos que como reemplazo total del pipeline.

## External References

- OpenAI file inputs / PDF inputs:
  - `https://platform.openai.com/docs/guides/pdf-files`
- OpenAI structured outputs:
  - `https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses&lang=python`
- OpenAI background mode:
  - `https://platform.openai.com/docs/guides/background`
- OpenAI models overview:
  - `https://developers.openai.com/api/docs/models`
- AWS Textract document analysis:
  - `https://docs.aws.amazon.com/textract/latest/dg/how-it-works-analyzing.html`

## Target Data Model

### Dataset layers

- `document`
  - un PDF del Pleno ya descubierto y descargado
- `page_profile`
  - características de cada página para ruteo y debugging
- `raw_block`
  - bloques de texto, tablas o regiones detectadas
- `session_parse`
  - salida estructurada principal del documento
- `attendance_row`
  - presencia o ausencia de un congresista
- `vote_event`
  - una votación identificable dentro del documento
- `vote_row`
  - voto individual por congresista dentro de una votación
- `parse_audit`
  - evidencia y métricas por documento

### Canonical fields

- `document_id`
- `record_id`
- `storage_relpath`
- `session_date_iso`
- `periodo_parlamentario`
- `periodo_anual`
- `legislatura`
- `document_kind`
- `source_title`
- `parse_status`
- `parse_method`
- `parse_confidence`
- `page_count`
- `ocr_applied`
- `llm_applied`
- `textract_applied`
- `parser_version`
- `parsed_at`

### Session-level fields

- `session_name`
- `session_type`
- `session_number`
- `session_start_time`
- `session_end_time`
- `is_provisional`
- `is_official`

### Attendance-level fields

- `legislator_name_raw`
- `legislator_name_normalized`
- `attendance_status_raw`
- `attendance_status_normalized`
- `attendance_confidence`
- `source_page`
- `source_bbox`

### Vote-level fields

- `vote_id`
- `vote_title`
- `vote_subject`
- `vote_result_summary`
- `yes_count`
- `no_count`
- `abstention_count`
- `other_count`
- `source_page_start`
- `source_page_end`

### Vote row fields

- `legislator_name_raw`
- `legislator_name_normalized`
- `vote_value_raw`
- `vote_value_normalized`
- `vote_confidence`
- `source_page`
- `source_bbox`

## Confidence Contract

- Cada valor estructurado debe llevar al menos una de estas procedencias:
  - `native_text`
  - `ocr_text`
  - `table_extraction`
  - `llm_normalization`
  - `textract`
- Cada documento debe exponer:
  - `document_profile_confidence`
  - `extraction_confidence`
  - `normalization_confidence`
  - `overall_parse_confidence`
- Reglas iniciales:
  - si un PDF tiene texto nativo consistente, evitar OCR;
  - si una página tiene baja densidad textual y alta presencia de imagen, encolar OCR o Textract;
  - si la normalización semántica devuelve inconsistencias contra el esquema, marcar `needs_review`;
  - si no cierran conteos agregados versus filas individuales, degradar confianza.

## Pipeline Architecture

### Step 1. Profile document

- Inspeccionar cada PDF antes de parsear.
- Medir por documento y por página:
  - cantidad de texto extraído
  - cantidad de imágenes
  - proporción de caracteres válidos
  - señales de tablas
  - rotación u orientación anómala
- Clasificar:
  - `digital`
  - `scanned`
  - `mixed`

### Step 2. Route extraction path

- `digital`
  - intentar texto nativo y tablas primero.
- `scanned`
  - OCR local primero; si cae por debajo del umbral, enviar a backend alternativo.
- `mixed`
  - rutear por página, no por documento completo.

### Step 3. Extract raw evidence

- Extraer:
  - texto por bloque
  - tablas candidatas
  - coordenadas
  - imágenes diagnósticas opcionales de regiones problemáticas
- Persistir evidencia intermedia para debugging en `data/processed/pleno/intermediate/`.

### Step 4. Segment parliamentary sections

- Detectar y separar secciones del PDF:
  - encabezado de sesión
  - asistencia
  - votaciones
  - resumen de resultados
- Esta capa debe ser principalmente determinista.

### Step 5. Normalize to schema

- Aplicar reglas y diccionarios para:
  - nombres de columnas
  - valores de asistencia
  - valores de voto
  - nombres de congresistas
- Si el parseo queda ambiguo, pasar el bloque ya reducido a OpenAI para:
  - convertir a JSON schema;
  - explicar incertidumbre;
  - devolver solo campos permitidos.

### Step 6. Validate and score

- Validar con `pydantic` y reglas de negocio.
- Comparar:
  - totales de voto frente a filas individuales;
  - cantidad de asistentes frente a totales declarados;
  - encabezados frente a metadatos del manifiesto.
- Clasificar salida:
  - `parsed`
  - `parsed_with_warnings`
  - `needs_review`
  - `failed`

## OpenAI API Plan

### Recommended use

- Sí, vale la pena contemplar llamadas a OpenAI API, pero no como OCR universal.
- La usaría para tres tareas concretas:
  - normalización estructurada de bloques ya extraídos;
  - resolución de encabezados o tablas ambiguas;
  - control de calidad semántico cuando los checks deterministas no basten.

### Concrete design

- Endpoint:
  - Responses API
- Input:
  - preferir texto o bloques ya extraídos;
  - usar PDF completo solo en casos acotados y evaluados.
- Output:
  - siempre con structured outputs y schema explícito.
- Mode:
  - síncrono para pruebas y documentos chicos;
  - `background=true` para lotes costosos o tareas largas.

### Guardrails

- No enviar el corpus completo sin deduplicar o chunkear.
- No usar salidas libres en lenguaje natural como contrato de persistencia.
- No aceptar parseos del modelo si rompen el schema o contradicen validaciones básicas.
- Registrar `model`, `response_id`, `prompt_version` y costo estimado por documento.

## AWS Textract Plan

### Recommended use

- Sí, conviene evaluarlo, pero como backend opcional y no como dependencia central en la primera iteración.
- Lo priorizaría si:
  - los escaneos son una fracción alta del corpus;
  - OCR local no llega al umbral de calidad;
  - se requiere una operación batch administrada en AWS.

### Concrete design

- Backend enchufable:
  - `local_ocr`
  - `aws_textract`
- Para Textract, comenzar solo con:
  - `TABLES`
  - `LAYOUT`
  - `QUERIES` en pruebas dirigidas
- Evitar desde el día 1:
  - sobreingeniería con demasiados feature types;
  - dependencia operacional si aún no hay benchmark comparativo.

## File Plan

| Path | Action | Details |
| --- | --- | --- |
| `plans/20260320-2125-parseo-estructurado-pdfs-pleno.md` | create | Plan detallado y canónico de la fase de parseo |
| `README.md` | modify | Añadir una sección corta con el roadmap del parseo y enlace al plan cuando la implementación arranque |
| `pyproject.toml` | modify | Agregar dependencias del pipeline de parseo y extras opcionales |
| `src/congreso_votaciones/models.py` | modify | Extender o complementar modelos con salidas de parseo estructurado |
| `src/congreso_votaciones/parse_pdf.py` | create | Orquestador principal del pipeline por documento |
| `src/congreso_votaciones/pdf_profile.py` | create | Perfilado de PDF por documento y página |
| `src/congreso_votaciones/extract_text.py` | create | Extracción nativa de texto y bloques |
| `src/congreso_votaciones/extract_tables.py` | create | Extracción tabular para PDFs digitales |
| `src/congreso_votaciones/ocr.py` | create | Integración con `ocrmypdf` y Tesseract |
| `src/congreso_votaciones/normalize_rules.py` | create | Reglas deterministas de normalización |
| `src/congreso_votaciones/normalize_llm.py` | create | Integración opcional con OpenAI Responses API |
| `src/congreso_votaciones/textract.py` | create | Integración opcional con AWS Textract |
| `src/congreso_votaciones/validation.py` | create | Validaciones de consistencia y scoring |
| `src/congreso_votaciones/parse_store.py` | create | Persistencia de datasets estructurados y auditoría |
| `src/congreso_votaciones/services.py` | modify | Exponer servicios de parseo reutilizables por CLI |
| `src/congreso_votaciones/cli.py` | modify | Agregar comandos `profile-pdf`, `parse-pdf`, `parse-pleno` y `evaluate-parse` |
| `docs/runbook-parse-pleno.md` | create | Explicar operación del pipeline de parseo y fallback de backends |
| `tests/fixtures/pdfs/` | create | Muestras mínimas digitales, escaneadas y mixtas |
| `tests/test_pdf_profile.py` | create | Cobertura del ruteo por tipo de PDF |
| `tests/test_extract_text.py` | create | Cobertura de extracción nativa |
| `tests/test_extract_tables.py` | create | Cobertura de tablas en PDFs digitales |
| `tests/test_ocr.py` | create | Cobertura de OCR y criterios de fallback |
| `tests/test_normalize_rules.py` | create | Cobertura de normalización determinista |
| `tests/test_normalize_llm.py` | create | Cobertura de contratos y mocking de OpenAI |
| `tests/test_validation.py` | create | Cobertura de score y estados finales |
| `tests/test_parse_pdf.py` | create | Cobertura end-to-end offline del pipeline |

## CLI Connections

- `profile-pdf`
  - recibe `record_id` o `--pdf-path`
  - carga el PDF local
  - ejecuta `pdf_profile.profile_pdf`
  - imprime clasificación, señales y ruta sugerida
- `parse-pdf`
  - recibe `record_id` o `--pdf-path`
  - ejecuta el pipeline completo sobre un documento
  - persiste evidencia y salida estructurada
- `parse-pleno`
  - carga el manifiesto
  - selecciona candidatos
  - ejecuta parseo incremental con concurrencia acotada
  - respeta flags como `--limit`, `--retry-failed`, `--use-openai`, `--use-textract`
- `evaluate-parse`
  - corre sobre un set curado y calcula métricas

## Storage Layout

```text
data/
├── raw/
│   └── pleno/
│       └── pdfs/
├── processed/
│   └── pleno/
│       ├── intermediate/
│       ├── parsed/
│       └── evaluation/
├── manifests/
└── logs/
```

### Proposed outputs

- `data/processed/pleno/intermediate/<record_id>/profile.json`
- `data/processed/pleno/intermediate/<record_id>/blocks.jsonl`
- `data/processed/pleno/intermediate/<record_id>/tables.jsonl`
- `data/processed/pleno/intermediate/<record_id>/ocr.jsonl`
- `data/processed/pleno/parsed/session_parses.jsonl`
- `data/processed/pleno/parsed/attendance_rows.jsonl`
- `data/processed/pleno/parsed/vote_events.jsonl`
- `data/processed/pleno/parsed/vote_rows.jsonl`
- `data/processed/pleno/parsed/parse_audit.jsonl`

## Implementation Phases

### Phase 1. Gold set y contrato de salida

- Seleccionar un set curado de entre `20` y `30` PDFs del Pleno:
  - digitales
  - escaneados
  - mixtos
  - antiguos y recientes
- Etiquetar manualmente la verdad mínima esperada:
  - metadatos de sesión
  - presencia de tabla de asistencia
  - presencia de votaciones
  - uno o dos ejemplos completos de filas por documento
- Definir schemas `pydantic` y contratos JSONL de salida.

### Phase 2. Perfilado y extracción nativa

- Implementar el clasificador `digital/scanned/mixed`.
- Implementar extracción nativa base.
- Medir cobertura sobre el gold set sin OCR.

### Phase 3. OCR fallback

- Integrar `ocrmypdf` y Tesseract.
- Aplicar OCR solo a documentos o páginas donde el perfil lo indique.
- Registrar mejora versus baseline.

### Phase 4. Normalización determinista

- Implementar diccionarios y reglas para votos, asistencia y nombres.
- Construir validaciones de consistencia.

### Phase 5. Integración OpenAI opcional

- Diseñar prompts de normalización estructurada.
- Limitar input a bloques ya segmentados.
- Usar structured outputs y mocks en tests.
- Medir costo, latencia y mejora real.

### Phase 6. Backend AWS Textract opcional

- Implementar adaptador detrás de interfaz común.
- Probar solo sobre subconjunto difícil del gold set.
- Decidir si queda activado por defecto o no.

### Phase 7. Parsing masivo incremental

- Parsear el corpus completo por lotes.
- Persistir estados y reintentos.
- Generar reportes de cobertura y revisión manual.

## Evaluation Plan

- Métricas mínimas:
  - `document_classification_accuracy`
  - `session_metadata_accuracy`
  - `attendance_row_precision`
  - `attendance_row_recall`
  - `vote_row_precision`
  - `vote_row_recall`
  - `table_detection_recall`
  - `documents_needing_review_rate`
  - costo promedio por documento
  - tiempo promedio por documento
- Umbrales iniciales recomendados para pasar a rollout amplio:
  - `>= 0.95` en clasificación `digital/scanned/mixed`
  - `>= 0.90` en metadatos de sesión
  - `>= 0.90` en `precision` de filas de asistencia
  - `>= 0.85` en `recall` de filas de asistencia
  - `>= 0.90` en `precision` de votos
  - `>= 0.80` en `recall` de votos
  - `<= 0.15` en `needs_review_rate` sobre el gold set

## Testing Strategy

- Unit tests para perfilado, extracción y normalización.
- Integration tests offline con fixtures PDF reales minimizadas.
- Contract tests de schemas JSONL.
- Mocking obligatorio para OpenAI y AWS en CI.
- Smoke tests opcionales contra APIs remotas solo bajo marker explícito.

## Validation Commands

- `uv run ruff format --check pyproject.toml src tests`
- `uv run ruff check pyproject.toml src tests`
- `uv run mypy src`
- `uv run pytest tests -m 'not network'`
- `uv run pytest tests/test_parse_pdf.py -m 'not network'`

## Risks

- PDFs muy heterogéneos entre legislaturas.
- Tablas rotas o reconstruidas como texto corrido.
- Nombres de congresistas con variaciones ortográficas.
- Costos de OpenAI o Textract si se usan sin ruteo previo.
- Falsos positivos de OCR sobre sellos, firmas o marcas gráficas.
- Tentación de aceptar parseos del modelo sin validación determinista.

## Non-Goals and Guardrails

- No mover el repo a una arquitectura cloud-first en esta fase.
- No agregar dependencia obligatoria en OpenAI o AWS para el camino básico.
- No esconder la incertidumbre: todo parseo debe exponer confianza y procedencia.
- No mezclar persistencia final con bloques intermedios sin versionado.

## Recommended First Implementation Slice

- Implementar primero:
  - `pdf_profile.py`
  - `extract_text.py`
  - schemas base de `session_parse`, `attendance_row` y `vote_row`
  - `parse-pdf` sobre un único documento
  - evaluación manual sobre `5` a `10` PDFs representativos
- Dejar OpenAI y Textract para la segunda ola, una vez medido el baseline local.

## Exit Criteria

- Existe un pipeline reproducible que parsea una muestra representativa del Pleno.
- La salida estructurada queda persistida en JSONL con schema estable.
- Cada documento queda clasificado y auditado.
- La decisión sobre activar OpenAI o Textract se toma con benchmark, no por intuición.
- El repositorio puede escalar del manifiesto de PDFs al dataset estructurado sin perder trazabilidad.
