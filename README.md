# Congreso Votaciones

Bootstrap inicial para descubrir, indexar y descargar los PDFs publicados en `Asistencia y Votaciones a las Sesiones del Pleno` del Congreso del Perú.

## Alcance actual

- descubre la página pública del Pleno;
- resuelve el `iframe` oficial;
- descarga la vista expandida del índice;
- parsea el árbol jerárquico y genera manifiestos `csv` y `jsonl`;
- descarga PDFs de forma incremental e idempotente;
- expone comandos CLI para `discover-pleno`, `download-pleno` y `sync-pleno`.

## Requisitos

- Python `3.12+`
- `uv`

## Bootstrap

```bash
uv sync
```

## CLI

```bash
uv run congreso-votaciones discover-pleno
uv run congreso-votaciones download-pleno
uv run congreso-votaciones sync-pleno
```

Opciones útiles:

```bash
uv run congreso-votaciones discover-pleno --limit 10
uv run congreso-votaciones download-pleno --retry-failed --max-concurrency 2
uv run congreso-votaciones sync-pleno --refresh-html
```

Semántica actual de `--limit`:

- acota solo los registros descubiertos o procesados en la ejecución actual;
- no recorta el manifiesto canónico si ya existen registros previamente indexados.

Semántica actual de `--refresh-html`:

- por defecto `discover-pleno` y `sync-pleno` reutilizan snapshots HTML locales si ya existen en `data/raw/pleno/html/`;
- con `--refresh-html` se fuerza redescarga de la página pública y de la vista expandida antes de parsear.

## Layout

```text
data/
├── raw/
│   └── pleno/
│       ├── html/
│       └── pdfs/
├── manifests/
└── logs/
```

El contenido interno de los PDFs todavía no se parsea en esta etapa. El manifiesto es el contrato base para futuras fases.

## Runbook

- Ver [docs/runbook-pleno-cli.md](docs/runbook-pleno-cli.md) para operación diaria, artefactos, logs, salidas esperadas y fallos comunes.
