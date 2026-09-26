# Acceptance evidence

This file maps the v0.1 PRD to implementation evidence. Pending rows are not release claims. Numerical fixtures establish the stated model, not real-cloud accuracy.

| PRD | Required behavior | Evidence owner | Status |
|---|---|---|---|
| P01 | Five ranked playable challenges | Authored content validation; full fixture runner; library journey | Pending |
| P02 | Ten editable component types, undo/redo/save | Compiler/profile tests; canvas behavior tests; browser journey | Pending |
| P03 | Explicit validated operation routes | `tests/test_contracts.py`; all 20 authored designs compile; draft versus runnable rules | Verified |
| P04 | Seeded event simulation and terminal outcomes | `tests/test_simulation.py`; exact timing, network conservation, cache races, late writes, shared workers, explicit priority and fault mapping regressions | Verified |
| P05 | Four-state deterministic assessment with evidence | `tests/test_assessment.py`; all comparator/sample boundaries; final 240-case fixture run | Verified |
| P06 | Grounded independent AI explanation | `tests/test_coach.py` and API review regressions: server-owned verdict, cited numerical claims, malformed responses, opt-in, and saved errors | Verified with controlled provider responses; live provider untested |
| P07 | Two-candidate immutable matched comparison | Patch/hash/ranking tests; compare/adopt browser journey | Pending |
| P08 | First-failure trace or aggregate replay | Saved evidence retention and replay navigation tests | Pending |
| P09 | Cache assumptions and demand-shift experiment | Warm/cold fixtures; optional scenario scoring isolation | Pending |
| P10 | Local history and export | Atomic storage; ZIP import/export/reproduction; saved-work journey | Pending |
| P11 | Pause/speed/step/reduced motion | Browser behavior and manual visual inspection | Pending |
| P12 | AI and interrupted-run failure handling | `tests/test_storage_jobs.py`, API/coach tests: injected write errors, queue rollback, queued cancellation, simulation/review/comparison restart, SSE replay/resync, preserved provider errors | Verified |

## Release measurements

Final engine fixture verification: **20 designs, 240 completed cases**, with all five references passing and all ten intended/budget failures failing. Maximum case event count was **357,734**, below the 2,000,000 limit. Full matrix wall time was 322.416 seconds while other verification work was running. The exact unrounded requirement values, sample counts and verdicts are in [release-fixtures.json](../.implementation/release-fixtures.json). This rerun includes the corrected event priority, fair shared-worker dispatch, and fault applicability behavior.

Measured on 26 September 2026, Apple M1 Max / 32 GiB, arm64, Python 3.13.12 and Node 25.2.1:

| Measurement | Observed | Method and scope |
|---|---:|---|
| Catalogue reference, all 15 cases | 30.472 s | Headless engine wall clock, excluding API persistence/browser/AI |
| Additional peak process RSS | 119.4 MiB | macOS `ru_maxrss` high-water mark minus startup baseline |
| Maximum catalogue events per case | 285,103 | Actual scheduler event count, below the 2,000,000 cap |
| Canvas interaction p95 | 32.8 ms | 20 pointer selections, pointerdown to second animation frame, 1440×900 headless Chromium |
| Canvas frame interval p95 | 16.8 ms | 240 idle canvas frame intervals; no claim about 100-marker playback load |

Numerical measurements: [.implementation/catalogue-benchmark.json](../.implementation/catalogue-benchmark.json), generated with `.venv/bin/python -m backend.fixtures --challenge product-catalogue --fixture reference --output .implementation/catalogue-benchmark.json`. Browser samples: [.implementation/ui-performance.json](../.implementation/ui-performance.json), generated with `node .implementation/browser-inspect.mjs --measure`. The browser sample recorded no page errors.

Targets are at most 60 seconds and 2 GiB additional memory for the headless catalogue suite, at most 100 ms interaction feedback, and investigation above 33 ms p95 frame time. These measurements cover the stated environments and workloads; they are not production capacity claims.

## Manual validation

Live-provider access and the five-person learning study cannot be replaced by deterministic test doubles. Mark each as performed or not performed; do not claim outcomes without observations. Review problem wording, feasibility, feedback and trace evidence for all released challenges.
