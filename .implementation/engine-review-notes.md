# Numerical implementation review notes

These are acceptance concerns derived from the approved specs, not replacement semantics.

- Do not use ordinary SimPy timeout/process callback order as the domain priority contract. All mutations must route through a scheduler with explicit priority and stable insertion order. Completion at deadline succeeds; crash at the same instant wins.
- End-of-measurement arrivals belong to drain and are not generated. Warmup work influences state but not measurement denominator. Use a finalization event after same-time completions and deadline events at drain end.
- Service randomness is keyed by seed, original ID, logical node, attempt and operation; a topology change cannot consume an unrelated global RNG stream.
- Apps keep handler occupancy during synchronous dependencies; data slots release before return transfer. Network request and response directions are independent FIFO channels.
- A timed-out operation already running may still commit, invalidate, consume slots or deliver an effect. It must not change its terminal user outcome or be counted twice.
- Freshness compares against committed history at client observation minus allowance. Single-key versions advance in commit order, independent of precomputed arrival IDs. Initial version zero is part of history.
- Synchronous invalidation covers every cache instance. Generation fencing prevents an old in-flight fill after invalidate/clear. Cache hit does not slide expiry; instances have independent LRU contents.
- Store nodes share data only within that node; separate SQL icons cannot accidentally share one dict. Compiler binds each dataset to one terminal store for its coupled operations.
- Queue acknowledgement and first effect are different outcomes. Job denominator is original enqueue intents, including rejected enqueues. Attempt counts and effect ledger must be separate; overlapping leases can cause duplicates with dedup off.
- First failure for aggregate metrics links to the actual evaluation window; it is not inferred from an arbitrary slow request. Traces are bounded but first correctness/freshness/timeout failures take retention priority.
- A cap, cancel, crash or missing required case cannot produce a completion badge, even when partial metrics appear good. Null latency with insufficient samples is not zero latency.
- Catalogue reference hypothesis: app.medium + sql.large costs 90 credits/h, within budget, and avoids cache correctness concerns. It must be executed before calling it passing. More app capacity alone must not give SQL magical capacity.
- For team-notes, cache/queue writes are compile-time failures. A separately runnable timeout/rate-limit fixture is needed for an assessed failure. Photo delivery may pass without a CDN; do not force a topology or assert an unmeasured CDN benefit.
- Require all seeds for each fixture; no threshold reductions or favorable-seed selection. Performance target is not proof until measured on the target machine.
