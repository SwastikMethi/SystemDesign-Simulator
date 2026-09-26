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

The first full browser sweep passed the 11 existing tests, but both new journeys reached their 20-second assessment wait while the shared simulation worker was still processing other tests' longer exercises. Their waits now match the existing preview/assessment integration tests (60/120 seconds, with 240 seconds for the whole journey). Assertions still require completed, passing real results. The final full rerun on `c2620e5` passed **all 13 browser tests in 3.9 minutes**, including the two walkthrough journeys alongside the original exercises.

The existing local app was refreshed on port 8770. Its installed challenge endpoint returned `first-design` with one operation and one required assessment case. Test runs use a separate temporary data directory.

## Independent review

`gpt-6-astra` reviewed immutable range `fcbd00e..c2620e5`, the approved plan, numerical evidence and screenshots. **No Critical, Important or Minor findings; no behaviors declined for judgment.** The reviewer confirmed original challenge compatibility, shared registration, instruction/control alignment, existing focus/save protections, the intended numerical lesson and usable narrow layouts. Approval was conditional on the full browser rerun, which subsequently passed as recorded above.

## Execution decisions

- Continued in the clean existing feature checkout to keep the running local workspace consistent. Cost if wrong: move the completed commit to a separate checkout.
- Used the completion wrapper for the full browser suite after focused journeys and the implementation commit, avoiding a redundant preliminary full sweep. Its observed queue-wait failure justified the corrected rerun, which passed. Cost if wrong: fix any final-suite failure before completion.
- Ran the independent read-only review against the immutable commit while the final browser rerun completed. Cost if wrong: cover any later source correction with a failing regression and green suite; no source corrections were needed after review.
- Keep the completed changes on the current feature branch; merging and publishing were not requested.
