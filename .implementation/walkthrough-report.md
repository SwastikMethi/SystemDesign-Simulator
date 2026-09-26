# Walkthrough verification

Approved plan: [walkthrough-plan.md](walkthrough-plan.md). Implementation base: `fcbd00e`.

## Delivered

“Your first design” appears above the five regular challenges with a Start walkthrough action and normal assessment progress. It loads a connected Client → App → Database starter and a five-step checklist in the existing Guide. The learner previews the capacity failure, selects Database's medium profile, assesses, and reopens the saved pass. The short challenge uses real simulation and existing saves, results and history; no AI, dependency, wire-contract or engine changes.

The installed challenge IDs are shared by the loader and fixture CLI. Original IDs/order and fixtures remain intact. The README and challenge specification document the walkthrough's explicit shortened assessment and unchanged Preview protocol.

## Numerical evidence

Executed the CLI's four walkthrough fixtures; [measured cases](walkthrough-fixture-results.json):

| Fixture | Verdict | Success | Successful read p95 | Credits/hour |
|---|---|---|---|---|
| Initial / failure | Fail | 85.63% | 1070.04 ms | 25 |
| Reference (medium SQL) | Pass | 100% | 63.07 ms | 45 |
| Budget (large SQL) | Fail | 100% | 63.07 ms | 85 |

Each fixture completed its one assessment case. Preview regression checks also verify that a passing reference preview remains incomplete and cannot serve as assessment completion.

## Executed checks

- Baseline: 82 backend tests and 8 frontend tests passed.
- Observed RED: new simulation checks and content inventory failed for the missing challenge; both browser widths failed for the missing walkthrough entry.
- Focused simulation/contracts: **18 passed in 3.48 s**.
- Full backend suite: **88 passed in 120.06 s**. The existing Starlette/httpx TestClient deprecation warning remains; dependency versions were not changed.
- Frontend unit checks: **8 passed in 593 ms**.
- TypeScript and production build: passed; Vite completed in **1.44 s**.
- New real-server browser journeys: **2 passed in 17.0 s**, at 1440×900 and 1024×768. They exercise failed preview/evidence, manual profile selection, all three passing requirements, library completion and reopening the exact saved assessment. No uncaught page errors or horizontal page overflow.
- The first post-implementation browser run stalled on an overly strict test label locator. The accessibility snapshot showed combobox “Profile”; changing the test to that role/name resolved it without altering production behavior.
- Inspected the wide library, narrow Guide and narrow passing result screenshots in `frontend/screenshots/walkthrough-*.png`.

The final full browser suite and independent review are pending.

## Execution decisions

- Continued in the clean existing feature checkout to keep the running local workspace consistent. Cost if wrong: move the completed commit to a separate checkout.
- The completion wrapper runs the full browser suite once after the focused journeys and implementation commit, avoiding a duplicate full run. A failing final suite will be fixed before completion.
- Keep the completed changes on the current feature branch; merging and publishing were not requested.
