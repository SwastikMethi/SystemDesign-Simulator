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

Task 2: implementation 5eb8d5c; 26 scoped tests passed, all20 fixtures/240 cases executed. Five references pass, every intended/budget failure fails. Coordinator found event-cap constant8,000,000 contradicting binding2,000,000; implementer correcting before independent review.
Task 3 integration: equal-cost passing ties must remain tied; imported workloads may earn completion only from a fresh assessment after exact canonical verification; JobOutcome now records queue admission separately.
Task 5: README setup and evidence draft created; final browser verification, reviews, acceptance map, and demo remain.
Task 2: fix round 1/5 — all3 Important findings addressed in ee4628b; scoped independent /root/engine_review Approved;31 tests pass,40 targeted authored cases preserve measurements. Task2 engine implementation complete; required fault_bindings comparison guard tracked in Task3.
Task 3: fix round1/5 in progress with /root/application;4 initial review findings plus comparison fault-map integration, details .implementation/reviews.md.
Task 3: fix round1/5 — three original findings addressed; overall coach authority remained partial; review found malformed usage handling and missing instance applicability gaps.
Task 3: fix round2/5 — commits1167a5f and05cf8a1 address remaining findings and aggregate expanded import limits; /root/application_review Approved, no new Important breakage. Task3 complete. Backend checkpoint60 tests passed, final focused16 passed/1 long test deselected; TestClient deprecation is a documented dependency warning.
Task 4: implementation continues; root identified required architecture replay/diff missing from initial results view. Independent /root/recorded_graph owns only RecordedGraph.tsx/css; /root/frontend owns integration, all other frontend files, and browser tests. Frozen prop contract sent to both.
Task 5: final engine matrix rerun completed:20 designs/240 cases; all references pass and all intended/budget failures fail, maximum357,734 events. Actual release data .implementation/release-fixtures.json. Full backend verification rerunning after accepted review fixes.
Ruling: The saved review's overall summary and assessment status are generated from the deterministic run; provider output supplies cited findings and experiments only. This enforces AI-COACH-SPEC's prohibition on model verdicts without relying on a synonym blacklist. The owning spec now documents prompt contract v2. Cost if wrong: revise provider schema/prompt; saved numerical outcomes remain unchanged.
Task 5: startup recovery for abandoned review/comparison jobs and complete coach profile/capacity payload assigned to application owner as integration fixes; covered by focused checks and the final whole-branch review.
Task 5: integration recovery ec81d06 passed17 focused tests. Release audit then found missing injected I/O, simulation restart, cancellation terminal state and SSE replay/resync checks. Commit03e2d8c adds focused checks and fixes failed pre-acceptance persistence leaving a run queued;18 API/storage tests pass,1 unchanged long test deselected.
Task 4/5: approved Explain/Hint teaching modes were missing before a run. Application owner is adding saved-draft guidance through the existing provider boundary; frontend owner integrates a concise opt-in panel. This remains required scope, not a deferred feature.
Task 4: core08a5382 passes build,2 Vitest checks and2 real-server Playwright journeys. Independent /root/frontend_review Needs fixes:6 Important UI identity/race/coach/evidence defects and2 small state-display issues. One consolidated correction round assigned to frontend owner; details .implementation/reviews.md. Final review awaits those fixes plus guidance.
Task 5: backend pre-run guidance7c67c07 complete;28 focused API/coach/storage/guidance checks pass,1 unchanged long integration test deselected. Draft guidance uses authored context only, question-first hints and explicit opt-in; no model grading or fake run. Frontend integration and core review fixes remain.

Ruling: After the shared contracts pass review, use the dispatching-parallel-agents skill for disjoint engine and application-service implementations, followed by frontend once HTTP shapes are published. The frozen handoff is .implementation/interfaces.md; owners do not modify each other's modules. This replaces serial dispatch only for these independent implementation surfaces and retains task reviews and real integration tests. Cost if wrong: interface mismatch caught and repaired at integration, without merging unverified behavior.
