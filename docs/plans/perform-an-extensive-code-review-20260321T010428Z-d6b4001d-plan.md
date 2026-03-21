# Extensive Code Review Remediation Plan

## Metadata
```yaml
id: perform-an-extensive-code-review-20260321T010428Z-d6b4001d
spec: docs/specs/perform-an-extensive-code-review-20260321T010428Z-d6b4001d.md
owner: Adrian Alarcon
status: draft
created: 2026-03-21
updated: 2026-03-21
```

## Phases
- Phase 0: Use the existing review spec and current local fixture corpus as the planning baseline; assume the untracked worktree is intentional and no live-site verification is required for this plan.
- Phase 1: Remove destructive discovery behavior by fixing canonical manifest merge semantics in `congreso-votaciones-2gy`.
- Phase 2: Harden manifest persistence and corruption handling in `congreso-votaciones-445` after the canonical-manifest behavior is defined.
- Phase 3: Improve failed-download observability in `congreso-votaciones-1ez` on top of the hardened manifest persistence surface.
- Phase 4: Resolve the parser contract for missing parliamentary hierarchy metadata in `congreso-votaciones-3gw`, then re-run quality gates and update operator-facing documentation.

## Tasks (machine-readable)
- `docs/plans/perform-an-extensive-code-review-20260321T010428Z-d6b4001d-tasks.json` must conform to `docs/contracts/autonomy-tasks.schema.json`.

## Task list (human summary)
| id | title | deps | status | notes |
| --- | --- | --- | --- | --- |
| congreso-votaciones-2gy | Prevent manifest truncation during limited or partial discovery | N/A | open | Highest-risk defect; touches `src/congreso_votaciones/services.py`, `src/congreso_votaciones/manifest.py`, and regression coverage in `tests/test_manifest.py` / `tests/test_services.py`. |
| congreso-votaciones-445 | Make manifest persistence atomic and resilient to partial writes | congreso-votaciones-2gy | open | Shares the manifest persistence surface; acceptance criteria already added in `bd`. |
| congreso-votaciones-1ez | Capture HTTP failure metadata for failed PDF downloads | congreso-votaciones-445 | open | Builds on persisted manifest behavior; expected touch points are `src/congreso_votaciones/download.py`, `src/congreso_votaciones/models.py`, and `tests/test_download.py`. |
| congreso-votaciones-3gw | Clarify or normalize missing parliamentary metadata in parsed records | N/A | open | Can proceed in parallel with the manifest work once the nullability/backfill policy is chosen and documented. |

## Risks
- The local `bd` Dolt server is unstable and intermittently closes during writes, so tracker updates may require retries even though the core issues and the two blocker dependencies were persisted.
- The repository has no configured Git remote and no commits yet, so the higher-level push-based handoff workflow cannot be completed from this environment.
- `src/congreso_votaciones/manifest.py` and `src/congreso_votaciones/services.py` are shared hot spots across the first three remediation tasks; landing them out of order increases merge and regression risk.
- Assumption: the local fixtures and current spec remain the authoritative baseline for this review plan; upstream Congreso HTML is not revalidated here.

## Evidence checklist
- `docs/specs/perform-an-extensive-code-review-20260321T010428Z-d6b4001d.md` reviewed and used as the source of truth for requirements, risks, and acceptance criteria.
- Source modules inspected: `src/congreso_votaciones/manifest.py`, `src/congreso_votaciones/services.py`, `src/congreso_votaciones/download.py`, `src/congreso_votaciones/parse_index.py`, `src/congreso_votaciones/models.py`.
- Test modules inspected: `tests/test_manifest.py`, `tests/test_services.py`, `tests/test_download.py`, `tests/test_parse_index.py`.
- `bd` issue `congreso-votaciones-1g6` is closed and the follow-up issues `congreso-votaciones-2gy`, `congreso-votaciones-445`, `congreso-votaciones-1ez`, and `congreso-votaciones-3gw` exist with acceptance criteria recorded.
- `bd` blocker dependencies were confirmed for `congreso-votaciones-445 -> congreso-votaciones-2gy` and `congreso-votaciones-1ez -> congreso-votaciones-445`.
- `uv run pytest` passed on 2026-03-21 UTC with 15 tests.
- `uv run ruff check` passed on 2026-03-21 UTC.
- `uv run mypy src` passed on 2026-03-21 UTC.

## Rollout / rollback
- Roll out in issue order: `congreso-votaciones-2gy`, `congreso-votaciones-445`, `congreso-votaciones-1ez`; `congreso-votaciones-3gw` can land in parallel once the metadata contract decision is explicit.
- After each issue, run targeted tests for touched modules, then run `uv run pytest`, `uv run ruff check`, and `uv run mypy src` before closing the issue.
- Roll back by reverting the last issue-scoped change set and restoring the previously known-good manifest behavior if a persistence or download contract change regresses offline flows.
