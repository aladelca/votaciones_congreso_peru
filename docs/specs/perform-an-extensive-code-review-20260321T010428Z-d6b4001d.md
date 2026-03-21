# Extensive Code Review of the Pleno Ingestion CLI

## Metadata
```yaml
id: perform-an-extensive-code-review-20260321t010428z-d6b4001d
owner: Adrian Alarcon
status: draft
created: 2026-03-21
updated: 2026-03-21
```

## Problem statement
The current `congreso-votaciones` codebase already has a coherent CLI, fixture-backed tests, and passing static checks, but it is still a bootstrap scraper whose correctness depends on fragile HTML parsing, manifest persistence, and download bookkeeping. Before extending the project into large-scale ingestion or PDF content extraction, the team needs a review artifact that converts code-level findings into explicit follow-up requirements.

Assumptions used for this review:
- The local worktree contents are intentional, even though the repository is largely untracked.
- The review is based on the local source tree, bundled fixtures, and local quality gates; it does not treat the live Congreso site as the source of truth.
- Missing hierarchy metadata in fixture-derived records may reflect either source omissions or parser limitations; the contract is therefore treated as ambiguous until clarified.

## Goals
- Synthesize the current architecture, test posture, and operational behavior of the Pleno ingestion CLI.
- Convert the highest-value review findings into actionable requirements and acceptance criteria.
- Preserve evidence for the most important risks discovered during review, especially around manifest safety and operator visibility.
- Record linked follow-up work in `bd` so the review does not become a standalone tracking system.

## Non-goals
- Implement the fixes described in this document.
- Redesign the scraper beyond the defects and contract gaps identified here.
- Add PDF content extraction, downstream analytics, or schema extensions unrelated to the current review findings.
- Provide a live-site certification of the Congreso source pages.

## Requirements
### Functional
- The discovery pipeline must not delete previously indexed records when `discover-pleno` or `sync-pleno` runs with `--limit` or against a temporarily incomplete upstream index.
- The persisted manifest must remain the canonical historical inventory of discovered PDFs unless a record is explicitly tombstoned or otherwise modeled as removed.
- Manifest writes must be atomic enough to avoid leaving partial JSONL or CSV state after interruptions.
- Manifest loading must surface corruption with an actionable error contract, and the team must decide whether recovery is fail-fast or tolerant.
- Failed PDF downloads must preserve richer failure metadata than a free-form message when HTTP or transport information is available.
- The data contract for `periodo_anual` and `legislatura` must explicitly allow nullable values or define a verified backfill strategy.
- The review output must reference tracked follow-up items in `bd`.

### Non-functional
- The ingestion flow must remain idempotent for repeated discovery and download runs.
- Review follow-ups must preserve offline reproducibility with fixture-backed tests.
- Observability must be sufficient for an operator to distinguish partial success, destructive behavior, and transient remote failures.
- Changes driven by this review must keep `pytest`, `ruff`, and `mypy` green.
- Persistence behavior must favor data safety over raw throughput.

## Interfaces / data contracts
- CLI surface reviewed: `discover-pleno`, `download-pleno`, and `sync-pleno` in `src/congreso_votaciones/cli.py`.
- Discovery contract reviewed: public page HTML, extracted `iframe` URL, expanded index HTML, and parsed `PlenoPdfRecord` values.
- Persistence contract reviewed: `pleno_pdfs_index.jsonl` and `pleno_pdfs_index.csv` generated from `ManifestRecord`.
- Download contract reviewed: `DownloadResult` plus filesystem outputs under `data/raw/pleno/pdfs/`.
- Logging contract reviewed: JSONL entries written to `data/logs/pleno_sync.log`.
- Contract gap identified: limited discovery currently behaves as destructive persistence, demonstrated locally by a full discovery of 933 records followed by `discover_pleno(..., limit=10)`, which rewrote the persisted manifest to 10 records.
- Contract gap identified: parsed records can currently contain blank `periodo_anual` values and blank `legislatura` values, so downstream consumers cannot assume these fields are always populated.
- Contract gap identified: failed downloads currently preserve `error_message` but do not consistently preserve HTTP classification metadata on failure paths.

## Acceptance criteria
- Re-running discovery with `--limit` after a full cached discovery no longer truncates the persisted manifest; an automated test covers this regression.
- Discovery against a temporarily incomplete index does not silently delete previously known records without an explicit removal model.
- Manifest persistence uses an atomic write strategy, and corruption handling is covered by tests for malformed or interrupted JSONL state.
- Failed downloads persist actionable metadata for HTTP and transport failures, and tests verify at least one HTTP error path.
- The nullability or backfill policy for `periodo_anual` and `legislatura` is documented and enforced by tests or validation rules.
- The follow-up issues created from this review remain linked in `bd` and map cleanly to the requirements above.
- `uv run pytest`, `uv run ruff check`, and `uv run mypy src` pass after the remediation work lands.

## Open questions
- Should `--limit` be treated strictly as a sampling mode that never mutates the canonical manifest, or should it persist a scoped manifest under a different file path?
- When upstream HTML omits `periodo_anual` or `legislatura`, should the pipeline preserve `null` semantics, carry forward the last known heading, or infer values from session dates and congressional periods?
- For malformed manifest lines, should commands fail immediately with a recovery hint, or should the loader quarantine bad rows and continue?
- Should HTML discovery fetches gain the same retry semantics already used for PDF downloads, or is fail-fast behavior preferred for upstream page changes?

## Risks
- High: manifest truncation during limited or partial discovery can silently discard previously indexed records and invalidate downstream download state.
- Medium: non-atomic manifest writes can corrupt the canonical inventory after an interrupted run.
- Medium: incomplete failure metadata for PDF downloads makes operations and debugging materially harder.
- Medium: the parser depends on specific HTML markers such as the first `iframe`, `openWindow(...)`, and heading row text, so upstream markup drift can break discovery.
- Low to medium: missing hierarchy metadata is already present in fixture-derived output, which can leak ambiguity into downstream analytics.
- Process risk: `bd` was usable during the review but showed intermittent local Dolt connectivity failures, so issue-tracking automation in this repo is not fully reliable.
- Environment risk: the repository currently has no configured Git remote, so normal push-based handoff automation cannot be completed as written in the higher-level workflow.

## References
- `README.md`
- `docs/runbook-pleno-cli.md`
- `src/congreso_votaciones/cli.py`
- `src/congreso_votaciones/services.py`
- `src/congreso_votaciones/manifest.py`
- `src/congreso_votaciones/download.py`
- `src/congreso_votaciones/parse_index.py`
- `tests/test_services.py`
- `tests/test_manifest.py`
- `tests/test_download.py`
- `tests/test_parse_index.py`
- `bd` review task: `congreso-votaciones-1g6`
- `bd` follow-up issues: `congreso-votaciones-2gy`, `congreso-votaciones-445`, `congreso-votaciones-1ez`, `congreso-votaciones-3gw`
- Quality gate evidence collected during review: `uv run pytest` passed with 15 tests, `uv run ruff check` passed, and `uv run mypy src` passed
