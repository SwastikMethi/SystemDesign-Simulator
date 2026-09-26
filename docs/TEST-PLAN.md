# Test and credibility plan

AI System Design Simulator · v0.1

## 1. What testing establishes

Tests verify that the software implements its stated simulation model and rubric. They do not establish exact real-world infrastructure performance. Real-service calibration is a later experiment and must be reported separately.

Prioritize numerical correctness, reproducibility, grading, and the complete learner journey. Avoid tests that merely mirror rendering implementation details.

## 2. Engine and accounting fixtures

| Fixture | Expected evidence |
|---|---|
| One server, constant service, no network | Exact known completion times and FIFO waiting |
| Full finite queue | Correct rejection count and no disappearing requests |
| Zero arrivals | Unavailable percentiles; no divide-by-zero; incomplete sample-dependent assessment |
| Timeout while dependency continues | One failed user outcome; downstream capacity consumed; late state changes visible |
| Sequential network transfers | Time includes serialization, FIFO waiting, propagation and response bytes exactly once |
| Two app instances | Dispatch uses configured slots; no magical increase in SQL capacity |
| Cache hit/miss/expiry | Measured hits, correct LRU eviction and TTL boundary |
| Write racing cache fill | Synchronous invalidation generation prevents reintroducing old data |
| Queue accepts quickly, worker slow | Fast acknowledgement coexists with failed job deadline requirement |
| Lease expires before completion | Attempt history preserved; deduplication prevents an extra modeled effect when enabled |
| Component fault | Expected unavailable capacity, active-request outcomes and recovery schedule |
| Event cap | Incomplete status, persisted diagnostic reason and no completion badge |

Conservation checks: original arrivals = terminal outcomes plus explicitly pending originals during execution; after finalization every original cohort member has exactly one terminal outcome. Attempts and jobs have separate conservation accounting. Busy slots stay within available capacity, queue depth is nonnegative, versions never fabricate a commit, and all exported numerical values are finite or explicitly null.

## 3. Analytical and repeatability checks

For constant durations, calculate exact expected outcomes by hand. For a single M/M/1 queue, use exponential arrivals and service, stable load below capacity, sufficiently long measurement and warmup, and predeclared statistical tolerances against known waiting/response expectations. Do not compare a finite-queue or timeout-heavy scenario to an unbounded stationary formula without accounting for the changed assumptions.

Identical input versions and seed reproduce the same event ordering, outcomes and hashes within the pinned runtime. Editing only canvas positions or labels does not alter numerical results. A candidate topology change must leave the precomputed incoming workload identical. Test replay at 0.5×, 1× and 4×; numerical results remain unchanged.

## 4. Assessment cases

Test values just below, exactly on and just above every comparator boundary. Evaluate unrounded values. Verify that one failing seed makes the applicable requirement fail; missing evidence yields not_evaluated or incomplete; percentiles exclude unsuccessful responses but success rate includes those failures; zero-sample metrics cannot pass.

Test cost for idle and disconnected billable nodes, profile upgrades and valid instance counts. Verify credits are never formatted as real currency. Check that optional experiments cannot silently change completion.

Each of the five challenges needs a passing design, an intended failure design and a budget failure design. Execute all required scenarios/seeds for each. Independently review problem wording, feasibility, feedback and trace evidence before publishing the challenge in the prototype.

## 5. AI and patch tests

Use fixed evidence fixtures to test invalid references, invented numbers, unsupported claims, stale revision patches, unknown component types, workload edits, negative capacity, nonexistent edge targets and prompt injection in labels. Invalid content must not become a valid review or candidate.

Verify that AI cannot overwrite a verdict, that patch testing preserves the active design, and that losing candidates remain visible. Simulate provider timeout, rate limit, malformed JSON and unavailable usage fields. Deterministic results remain accessible and missing cost stays null.

Manual review rubric: explanation is understandable, names the relevant evidence, distinguishes observation from hypothesis, acknowledges assumptions and proposes a testable change. Do not grade the coach solely through another LLM.

## 6. End-to-end journeys

1. Catalogue starter → preview → assessment failure → inspect evidence → AI suggestion → compare → adopt revision → assess/save.
2. Same journey with provider unavailable through results; request review later.
3. Refresh during a run and reconnect to current progress.
4. Cancel a queued/active run; confirm no badge is awarded.
5. Restart backend mid-run; show Interrupted and preserve complete prior runs.
6. Export a comparison, reimport supported design/workload data, and reproduce under matching versions.
7. Edit a previously passing design; show Unassessed changes and preserve historical pass.

Use deterministic fixtures for automated browser tests; run a small manual live-provider smoke test separately. No requirement to provision actual cloud resources.

## 7. UI, motion and performance

Measure on M1 Max / 32 GB RAM using the default catalogue workload. Targets are release goals, not existing measurements:

- Visual feedback for direct interaction within 100 ms.
- Smooth canvas/playback target 60 fps; investigate p95 frame durations above 33 ms under the 100-marker cap.
- API status/cancel requests remain responsive while the child process runs.
- Default 15-case catalogue assessment target <=60 s wall time, excluding AI, with <=2 GiB additional process memory. If missed, profile and reduce overhead without changing numerical semantics; document measured limits before release.
- No frame-rate-dependent metrics, fabricated progress or moving-marker overload.

Test keyboard-only operation, focus order, contrast, reduced motion, long labels, validation errors and 1440×900/1024×768 layouts. Review a complete demo recording for legibility and meaningful cause/effect transitions.

## 8. Release checklist

All critical numerical and scoring fixtures pass. Five challenges have reviewed runnable fixtures. UI never calls unsupported capabilities simulated. Export preserves compatibility evidence. AI claims and patches are validated. No secret is included in frontend/export. README records actual setup commands and measured limits. Open defects that can invalidate a verdict block release.
