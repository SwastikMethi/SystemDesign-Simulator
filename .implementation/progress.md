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

Task 1: pending.
Task 2: pending.
Task 3: pending.
Task 4: pending.
Task 5: pending.
