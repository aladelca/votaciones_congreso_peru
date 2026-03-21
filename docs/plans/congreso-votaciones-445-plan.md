# Manifest Persistence Hardening Plan

## Metadata
```yaml
id: congreso-votaciones-445
spec: docs/specs/perform-an-extensive-code-review-20260321T010428Z-d6b4001d.md
owner: Adrian Alarcon
status: draft
created: 2026-03-21
updated: 2026-03-21
```

## Phases
- Phase 0: Use the closed `congreso-votaciones-2gy` discovery fix as the baseline, assume the current local fixtures and source tree are authoritative, and treat `pleno_pdfs_index.jsonl` as the canonical manifest because runtime reads only `manifest_jsonl_path`.
- Phase 1: Codify the malformed-manifest contract in `congreso-votaciones-445.1` so `load_manifest` and service callers fail fast with path-aware recovery guidance instead of silently skipping corrupted state.
- Phase 2: Implement temp-file-plus-replace persistence in `congreso-votaciones-445.2`, using same-directory staging files and a commit order that prioritizes correctness of the canonical JSONL manifest over the derived CSV export.
- Phase 3: Finish `congreso-votaciones-445.3` with regression coverage for malformed input and failed writes, then update the runbook so operators know how to detect corruption, recover, and re-run safely.

## Tasks (machine-readable)
- `docs/plans/congreso-votaciones-445-tasks.json` must conform to `docs/contracts/autonomy-tasks.schema.json`.

## Task list (human summary)
| id | title | deps | status | notes |
| --- | --- | --- | --- | --- |
| congreso-votaciones-445 | Make manifest persistence atomic and resilient to partial writes | congreso-votaciones-2gy | open | Umbrella bug for manifest safety; blocker `congreso-votaciones-2gy` is already closed, so execution can proceed. |
| congreso-votaciones-445.1 | Codify malformed manifest contract and recovery path | congreso-votaciones-445 | open | Establishes the canonical JSONL contract, fail-fast loader behavior, and operator guidance before write-path changes land. |
| congreso-votaciones-445.2 | Implement atomic manifest writes for JSONL and CSV | congreso-votaciones-445.1 | open | Refactors `src/congreso_votaciones/manifest.py` and `src/congreso_votaciones/services.py` around temp-file-plus-replace persistence helpers. |
| congreso-votaciones-445.3 | Add manifest persistence regression coverage and operator guidance | congreso-votaciones-445.2 | open | Locks in malformed-input and interrupted-write behavior with fixture-backed tests plus runbook updates. |

## Risks
- Dual-file persistence cannot be truly atomic across both `csv` and `jsonl`, so the implementation must explicitly favor correctness of the canonical JSONL manifest and document any derivative CSV drift behavior.
- `src/congreso_votaciones/manifest.py` and `src/congreso_votaciones/services.py` are shared hot spots with downstream issue `congreso-votaciones-1ez`, so landing work out of order increases merge and regression risk.
- Temp-file-plus-replace only behaves atomically when staging happens on the same filesystem as the target path; helper design must avoid cross-directory temp files.
- A new corruption contract changes operator-visible failure behavior, so tests and `docs/runbook-pleno-cli.md` must land in the same sequence as the code.

## Evidence checklist
- Reviewed `docs/specs/perform-an-extensive-code-review-20260321T010428Z-d6b4001d.md` for requirements, acceptance criteria, and rollout sequencing.
- Inspected `src/congreso_votaciones/manifest.py` and `src/congreso_votaciones/services.py` to confirm direct `open(..., "w")` writes and JSONL-only load behavior.
- Inspected `tests/test_manifest.py` and `tests/test_services.py` to confirm current coverage gaps around malformed input and partial-write failures.
- Inspected `docs/runbook-pleno-cli.md` to align the planned corruption contract with current operator guidance.
- Created child Beads tasks `congreso-votaciones-445.1`, `congreso-votaciones-445.2`, and `congreso-votaciones-445.3` with acceptance criteria and sequential dependencies.
- Confirmed the upstream blocker `congreso-votaciones-2gy` is closed.

## Rollout / rollback
- Execute child tasks in order: `congreso-votaciones-445.1`, then `congreso-votaciones-445.2`, then `congreso-votaciones-445.3`.
- During implementation, run `uv run pytest tests/test_manifest.py tests/test_services.py` after each phase and run full gates before closing `congreso-votaciones-445`.
- Roll back by reverting the last persistence-scoped change set, removing any orphaned temp artifacts, and keeping `pleno_pdfs_index.jsonl` as the source of truth for recovery.
