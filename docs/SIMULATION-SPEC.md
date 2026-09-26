# Simulation and assessment specification

AI System Design Simulator · numerical contract v0.1

## 1. Purpose and limits

Model request flow, finite concurrency, queues, network transfer, caching, basic state changes, asynchronous jobs and selected failures. This is an educational model with disclosed assumptions. It does not emulate a real SQL engine, operating system, cloud provider or consensus protocol.

Time is stored as integer microseconds. API/display values use milliseconds or seconds with unit suffixes. Randomly sampled durations are rounded to at least one microsecond. At the same timestamp process fault/state changes first, service completions and commits second, deadline/lease expiry third, new arrivals/dispatch fourth, and snapshots last; use stable insertion sequence within a priority. Thus a valid completion exactly at its deadline succeeds, while a crash at that same instant takes precedence. Implement these priorities in the engine scheduler instead of relying on accidental SimPy callback order.

## 2. Workload contract

Each case defines operation mix, arrival-rate segments, payload size, key distribution, initial data, warmup, measurement, drain, seed and fault schedule. Normal arrivals use a Poisson process inside each constant-rate segment. A segment boundary schedules its own future arrivals; it must not leak arrivals from the preceding rate.

Original user arrivals are independent of response completion. Retries are child attempts and cannot create additional original-user successes. v0.1 uses no automatic client retries in graded workloads. Supported service retries are explicit, bounded and visible. Arrivals scheduled at a boundary belong to the new interval: measurement is [start, end), and the instant at measurement end begins drain.

Create the complete original-arrival trace before running a design. A comparison reuses this trace, operation payloads, initial data and fault schedule across all revisions. Separate randomness for workloads, service samples, retry jitter and failures. Key service samples by seed, request/job ID, logical component ID, attempt and operation so a topology edit does not reshuffle all other samples.

Preview: the first steady scenario, seed 101, 10 s warmup, 60 s measurement, 30 s drain; result is exploratory. The default preview does not claim to exercise a burst scheduled after 120 s. Assessment: each required scenario at seeds 101, 202, 303, 404, 505, with 60 s warmup, 300 s measurement and 30 s drain. Scenario times are relative to the measurement start. Reset each case independently.

## 3. Request lifecycle

An original request has `request_id`, `operation_id`, `key`, payload, scheduled arrival, deadline and parent-free identity. Each hop records arrival, wait start, service start, service end, downstream wait, response transfer and status.

Compute nodes have a finite number of handler slots per instance and finite FIFO waiting room. Excess arrivals receive an explicit rejection. An application handler stays occupied while awaiting synchronous dependencies; call this busy handler occupancy, not CPU utilization. Data-service slots are released after their local operation, before response network transfer.

Default processing durations are Gamma distributed with mean m and coefficient of variation c from the profile. Shape = 1/c²; scale = m*c². c=0 means a constant duration. Preset values are teaching parameters, not benchmark-derived capacities.

Arrival-to-terminal-outcome time includes all network transfer, waiting, local processing and synchronous dependencies. A timeout is a user failure even if downstream work subsequently finishes. A timed-out operation already executing may continue and change state; its late completion must remain in the trace and cannot produce a second user success.

For an ordinary request, emit exactly one terminal user outcome: success, timeout, rejected, dependency_error, invalid_result, or incomplete. The measurement cohort comprises original arrivals during the measurement interval; warmup arrivals may affect state but do not count in the cohort.

## 4. Network behavior

Every edge has propagation delay and a bandwidth limit per direction. Serialize payload bytes through a FIFO link resource for bytes/bandwidth seconds, release that resource, then apply propagation delay. Return payloads traverse the reverse direction of the same logical link. Default: 2 ms one-way propagation and 100 MiB/s per direction, unless a challenge overrides them.

Link queue wait and transfer time are separate from node service. Object payload transfer is not charged a second time as object-store local processing. These links are simplified independent channels; TCP congestion, loss recovery, DNS and TLS are not simulated in v0.1.

## 5. Caches, data and writes

Cache entries store key, value/version, insertion time, expiry and size. Implement LRU eviction; hits do not extend TTL. Keys originate in the workload. A cache's hit rate is measured, never a learner-entered success percentage. Start empty unless a scenario explicitly preloads entries; warmup can populate them.

On a miss, fetch from the connected store and populate after the response. Concurrent misses are independent in v0.1; no request coalescing. A write commits one key/version atomically in the logical store. SQL here models an atomic single-key operation and constrained processing, not SQL syntax or multi-key transactions.

Invalidation can be off or synchronous. With synchronous invalidation, the application writes to the store, invalidates connected cache keys, then acknowledges. Fence in-flight cache fills with per-key invalidation generations so a read started before invalidation cannot repopulate an old version afterward. This simplified behavior must be explicit in component help.

For a read at observation time t, acceptable freshness means its returned version is at least the latest committed version with commit time <= t minus the allowed freshness interval. Correctness and freshness are separate: an older valid value may be stale; a value for the wrong key is incorrect. No reads qualifying for a freshness check means insufficient evidence, not a perfect score.

## 6. Queue and worker behavior

Enqueue success means the buffer accepted the job; it does not mean the job completed. Track accepted, delivered, failed, expired and pending job IDs separately. Queue storage survives consumer redelivery in a case; queue-node crash durability is not modeled and cannot be claimed.

A consumer receives a lease. On successful delivery it acknowledges; on lease expiry or a retryable error the message can be redelivered, up to max attempts. Workers use an atomic job-ID check-and-record at effect commit, so overlapping attempts cannot both produce an effect when deduplication is enabled. The notification effect is a record in a synthetic delivery sink, not a real external email/SMS service. Attempt counters and effects must be separate.

Job completion latency starts at the original user enqueue arrival and ends at the first successful effect. User request acknowledgement has its own latency. A duplicate-effect requirement requires the synthetic effect ledger; it cannot be inferred from queue length.

## 7. Faults and termination

v0.1 fault types: application-instance unavailable, node service-time multiplier, and cache clear. Fault intervals are fixed in the scenario before execution. Instance failure removes its slots and fails its active/queued requests; selection follows stable instance ID. Recovery restores capacity. Load-balancer health checks have interval and threshold; do not assume immediate rerouting.

Measure through the full 300 s interval, then stop original arrivals and drain for 30 s. Continue deadlines and job expiry checks. At drain end, any remaining cohort work is classified incomplete or deadline-missed as appropriate; it is never silently dropped. Downstream abandoned work can continue consuming modeled resources until shutdown but cannot modify a recorded terminal user outcome.

Record the first violation of per-request or time-window requirements. An aggregate requirement with no single failing request must link to its calculation window instead of inventing a root-cause trace.

## 8. Metric definitions

| Metric | Exact meaning |
|---|---|
| User success rate | Successful original cohort requests / all original cohort arrivals |
| p50/p95/p99 response latency | Nearest-rank percentiles of successful original cohort response durations; show sample count and failure rate alongside |
| Goodput | Original requests that are successful, correct, and meet their operation deadline / measurement seconds |
| Queue depth | Number waiting, excluding actively processing items |
| Queue wait | Service start minus queue arrival for serviced work; unfinished work shown separately |
| Busy-slot occupancy | Time integral of busy handler/data slots divided by available slot-time; display unavailable capacity separately |
| Retry amplification | Total attempts / original operations; do not count attempts as goodput |
| Job deadline completion | Jobs with a correct first effect by their deadline / all original enqueue-intent arrivals |
| Freshness violation rate | Eligible successful reads below the allowed committed-version boundary / eligible successful reads |
| Duplicate effects | Extra synthetic effects for an already-effected job ID |
| Recovery time | Time from fault end until all operation targets hold in consecutive full 10 s windows for 30 s; null if not established before case end |
| Credits/hour | Sum of configured provisioned-instance profile rates; includes idle resources and disconnected billable nodes |

Requirement metrics use unrounded values. Latency percentiles return null for zero samples, never zero. Reject/rate-limit outcomes remain failures for the defined legitimate workload. A separate abuse-protection objective would require a distinct workload and rubric.

Cost v0.1 has fixed fictional rates and fixed provisioning. There is no storage/egress usage bill or autoscaling cost model yet. Display missing dimensions next to cost, and never label credits as USD.

## 9. Assessment rules

Requirements name a metric, operation scope, scenarios, comparator, threshold, minimum sample count and severity. All published v0.1 completion requirements are hard requirements. Optional stress tests are clearly separate and cannot silently change completion status.

Evaluate each requirement per scenario and per seed. Status is pass only if every applicable case passes and required evidence is available. Any violation is fail; unsupported metric is not_evaluated; cancellation, cap or missing completed cases is incomplete. Overall challenge completion requires all hard requirements to pass. Preserve the case-level results; do not hide failures behind an average across seeds.

Use minimum 100 successful samples for p95, 1,000 for an optional p99, and 100 eligible reads for freshness unless a challenge explicitly declares another minimum. Missing samples prevent a pass. Show sample counts and run-to-run ranges. These five seeds are repeatability checks, not a statistical claim about production availability.

## 10. Comparing candidates

Freeze baseline inputs. Generate at most two schema-valid candidate patches. Evaluate baseline and candidates using the same assessment workload bundle and supported profiles. Match faults by logical role/instance mapping; adding instances does not remove a required failure. Reject comparisons if scenario applicability changes unexpectedly.

First compare feasibility: which designs pass all hard requirements? Among passing designs, the default objective is minimum credits/hour. At equal cost, show latency and complexity trade-offs without claiming a unique winner. If none passes, report unmet requirements and improvements without a Best label.

Retain losing and invalid candidates and explanations. A claim of lower cost or latency must reference actual comparison metrics. No global optimality claim is supported.

## 11. Verification before release

Check one constant-time server, finite queues, exact event ordering, byte-transfer delay, cache expiry/invalidations, asynchronous acknowledgement vs completion, and late work after timeouts. Compare stable single-server random workloads with queueing-theory expectations under their matching assumptions and broad predeclared tolerances. Test flow conservation and terminal-outcome uniqueness. These checks validate implementation of the model; real-infrastructure accuracy needs separate experiments.
