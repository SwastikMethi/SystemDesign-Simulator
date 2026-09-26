# Task 2 — simulator and deterministic assessment

Implemented 26 September 2026. All twenty original authored fixtures have now been executed across every required scenario and all five seeds: **240 completed cases**. No design fixture or rubric threshold needed adjustment.

## Delivered interfaces

- `backend.simulation.run_case(challenge, design, workload, *, on_progress=None, should_cancel=None) -> CaseArtifacts`.
- `CaseArtifacts` contains typed `result`, `outcomes`, `jobs`, `snapshots`, and `traces`. Every original arrival before measurement end, including warmup, has one request outcome; grading selects `[warmup_end_us, measurement_end_us)`.
- `run_suite(...)` returns `(AssessmentResult, list[CaseArtifacts])`; the API continues orchestrating individual cases.
- `backend.assessment.assess_suite(challenge, case_results, *, mode='assessment')` verifies required scenario/seed and requirement-row completeness. Preview/experiment cannot complete a challenge. Interrupted/canceled/missing cases remain incomplete. Within a completed suite, a known violation yields fail even if another metric has insufficient samples.
- `compare_assessments(mapping)` ranks only passing designs by provisioned cost. Equal costs share a rank; failed designs have no rank.
- `python -m backend.fixtures` runs the installed fixtures and persists case-level requirement values, sample counts, statuses, and timings. Supports `--challenge`, `--fixture`, `--output`.
- `JobOutcome.accepted_us` is queue admission (additive shared contract coordinated with parent). `acknowledged_us` is the consumer's acknowledgement; user acknowledgement is the originating `RequestOutcome`. Rejected intents are preserved with `accepted_us=None`.
- Design-level cost/recovery metrics live in `node_metrics['__design__']`. Every assessed requirement also contains its own typed measured value and evidence IDs.

## Numerical implementation

All ten component types execute through an actual SimPy event heap. Integer microseconds and explicit priorities order fault/state changes, completion/commit, deadline/lease, dispatch, and snapshot events; SimPy's insertion sequence breaks ties. Finite FIFO node pools retain app handlers across synchronous calls. Each edge direction independently reserves FIFO serialization capacity, then incurs propagation, with data slots released before return transfer.

The engine includes keyed Gamma service samples, deadline-safe original outcomes and late commits, bounded retry-safe reads, token buckets, per-instance round robin, delayed LB health checks, single-key histories and observation-time freshness, object capacity, independent LRU caches, expiry, clear/invalidation generation fencing, all-instance synchronous invalidation, job leases/redelivery, an atomic synthetic effect ledger, all three fault categories, and overlapping-fault recovery. Queue worker attempts and first effects are accounted separately from original enqueue intents.

Snapshots are fixed at one virtual second. At most 100 request traces are retained, prioritizing first request/correctness/freshness/job failures; each trace is bounded at 200 events. Aggregate failures cite their actual measurement window; request-level failures additionally cite a retained trace. Progress callbacks receive coarse time/snapshot dictionaries and do no network I/O.

Caps: 100,000 original arrivals, 2,000,000 executed events, one-hour virtual case duration, plus contract node/edge/instance caps. Cancellation is checked every 1,024 events. Partial runs preserve explicit incomplete outcomes, including unstarted planned arrivals without negative durations, and cannot pass.

## RED / GREEN evidence

Initial numerical tests failed collection because `Engine`, `Scheduler`, and `Pool` did not exist. The first four exact tests then passed after implementation. Added regressions exposed and fixed job-failure trace retention and completed-suite failure precedence. The additive admission-field regression was red until the coordinated shared schema field was available.

Final scoped command:

```sh
.venv/bin/python -m pytest tests/test_simulation.py tests/test_assessment.py -q
```

**26 passed in 0.44 s.** Coverage includes exact FIFO/finite rejection, independent directional links, deadline equality and crash priority, late-write conservation, zero samples, cancel/cap accounting, TTL/LRU and invalidation/clear races, every cache instance invalidated, lease overlap with dedup on/off, queue acknowledgement versus effect deadline, accepted-pending versus rejected jobs, first-failure retention under the 100-trace cap, retry-safe-only behavior, per-instance LB failure/recovery delay, object capacity, all fault types and overlaps, SQL capacity independent of app count, labels/positions and unrelated-topology invariance, all comparator boundaries, missing cases/requirements, ties, and recovery windows including job targets.

The analytical M/M/1 test uses 30,000 arrivals, excludes the first 1,000 for warmup, and checks mean queue wait against 4 seconds at lambda=.8/mu=1 with a predeclared 15% tolerance. Exact constant-service tests separately verify microsecond arithmetic.

A repository integration checkpoint before the final additive admission/trace tests was **43 passed in 89.79 s**, including real API-engine execution. Parent owns the final integration run; no claim that this older checkpoint includes subsequent tests.

## Executed fixture verdicts

| Challenge | Initial | Reference | Intended failure | Budget | Cases per fixture |
|---|---|---|---|---|---:|
| Team notes | pass | pass | fail | fail | 10 |
| URL lookup | fail | pass | fail | fail | 10 |
| Product catalogue | fail | pass | fail | fail | 15 |
| Photo delivery | pass | pass | fail | fail | 15 |
| Notifications | fail | pass | fail | fail | 10 |

All required seeds were 101, 202, 303, 404 and 505. All reference operation success rates were 1.0. Maximum observed reference p95 values (across its operations/cases) were 54.130 ms, 59.084 ms, 59.894 ms, 59.110 ms, and 12.034 ms respectively. Catalogue reference freshness violations were zero; notification reference deadline completion was 1.0. Reference costs remain 50, 82, 82, 42, and 70 credits/hour.

The intended failures show the planned lessons: team/photo rate limits reduce legitimate request success; URL SQL overload fails burst success/latency; catalogue invalidation-off freshness violation rates range from 0.4945 to 0.5845; notification burst deadline completion falls as low as 0.2684 despite successful fast user acknowledgements. Budget fixtures exceed their published cost limits. Team notes and photo initial designs already pass; no mandatory cache/LB/CDN topology was invented to make them fail.

Full measured case evidence: `.implementation/fixture-results-final.json`. This includes every case's unrounded requirement value and sample count; no favorable seed selection or threshold relaxation occurred. The full final matrix took 268.161 seconds and peaked at 179,175,424 process RSS bytes (145,866,752 additional bytes over startup).

## Catalogue benchmark

Latest isolated 15-case catalogue reference: **27.337 seconds** (27.414 seconds including runner reporting/GC), **167,542,784 bytes peak RSS**, **133,922,816 additional bytes** (~127.7 MiB). This meets the <=60-second and <=2-GiB additional-memory targets. All 15 cases passed under the binding 2,000,000-event cap; the largest executed case used 232,002 events.

Target verified by coordinator: Apple M1 Max, 32 GiB, arm64; project Python 3.13.12. Timing uses `time.perf_counter()` wall time; memory uses `resource.getrusage(RUSAGE_SELF).ru_maxrss`, which is bytes on macOS, minus the process startup high-water baseline. AI/provider latency is excluded. Machine-readable measurement and each case are saved in `.implementation/catalogue-benchmark.json`.

## Limits and review handoff

These are the specified educational models: independent links without TCP, logical atomic stores without database/consensus emulation, no queue-node crash durability, synthetic notification effects, and fictional fixed provisioning credits without usage/egress billing. Store/profile calibration against infrastructure is outside this release. Sandbox-only test hooks permit deterministic service/network values; public `run_case` uses the authored profiles and network defaults.

No API/storage/coach/frontend code or authored fixture content was changed by this task. The additive shared `accepted_us` field/schema was implemented by the coordinator. Engine, assessment, fixture runner, numerical tests, this report, and measured JSON artifacts are the owned handoff for independent review.

Review correction: the first implementation incorrectly chose an 8,000,000 event ceiling. `docs/BUILD-PLAN.md` specifies 2,000,000; the constant was corrected without changing numerical scheduling. The catalogue benchmark was rerun with the binding cap and now records executed event counts.
