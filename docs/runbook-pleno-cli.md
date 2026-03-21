# Runbook del CLI de Pleno

## Objetivo

Este runbook describe el comportamiento actual del CLI que descubre, indexa y descarga los PDFs publicados en `Asistencia y Votaciones a las Sesiones del Pleno` del Congreso del Perú.

## Comandos disponibles

```bash
uv run congreso-votaciones discover-pleno
uv run congreso-votaciones download-pleno
uv run congreso-votaciones sync-pleno
```

Flags operativas:

```bash
--output-root <path>
--limit <n>
--max-concurrency <n>
--retry-failed
--refresh-html
```

## Comportamiento actual

### `discover-pleno`

- Resuelve la página pública del Pleno.
- Obtiene la URL del `iframe`.
- Construye la vista expandida `?OpenForm&ExpandView&Seq=1`.
- Parsea el índice jerárquico y genera manifiestos `csv` y `jsonl`.
- El archivo canónico es `data/manifests/pleno_pdfs_index.jsonl`; `pleno_pdfs_index.csv` es una exportación derivada para inspección manual.
- Si se usa `--limit`, solo recorta los registros procesados en esta corrida; el manifiesto conserva entradas previas no redescubiertas.
- No descarga PDFs.

### `download-pleno`

- Lee el manifiesto actual.
- Selecciona registros `pending`.
- Si se usa `--retry-failed`, también reintenta registros `failed`.
- Descarga PDFs válidos, calcula `sha256` y actualiza el manifiesto.

### `sync-pleno`

- Ejecuta `discover-pleno`.
- Luego ejecuta `download-pleno` sobre el manifiesto resultante.

## Cache HTML

Comportamiento vigente:

- Si existen `public_page.html` y `expanded_view.html` en `data/raw/pleno/html/`, `discover-pleno` reutiliza esos snapshots por defecto.
- Si se pasa `--refresh-html`, fuerza redescarga de ambos HTML antes de parsear.
- El CLI expone esta decisión en la salida como `note: html_source=cache` o `note: html_source=network`.

Esto reduce carga sobre la fuente y permite repetir discovery offline contra snapshots ya guardados.

## Artefactos generados

```text
data/
├── raw/
│   └── pleno/
│       ├── html/
│       │   ├── public_page.html
│       │   └── expanded_view.html
│       └── pdfs/
├── manifests/
│   ├── pleno_pdfs_index.csv
│   └── pleno_pdfs_index.jsonl
└── logs/
    └── pleno_sync.log
```

## Log operativo

El sistema escribe eventos JSONL en `data/logs/pleno_sync.log`.

Eventos actuales:

- `discover_started`
- `discover_completed`
- `download_started`
- `download_completed`
- `download_failed_record`
- `download_missing_manifest`
- `manifest_load_failed`

Cada línea contiene `timestamp`, `event` y campos operativos como `command`, `limit`, `failed`, `manifest_jsonl` o `record_id`.

Cuando el loader detecta un `jsonl` corrupto o inválido, el error menciona la ruta afectada y, si aplica, la línea fallida. El mensaje también recuerda que el JSONL es el manifiesto canónico y que el CSV se vuelve a generar a partir de ese archivo.

## Salida de consola esperada

Formato base:

```text
command: discover-pleno
discovered: 3
pending: 3
downloaded: 0
skipped: 0
failed: 0
manifest_csv: /ruta/.../pleno_pdfs_index.csv
manifest_jsonl: /ruta/.../pleno_pdfs_index.jsonl
note: log_path=/ruta/.../pleno_sync.log
note: html_source=network
```

Para `download-pleno` también aparece:

```text
note: download_candidates=<n>
```

## Códigos de salida

- `0`: ejecución correcta
- `1`: error operativo o descarga parcial con fallos
- `2`: error de configuración, por ejemplo ejecutar `download-pleno` sin manifiesto previo

## Validación actual conocida

Estado verificado en esta rama:

- `ruff format --check`: OK
- `ruff check`: OK
- `mypy src`: OK
- `pytest tests -m 'not network'`: OK

Smoke real confirmado:

```bash
.venv/bin/congreso-votaciones discover-pleno --limit 3 --output-root /tmp/congreso-votaciones-smoke
.venv/bin/congreso-votaciones download-pleno --limit 1 --output-root /tmp/congreso-votaciones-smoke
```

## Limitaciones conocidas

- El contenido interno del PDF todavía no se parsea.
- El manifiesto conserva simultáneamente PDFs `provisional` y `official`; no hay lógica de reemplazo semántico.
- El parser actual del índice y el conteo por regex no necesariamente producen el mismo total si se usan métodos distintos de conteo.
- `bd` no está operativo ahora mismo en este repo porque el backend Dolt no levanta de forma confiable.

## Fallos comunes y respuesta

### `configuration-error: ... Ejecuta discover-pleno primero`

Causa:

- Se llamó `download-pleno` sin manifiesto previo en `output-root`.

Acción:

```bash
uv run congreso-votaciones discover-pleno --output-root <path>
uv run congreso-votaciones download-pleno --output-root <path>
```

### `error: Manifiesto JSONL inválido en ...`

Causa:

- `data/manifests/pleno_pdfs_index.jsonl` existe pero está truncado, vacío o contiene una línea JSON inválida.
- El `payload` de una línea ya no coincide con el contrato esperado de `ManifestRecord`.

Acción:

1. Trata `pleno_pdfs_index.jsonl` como la fuente canónica y no intentes recuperar el estado desde el CSV.
2. Mueve o corrige el JSONL corrupto.
3. Regenera ambos manifiestos desde discovery.

```bash
mv -f data/manifests/pleno_pdfs_index.jsonl data/manifests/pleno_pdfs_index.jsonl.bak
uv run congreso-votaciones discover-pleno --refresh-html --output-root <path>
```

Si necesitas conservar evidencia para diagnóstico, guarda también `data/logs/pleno_sync.log` antes de regenerar.

### `error: No se pudo persistir el manifiesto en ...`

Causa:

- El proceso no pudo escribir o reemplazar el archivo destino en `data/manifests/`.
- Si el error menciona `pleno_pdfs_index.csv`, el JSONL canónico puede haberse actualizado y el CSV haber quedado desfasado.

Acción:

1. Corrige la causa operativa: permisos, espacio en disco o bloqueo del archivo.
2. Si falló `pleno_pdfs_index.jsonl`, el manifiesto anterior se conserva porque la escritura usa archivo temporal + `replace`; vuelve a ejecutar el comando luego de corregir el problema.
3. Si falló `pleno_pdfs_index.csv`, toma el JSONL como fuente de verdad y vuelve a ejecutar `discover-pleno` o `sync-pleno` para regenerar la exportación derivada.

```bash
uv run congreso-votaciones discover-pleno --output-root <path>
```

### Discovery usa HTML viejo

Causa:

- Existen snapshots locales y no se pasó `--refresh-html`.

Acción:

```bash
uv run congreso-votaciones discover-pleno --refresh-html
```

### PDFs en `downloaded` pero archivo local inválido

Comportamiento actual:

- En la siguiente corrida, el reconciliador marca el registro nuevamente como `pending`.

Acción:

```bash
uv run congreso-votaciones download-pleno --retry-failed
```

### Fallos remotos o PDFs corruptos

Comportamiento actual:

- Se reintenta hasta `3` veces.
- Si no se recupera, el registro queda en `failed` y el detalle aparece en el manifiesto y en el log.

## Ruta recomendada para operar

Primera corrida:

```bash
uv sync
uv run congreso-votaciones sync-pleno --refresh-html
```

Corridas siguientes:

```bash
uv run congreso-votaciones sync-pleno
```

Recuperación de fallos:

```bash
uv run congreso-votaciones download-pleno --retry-failed
```
