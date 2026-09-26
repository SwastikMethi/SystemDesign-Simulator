# Acceptance evidence

The v0.1 implementation and independent final review are complete. This file maps the PRD to executed verification evidence and its limits. Numerical fixtures establish the stated model, not real-cloud accuracy; live-provider quality and the five-person learning study remain unverified.

| PRD | Required behavior | Evidence owner | Status |
|---|---|---|---|
| P01 | Five ranked playable challenges | `tests/test_contracts.py`; all 20 designs/240 cases; ranked library and real learner journey | Verified |
| P02 | Ten editable component types, undo/redo/save | Compiler/profile and graph tests; live drag/Undo; keyboard component dialog; saved-draft race regression | Verified |
| P03 | Explicit validated operation routes | `tests/test_contracts.py`; all 20 authored designs compile; draft versus runnable rules | Verified |
| P04 | Seeded event simulation and terminal outcomes | `tests/test_simulation.py`; exact timing, network conservation, cache races, late writes, shared workers, priorities, canonical traversal/fault bindings and full array-permutation regressions | Verified |
| P05 | Four-state deterministic assessment with evidence | `tests/test_assessment.py`; all comparator/sample boundaries; final 240-case fixture run | Verified |
| P06 | Grounded independent AI explanation | Coach/API regressions: server-owned verdict, cited claims, strict outgoing schema, context-only proposal and real comparison, total provider deadline, malformed/partial responses, opt-in and saved errors | Verified with controlled provider responses; live provider untested |
| P07 | Two-candidate immutable matched comparison | API patch/hash/fault-binding/tie tests; loser preservation; real compare/adopt journey; baseline identity regression | Verified |
| P08 | First-failure trace or aggregate replay | Saved artifact references resolve stale successful reads, duplicate effects and late delivery; aggregate windows stay distinct; real failure replay and delayed case/trace response checks | Verified |
| P09 | Cache assumptions and demand-shift experiment | Warm/cold catalogue fixtures; seeded Zipf/segment checks; separate experiment mode; reviewed saved-work scenario selection | Verified |
| P10 | Local history and export | Atomic storage and injected I/O errors; actual comparison ZIP import/export; canonical rerun validation and safe deletion regressions | Verified |
| P11 | Pause/speed/step/reduced motion | Recorded replay under both motion settings, keyboard editing, six dialogs with focus transfer/wrap/Escape/restoration at both widths, visual inspection; no AI request during replay | Verified |
| P12 | AI and interrupted-run failure handling | `tests/test_storage_jobs.py`, API/coach tests: injected write errors, queue rollback, queued cancellation, simulation/review/comparison restart, SSE replay/resync, preserved provider errors | Verified |

## Release measurements

The initial 75 backend checks passed across the full sweep and one targeted integration rerun. Final review corrections separately passed 45 numerical/contract/assessment checks and 28 coach/guidance/API checks. The updated frontend passed eight unit tests and all ten browser tests across the combined run (nine passes) plus a focused corrected rerun. Both full real-server learner journeys passed at 1440×900 and 1024×768. The remaining browser checks cover editor behavior, delayed responses, lifecycle recovery and modal accessibility; four focused regressions use controlled responses against the real application to expose specific evidence/race conditions. The independent scoped final re-review of `d7296cb..2b41d2b` returned **Approved**, with all seven Important findings and both minor items addressed and no new Critical/Important breakage. Exact commands and the test-only selector corrections are documented in [final-fix-report.md](../.implementation/final-fix-report.md) and [task-5-report.md](../.implementation/task-5-report.md); review dispositions are in [final-review.md](../.implementation/final-review.md).

Final engine **0.1.1** fixture verification: **20 designs, 240 completed cases**, with all five references passing and all ten intended/budget failures failing. Maximum case event count was **357,734**, below the 2,000,000 limit. Full matrix wall time was **305.789 seconds** while other verification work was running. The exact unrounded requirement values, sample counts and verdicts are in [release-fixtures.json](../.implementation/release-fixtures.json). This rerun includes canonical graph traversal/fault selection, explicit event priority, fair shared-worker dispatch and fault applicability checks. All 20 fixture summaries match the prior engine artifact after excluding wall-clock measurements.

Measured on 26 September 2026, Apple M1 Max / 32 GiB, arm64, Python 3.13.12 and Node 25.2.1:

| Measurement | Observed | Method and scope |
|---|---:|---|
| Catalogue reference, all 15 cases | 33.221 s | Headless engine 0.1.1 wall clock, excluding API persistence/browser/AI |
| Additional peak process RSS | 124.5 MiB | macOS `ru_maxrss` high-water mark minus startup baseline |
| Maximum catalogue events per case | 285,103 | Actual scheduler event count, below the 2,000,000 cap |
| Canvas interaction p95 | 32.8 ms | 20 pointer selections, pointerdown to second animation frame, 1440×900 headless Chromium |
| Canvas frame interval p95 | 16.8 ms | 240 idle canvas frame intervals; no claim about 100-marker playback load |

Numerical measurements: [.implementation/catalogue-benchmark.json](../.implementation/catalogue-benchmark.json), generated with `.venv/bin/python -m backend.fixtures --challenge product-catalogue --fixture reference --output .implementation/catalogue-benchmark.json`. Browser samples: [.implementation/ui-performance.json](../.implementation/ui-performance.json), generated with `node .implementation/browser-inspect.mjs --measure`. The browser sample recorded no page errors.

Targets are at most 60 seconds and 2 GiB additional memory for the headless catalogue suite, at most 100 ms interaction feedback, and investigation above 33 ms p95 frame time. These measurements cover the stated environments and workloads; they are not production capacity claims.

## Manual validation

The corrected editor was inspected at 1440×900 and 1024×768, with actual keyboard input, live dragging and reduced-motion replay checks. Recorded result views and native-dialog screenshots were inspected separately. Local artifacts include the [recorded journey](../frontend/screenshots/demo.webm), [failure view](../frontend/screenshots/failure-1440.png), [comparison view](../frontend/screenshots/comparison-1440.png), and [evidence ZIP](../frontend/screenshots/evidence.zip). The full narrow journey has a separate [recording](../frontend/screenshots/demo-1024.webm), [comparison view](../frontend/screenshots/comparison-1024-journey.png), and [evidence ZIP](../frontend/screenshots/evidence-1024.zip). These generated browser artifacts are retained locally and ignored by Git. The refreshed wide recording is 1440×900, 25 fps and **110.04 seconds**; sampled frames from a 30-second sequence were inspected alongside full-page comparisons. The narrow-viewport recording lasts **108.96 seconds** on the same capture canvas. Narrow screenshots showed readable controls and no horizontal clipping. Both final ZIPs contain 147 entries and passed independent CRC checks.

Live-provider smoke: **not performed**. Five-person learning study: **not performed**. Controlled provider responses verify contracts and failure handling; they do not establish explanation quality or learning impact. The locked FastAPI/Starlette test client emits one `httpx` deprecation warning; no warning suppression was added.
