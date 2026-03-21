# Descarga masiva e idempotente de PDFs de sesiones del Pleno del Congreso del Perú

## Goal

- Implementar la primera capacidad operativa del repositorio para descubrir, indexar y descargar de forma incremental todos los PDFs publicados en `Asistencia y Votaciones a las Sesiones del Pleno`, dejando un manifiesto reproducible y trazable para etapas posteriores de extracción de contenido.

## Request Snapshot

- User request: "revisa el plan existente, modificalo para que sea lo mas detallado posible" y luego "centrate en las sesiones del pleno"
- Owner or issue: `None`
- Plan file: `plans/20260320-2038-descarga-masiva-pdfs-pleno.md`
- Legacy plan reviewed: `PLAN_DESCARGA_PDFS.md`

## Current State

- El bootstrap inicial ya existe en `pyproject.toml`, `README.md`, `src/congreso_votaciones/` y `tests/`.
- El CLI actual expone `discover-pleno`, `download-pleno` y `sync-pleno`, cableados vía `src/congreso_votaciones/services.py`.
- El proyecto ya genera manifiestos `csv` y `jsonl`, descarga PDFs válidos y guarda snapshots HTML del Pleno.
- Existen fixtures reales del HTML público y de la vista expandida en `tests/fixtures/`.
- Validación actual confirmada:
  - `.venv/bin/ruff format --check pyproject.toml src tests`
  - `.venv/bin/ruff check pyproject.toml src tests`
  - `.venv/bin/mypy src`
  - `.venv/bin/pytest tests -m 'not network'`
- Smoke test confirmado:
  - `discover-pleno --limit 3` genera manifiesto real
  - `download-pleno --limit 1` descarga un PDF real sobre `/tmp/congreso-votaciones-smoke`
- La brecha restante de esta iteración es operativa, no de bootstrap:
  - persistir logging legible para ejecución CLI
  - documentar el comportamiento actual en un runbook
  - hacer explícito el comportamiento de cache HTML controlado por `--refresh-html`
- `bd` no está operativo en este repo ahora mismo porque el servidor Dolt no acepta conexiones; no bloquea el código, pero sí el tracking por beads.

## Findings

- La página pública del Pleno sigue respondiendo `200` y contiene un `iframe` con `src="https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion"`.
- El `iframe` también responde `200` y expone enlaces `ExpandView` y `CollapseView`; no hace falta automatización con navegador como camino principal.
- La vista expandida `?OpenForm&ExpandView&Seq=1` sigue devolviendo el árbol completo en una sola respuesta HTML.
- En una verificación en vivo realizada el `2026-03-20`, la vista expandida devolvió `925` enlaces PDF detectables por el patrón `javascript:openWindow('Apleno/.../$FILE/...pdf')`.
- En la fixture actual descargada por CLI y parseada offline, el índice produce `933` registros. Esa diferencia frente al conteo regex anterior confirma que el runbook debe documentar el método de conteo usado en cada validación.
- Un PDF real del Pleno respondió `200` con `content-type: application/pdf` y `content-length` válido, así que el flujo HTTP directo está vigente.
- La estructura jerárquica visible en el HTML es consistente con:
  - `Periodo Parlamentario`
  - `Período Anual de Sesiones`
  - `Legislatura`
  - filas documento con fecha y título
- En el HTML actual aparecen variantes reales que el parser debe soportar:
  - títulos `Asistencia` y `Asistencias y votaciones`
  - etiquetas `OFICIAL` y `PROVISIONAL`
  - sesiones `solemne`, `extraordinaria` y `vespertina`
  - más de un PDF para una misma fecha
  - nombres de archivo con tildes, guiones, guiones bajos y capitalización inconsistente
- La página fuente ya está centrada en Pleno; este feature no necesita contemplar Comisión Permanente ni un scraper genérico multipágina.

## Scope

### In scope

- Bootstrap del proyecto Python para este caso de uso.
- Descubrimiento de la página pública del Pleno y resolución dinámica del `iframe`.
- Descarga del HTML expandido del Pleno.
- Parseo del índice jerárquico y extracción de todos los enlaces PDF del Pleno.
- Normalización mínima de metadatos para cada documento.
- Descarga idempotente de todos los PDFs del Pleno, incluyendo documentos `oficial` y `provisional`.
- Generación de manifiestos `csv` y `jsonl`.
- CLI para `discover`, `download` y `sync` enfocada solo en Pleno.
- Conexiones CLI explícitas entre comandos, servicios internos y artefactos en disco para que el flujo operativo no quede implícito.
- Logging persistente del comportamiento CLI y runbook operativo del estado actual.
- Tests unitarios e integración offline con fixtures HTML.
- Validaciones con `ruff`, `mypy` y `pytest`.

### Out of scope

- Comisión Permanente.
- OCR, parsing interno del PDF, extracción tabular o estructuración de votos por congresista.
- API, dashboard o base de datos analítica.
- Generalización del scraper a otros módulos del portal del Congreso.
- Eliminación automática de PDFs locales si desaparecen del sitio remoto.
- Deducción de cuál PDF reemplaza semánticamente a otro entre versiones `provisional` y `oficial`; en esta fase ambos se conservan y se etiquetan.
- Dependencia obligatoria en Playwright o Selenium para la ruta principal.

## Resolved Decisions

- Fuente objetivo: solo `Asistencia y Votaciones a las Sesiones del Pleno`.
- Estrategia principal: HTTP directo + parser HTML; navegador solo como fallback futuro si el HTML deja de ser accesible por `GET`.
- Regla de negocio para documentos: descargar todos los PDFs publicados por la fuente del Pleno y clasificar `is_provisional` / `is_official` en el manifiesto.
- Identificador estable: no usar solo fecha; derivar `record_id` desde `pdf_relative_path`.
- Runner del proyecto: adoptar `uv` y consolidar `ruff`, `mypy` y `pytest` dentro de `pyproject.toml`.
- El wiring CLI debe quedar explícito: `cli.py` orquesta argumentos, invoca servicios de `fetch`, `parse_index`, `manifest` y `download`, y devuelve códigos de salida coherentes para uso por terminal o cron.

## File Plan

| Path | Action | Details |
| --- | --- | --- |
| `plans/20260320-2038-descarga-masiva-pdfs-pleno.md` | create | Plan detallado y canónico para la implementación del feature |
| `PLAN_DESCARGA_PDFS.md` | modify | Convertir el documento legado en puntero al plan canónico en `/plans` |
| `.gitignore` | modify | Ignorar artefactos de descarga y ejecución como `data/raw/`, `data/manifests/`, `data/logs/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/` |
| `README.md` | create | Documentar el objetivo del repo, bootstrap, comandos CLI y layout de datos para Pleno |
| `pyproject.toml` | create | Declarar proyecto, dependencias, `project.scripts`, configuración de `ruff`, `mypy` y `pytest` |
| `data/.gitignore` | create | Mantener la estructura `data/` sin versionar PDFs, snapshots HTML, manifiestos ni logs |
| `src/congreso_votaciones/__init__.py` | create | Marcar el paquete y exponer versión si se define en el bootstrap |
| `src/congreso_votaciones/config.py` | create | Definir `Settings` con rutas, timeouts, concurrencia, retries y headers HTTP |
| `src/congreso_votaciones/models.py` | create | Definir modelos tipados como `PlenoPdfRecord`, `ManifestRecord` y `DownloadOutcome` |
| `src/congreso_votaciones/fetch.py` | create | Implementar `fetch_public_page`, `extract_iframe_url`, `build_expand_view_url`, `fetch_expand_view_html` y `download_pdf_bytes` |
| `src/congreso_votaciones/parse_index.py` | create | Implementar el parser del árbol Domino/NSF y helpers de normalización (`normalize_date`, `classify_document_type`, `classify_session_type`) |
| `src/congreso_votaciones/manifest.py` | create | Implementar `load_manifest`, `merge_discovery_with_manifest`, `write_manifest_csv`, `write_manifest_jsonl` |
| `src/congreso_votaciones/download.py` | create | Resolver almacenamiento, descargar con concurrencia acotada, validar firma PDF y calcular `sha256` |
| `src/congreso_votaciones/cli.py` | create | Exponer comandos `discover-pleno`, `download-pleno` y `sync-pleno` |
| `src/congreso_votaciones/services.py` | create | Centralizar las conexiones CLI entre discovery, manifiesto y descarga para no duplicar wiring en cada comando |
| `src/congreso_votaciones/logging_utils.py` | create | Registrar eventos operativos de discovery, download y sync en `data/logs/pleno_sync.log` |
| `tests/fixtures/pleno_public_page.html` | create | Snapshot mínimo de la página pública con el `iframe` real |
| `tests/fixtures/pleno_index_expanded.html` | create | Snapshot real del HTML expandido para probar el parser offline |
| `tests/test_fetch.py` | create | Cubrir extracción del `iframe`, construcción de `expand_view_url` y manejo de errores HTTP |
| `tests/test_parse_index.py` | create | Cubrir jerarquía, fechas, clasificación de documentos y duplicados por fecha |
| `tests/test_manifest.py` | create | Cubrir `record_id`, merge incremental e idempotencia del manifiesto |
| `tests/test_download.py` | create | Cubrir naming en disco, validación `%PDF`, reintentos y detección de archivo corrupto |
| `tests/test_services.py` | create | Cubrir cache HTML, persistencia de manifiesto y escritura de logs |
| `docs/runbook-pleno-cli.md` | create | Explicar comportamiento actual, artefactos, comandos, logs, fallos comunes y límites conocidos |

## Data and Contract Changes

- URL pública base:
  - `https://www.congreso.gob.pe/labor-legislativa/asistencias-votaciones-y-descuentos-por-inasistencias/asistencia-y-votaciones-a-las-sesiones-del-pleno/`
- URL del `iframe` a resolver dinámicamente:
  - `https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion`
- URL expandida a derivar desde el `iframe`:
  - `https://www2.congreso.gob.pe/Sicr/RelatAgenda/PlenoComiPerm20112016.nsf/new_asistenciavotacion?OpenForm&ExpandView&Seq=1`
- Patrón de documento a soportar:
  - `<A HREF=javascript:openWindow('Apleno/.../$FILE/archivo.pdf')>`
- Directorios de salida propuestos:
  - `data/raw/pleno/html/public_page.html`
  - `data/raw/pleno/html/expanded_view.html`
  - `data/raw/pleno/pdfs/<periodo_parlamentario_slug>/<session_date_iso>__<record_id>.pdf`
  - `data/manifests/pleno_pdfs_index.csv`
  - `data/manifests/pleno_pdfs_index.jsonl`
  - `data/logs/pleno_sync.log`
- `record_id` recomendado:
  - `sha1(pdf_relative_path.lower())[:16]`
- Campos mínimos de `PlenoPdfRecord` antes de descargar:
  - `record_id`
  - `source_page_url`
  - `iframe_url`
  - `expand_view_url`
  - `periodo_parlamentario`
  - `periodo_anual`
  - `legislatura`
  - `session_date_raw`
  - `session_date_iso`
  - `source_title`
  - `document_type`
  - `session_type`
  - `is_provisional`
  - `is_official`
  - `pdf_relative_path`
  - `pdf_url`
  - `filename_original`
- Campos adicionales de `ManifestRecord` tras la descarga:
  - `storage_relpath`
  - `download_status`
  - `http_status`
  - `content_type`
  - `content_length`
  - `sha256`
  - `downloaded_at`
  - `error_message`
- Contrato de clasificación:
  - `document_type = asistencia` si el título no menciona `votación` o `votaciones`
  - `document_type = asistencia_y_votaciones` si el título sí menciona `votación` o `votaciones`
  - `session_type = solemne` si el título contiene `solemne`
  - `session_type = extraordinaria` si el título contiene `extraordinaria`
  - `session_type = vespertina` si el título contiene `vespertina` o `nocturna`
  - `session_type = ordinaria` en el resto de casos
  - `is_provisional = true` si el título o el nombre del archivo contiene `PROVISIONAL`
  - `is_official = true` si el título o el nombre del archivo contiene `OFICIAL`
- Contrato CLI propuesto:
  - `uv run congreso-votaciones discover-pleno`
  - `uv run congreso-votaciones download-pleno`
  - `uv run congreso-votaciones sync-pleno`
- Conexiones CLI requeridas:
  - `discover-pleno` -> `fetch_public_page` -> `extract_iframe_url` -> `build_expand_view_url` -> `fetch_expand_view_html` -> `parse_pleno_index` -> `merge_discovery_with_manifest` -> `write_manifest_csv/jsonl`
  - `download-pleno` -> `load_manifest` -> `select_download_candidates` -> `download_records` -> `write_manifest_csv/jsonl`
  - `sync-pleno` -> reutiliza el flujo de `discover-pleno` y luego encadena `download-pleno` sin duplicar lógica de CLI
- Códigos de salida CLI recomendados:
  - `0` ejecución correcta
  - `1` error operativo recuperable o fallo parcial con descargas fallidas
  - `2` error de configuración o argumentos inválidos
- Flags iniciales recomendados:
  - `--output-root`
  - `--limit`
  - `--max-concurrency`
  - `--retry-failed`
  - `--refresh-html`
- Semántica operativa requerida para `--refresh-html`:
  - si `false` y existen snapshots HTML locales válidos, `discover-pleno` puede reutilizarlos;
  - si `true`, debe forzar redescarga de página pública e índice expandido antes de parsear.

## Implementation Steps

1. Bootstrap del proyecto

- Crear `pyproject.toml` con `requires-python >= 3.11`.
- Definir dependencias iniciales:
  - `httpx`
  - `beautifulsoup4`
  - `typer`
  - `pytest`
  - `ruff`
  - `mypy`
- Declarar un script de consola `congreso-votaciones = congreso_votaciones.cli:app`.
- Crear el paquete `src/congreso_votaciones/`.
- Expandir `.gitignore` y agregar `data/.gitignore` para evitar versionado de artefactos.

2. Modelado y configuración base

- Implementar `Settings` en `src/congreso_votaciones/config.py` con:
  - rutas de `data/raw/pleno/html`, `data/raw/pleno/pdfs`, `data/manifests`, `data/logs`
  - timeout HTML por defecto `20s`
  - timeout PDF por defecto `60s`
  - reintentos por defecto `3`
  - concurrencia por defecto `4`
  - headers HTTP con `User-Agent` identificable
- Implementar modelos tipados en `src/congreso_votaciones/models.py`.
- Decidir si los modelos serán `dataclass` o `TypedDict`; para este repo inicial se recomienda `dataclass(slots=True)` para mantener simplicidad y buen soporte de `mypy`.

3. Discovery de fuente del Pleno

- Implementar `fetch_public_page()` para descargar la página pública del Pleno.
- Implementar `extract_iframe_url(html: str) -> str` para localizar el `iframe` sin hardcodear el `src` en el flujo principal.
- Persistir el HTML crudo en `data/raw/pleno/html/public_page.html` cuando se ejecute `discover-pleno`.
- Implementar `build_expand_view_url(iframe_url: str) -> str` para forzar `OpenForm&ExpandView&Seq=1`.
- Implementar `fetch_expand_view_html()` y persistir el snapshot en `data/raw/pleno/html/expanded_view.html`.
- Validar explícitamente que el HTML expandido contiene el patrón `openWindow(` antes de pasar al parser.

4. Parseo del índice expandido

- Implementar un parser por recorrido secuencial de filas `tr` y mantenimiento de contexto jerárquico actual.
- Detectar cambios de:
  - `periodo_parlamentario`
  - `periodo_anual`
  - `legislatura`
- Detectar filas documento por presencia de `javascript:openWindow(`.
- Extraer de cada fila:
  - fecha visible
  - título visible
  - `pdf_relative_path`
  - `filename_original`
- Resolver `pdf_url` absoluta usando la base del `.nsf`.
- Normalizar `session_date_iso` desde el formato observado `MM/DD/YYYY`.
- Construir `record_id` desde `pdf_relative_path` antes de cualquier escritura a disco.
- Rechazar registros incompletos solo si faltan `pdf_relative_path` o `session_date_raw`; registrar el error para depuración.

5. Normalización y reglas de negocio

- Conservar todas las variantes del Pleno sin filtrar:
  - asistencia
  - asistencia y votaciones
  - ordinaria
  - extraordinaria
  - solemne
  - vespertina
  - oficial
  - provisional
- No colapsar por fecha.
- No deducir reemplazos entre documentos `provisional` y `oficial`.
- Guardar el texto original en `source_title` y el nombre original en `filename_original`.
- Usar `storage_relpath` con ASCII sanitizado para evitar problemas de filesystem, pero no perder los valores originales en el manifiesto.

6. Construcción y actualización del manifiesto

- Implementar lectura segura del manifiesto previo si existe.
- Hacer merge por `record_id`.
- Reglas de merge:
  - si un `record_id` nuevo no existe en el manifiesto, marcarlo `pending`
  - si existe y el archivo local es válido, conservar `download_status = downloaded`
  - si existe pero el archivo falta o falla validación, volver a `pending`
  - si el remoto ya no publica el documento, conservar el registro local y marcarlo `not_seen_in_last_discovery` si se desea trazabilidad futura
- Exportar el estado consolidado a `csv` y `jsonl` después de `discover-pleno` y nuevamente después de `download-pleno`.

7. Descarga de PDFs

- Implementar `build_storage_relpath(record)` para que la ruta local no dependa solo de la fecha.
- Implementar descarga con límite de concurrencia configurable.
- Reintentar hasta `3` veces con backoff corto.
- Escribir primero a un archivo temporal y mover a destino final solo si la validación termina bien.
- Validaciones mínimas de integridad:
  - HTTP `200`
  - `content-type` que incluya `pdf` o encabezado binario `%PDF`
  - archivo no vacío
- Calcular `sha256` y `content_length` real del archivo escrito.
- Registrar errores sin abortar el lote completo.

8. CLI de uso operativo

- `discover-pleno`
  - descarga HTML
  - resuelve `iframe`
  - genera el manifiesto sin bajar PDFs
- `download-pleno`
  - toma el manifiesto actual
  - descarga solo `pending` o `failed` si se usa `--retry-failed`
- `sync-pleno`
  - ejecuta `discover-pleno` y luego `download-pleno`
- Incluir salida legible en consola:
  - total descubiertos
  - pendientes
  - descargados
  - omitidos
  - fallidos
- Implementar una capa de servicio para que el CLI solo haga:
  - parseo de flags y validación de argumentos
  - invocación de funciones de alto nivel en `services.py`
  - traducción de resultados a salida de consola y códigos de salida
- Evitar que `cli.py` importe detalles de parsing HTML o escritura CSV directamente; esas conexiones deben resolverse por funciones de servicio con contratos estables.

9. Fixtures y tests

- Guardar una copia real de la página pública del Pleno en `tests/fixtures/pleno_public_page.html`.
- Guardar una copia real del HTML expandido en `tests/fixtures/pleno_index_expanded.html`.
- Agregar tests sobre:
  - extracción del `iframe`
  - construcción de URL expandida
  - conteo de registros parseados
  - clasificación de `document_type`, `session_type`, `is_provisional`, `is_official`
  - duplicados por fecha
  - estabilidad de `record_id`
  - merge incremental del manifiesto
  - validación de firma `%PDF`
- Si se agrega smoke test contra red real, marcarlo con `@pytest.mark.network` para no ejecutarlo por defecto.

10. Documentación operativa

- Escribir `README.md` con:
  - propósito del repo
  - alcance exclusivo a sesiones del Pleno en esta fase
  - comandos de bootstrap
  - comandos CLI
  - layout de salida en `data/`
  - advertencia de que el contenido del PDF no se parsea todavía
- Documentar que el manifiesto es el contrato de continuidad hacia etapas posteriores.
- Escribir `docs/runbook-pleno-cli.md` con:
  - comportamiento actual de `discover-pleno`, `download-pleno` y `sync-pleno`
  - ubicación y significado de snapshots HTML, manifiestos, PDFs y logs
  - semántica real de `--refresh-html`
  - códigos de salida y acciones sugeridas ante fallos comunes
  - límites conocidos del parser actual

## Tests

- Unit: `tests/test_fetch.py` debe cubrir extracción de `iframe`, derivación de `expand_view_url` y manejo de HTML sin `iframe`.
- Unit: `tests/test_parse_index.py` debe cubrir jerarquía `periodo -> anual -> legislatura -> documento`, normalización de fecha y clasificación de tipos de sesión.
- Unit: `tests/test_parse_index.py` debe cubrir que dos documentos con la misma fecha generan `record_id` distintos si cambia `pdf_relative_path`.
- Unit: `tests/test_manifest.py` debe cubrir idempotencia del merge y reactivación de registros corruptos a estado `pending`.
- Unit: `tests/test_download.py` debe cubrir validación `%PDF`, escritura temporal y cálculo de `sha256`.
- Unit: `tests/test_cli.py` debe cubrir que los comandos CLI llaman el servicio correcto, propagan flags relevantes y retornan códigos de salida esperados.
- Unit: `tests/test_services.py` debe cubrir reutilización de snapshots HTML cuando `--refresh-html` no fuerza redescarga.
- Unit: `tests/test_services.py` debe cubrir escritura de eventos operativos en `data/logs/pleno_sync.log`.
- Integration: `tests/test_parse_index.py` debe ejecutar el parser completo contra `tests/fixtures/pleno_index_expanded.html`.
- Integration: `tests/test_cli.py` debe validar el wiring `discover -> manifest` y `sync -> download` con servicios stubbeados.
- Regression: fixture con un documento `PROVISIONAL`, uno `OFICIAL`, uno `solemne`, uno `extraordinaria` y uno `vespertina`.
- Regression: `None` para extracción de contenido del PDF, porque esta fase no lo aborda.

## Validation

- Bootstrap: `uv sync`
- Format: `uv run ruff format --check pyproject.toml src tests`
- Lint: `uv run ruff check pyproject.toml src tests`
- Types: `uv run mypy src`
- Tests: `uv run pytest tests -m 'not network'`
- Optional smoke: `uv run congreso-votaciones discover-pleno --limit 3`
- Optional smoke: `uv run congreso-votaciones sync-pleno --limit 3 --max-concurrency 2`

## Risks and Mitigations

- Cambio en la página pública del Pleno -> extraer siempre el `iframe` desde la página pública y no depender solo de la URL interna.
- HTML legado inconsistente -> usar parser tolerante, fixtures reales y pruebas sobre snapshots del HTML.
- Múltiples PDFs para la misma fecha -> derivar `record_id` desde `pdf_relative_path`, no desde la fecha.
- Mezcla de documentos `provisional` y `oficial` -> descargar ambos y registrar flags explícitos en vez de colapsarlos.
- Nombres de archivo con tildes o caracteres variables -> usar ruta local sanitizada ASCII y retener nombre original en manifiesto.
- Descargas parciales o corruptas -> escribir a archivo temporal, validar `%PDF` y recalificar a `pending` si la validación falla.
- Tracking accidental de datos masivos en git -> ampliar `.gitignore` y usar `data/.gitignore`.
- Dependencia futura en red real para pruebas -> mantener el grueso de pruebas offline con fixtures y dejar los smoke tests de red como opcionales.

## Open Questions

- None

## Acceptance Criteria

- Existe un comando `discover-pleno` que descubre la fuente del Pleno desde la página pública, resuelve el `iframe`, descarga la vista expandida y genera un manifiesto con un registro por PDF.
- El manifiesto incluye jerarquía parlamentaria, fecha normalizada, tipo de documento, tipo de sesión y flags `is_provisional` / `is_official`.
- El `record_id` es estable entre ejecuciones y no colapsa documentos distintos publicados el mismo día.
- Existe un comando `sync-pleno` que solo descarga PDFs faltantes o inválidos y actualiza el manifiesto sin duplicados.
- Los PDFs descargados se validan como binarios PDF y se acompañan de `sha256`, `content_length` y estado de descarga.
- Las pruebas cubren parser, manifiesto, naming y validación de descarga.
- El proyecto queda con comandos ejecutables para `ruff`, `mypy` y `pytest`.

## Definition of Done

- Estructura inicial del proyecto creada.
- CLI de Pleno implementada y documentada.
- Discovery y descarga incremental funcionando para la fuente del Pleno.
- Manifiestos `csv` y `jsonl` generados desde código.
- Tests agregados o actualizados para parser, manifiesto y descarga.
- `uv run ruff format --check pyproject.toml src tests` en verde.
- `uv run ruff check pyproject.toml src tests` en verde.
- `uv run mypy src` en verde.
- `uv run pytest tests -m 'not network'` en verde.
- Este plan se mantiene como documento vivo si cambia el alcance o aparecen restricciones nuevas durante la implementación.
