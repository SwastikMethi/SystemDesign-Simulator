# SDD ledger — plan: docs/BUILD-PLAN.md

## Preflight

| Producer / consumer | Interface / check | Resolution |
|---|---|---|
| Task 1 → Task 2 | Pydantic designs/challenges/profiles, compiler and workloads | Engine consumes validated canonical models |
| Task 1 → Task 3 | Draft/run validation, hashes, patches | Same validator for manual/AI edits |
| Task 2 → Task 3 | Headless case/suite, outcomes and assessments | Backend spawns one simulation process; no engine work in request thread |
| Task 3 → Task 4 | OpenAPI, SSE, replay/comparison/review shapes | Generated API types, actual data only |
| Tasks 1–4 → Task 5 | Full fixtures and learner journey | All acceptance criteria verified before release claim |
| Task 1 | Schemas vs examples/constraints | Preserve examples and thresholds |
| Task 2 | Simulation vs grading | Rules assess saved outputs; AI cannot grade |
| Task 3 | Async jobs vs persistence | Manifest finalization and SSE separate from numerical truth |
| Task 4 | Playback vs numerical outcomes | Playback never recalculates evidence |
| Task 5 | Release claims vs measurements | Publish only actual results |

Ruling: The provided folder is a new documentation-only workspace with no existing Git repository or branch. Initialize a dedicated feature branch in place; a second worktree provides no existing code isolation benefit. Cost if wrong: relocate the checkout later without changing project behavior.

Task 1: in progress; implementer /root/contracts; BASE 1b280c8.
Task 1: initial implementation eb79736, 12 tests passing; review /root/contracts_review requires strict per-component exported settings schema and rejection of nonfinite challenge rates. Fix round 1 in progress.
Task 1: complete (implementation eb79736 + fix 98bf6c8; `.venv/bin/python -m pytest -q` → 14 passed; schema export and uv lock check passed; /root/contracts_review approved both Important fixes and found no new blocking breakage).
Task 1: minor (deferred): input integer strings are coerced by Pydantic while exported schema requires integer values.
Task 1: minor (deferred): operation_ids reordering changes the numerical design hash despite equivalent operation routing.
Task 2: in progress; /root/engine, BASE 5f05d47; owns simulation/assessment/numerical fixtures and tests.
Task 3: in progress; /root/application, BASE 5f05d47; owns API/storage/jobs/coach and related tests; HTTP schema publication precedes frontend dispatch.
Task 4: in progress; /root/frontend, consumes backend/openapi.json and .implementation/http-interface.md; owns frontend/ only. Core 17 API paths published; remaining endpoint schemas will follow without changing core shapes.
Task 5: pending.

Ruling: After the shared contracts pass review, use the dispatching-parallel-agents skill for disjoint engine and application-service implementations, followed by frontend once HTTP shapes are published. The frozen handoff is .implementation/interfaces.md; owners do not modify each other's modules. This replaces serial dispatch only for these independent implementation surfaces and retains task reviews and real integration tests. Cost if wrong: interface mismatch caught and repaired at integration, without merging unverified behavior.
