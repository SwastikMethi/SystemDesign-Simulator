# Component catalogue

AI System Design Simulator · component profiles v0.1

## 1. Support policy

Ten component types are required for the prototype. Every type has defined ports, configuration, behavior and trace events. Expansion types are visible in documentation and an optional Coming later drawer, not as functional blocks in assessed designs.

Show one of these support labels for each capability: Simulated, Rule checked, or Not modeled. A static diagram check cannot be presented as a performance or security measurement.

## 2. Shared settings

Stable node ID, display name, profile ID, instance count, per-instance handler slots, queue limit, local service-time profile and credits/hour. Hide advanced settings until expanded. Assessment permits documented presets and selected policy controls; it does not permit arbitrary zero-cost capacity or zero service times. Freeform profile editing is sandbox-only and invalidates graded comparability.

All processing values below are synthetic means with coefficient of variation 0.25. The shared network defaults are defined in SIMULATION-SPEC. Queue limits are per instance unless stated otherwise. Instance dispatch within a node uses round-robin; a separate load-balancer node is needed for routing among distinct service nodes and explicit health checks.

## 3. Prototype catalogue and small profiles

| Type / profile ID | Purpose and behavior | Small-profile defaults | Credits/h per instance |
|---|---|---|---:|
| client / client.v1 | Emits original workload requests; observes end-to-end results | One workload source; no service queue | 0 |
| load_balancer / lb.small.v1 | Round-robin among matching upstream routes; health checks skip marked-unhealthy targets | 64 slots; 0.5 ms local processing; queue 500; check every 1 s, one failed check to remove and two successful checks to restore | 5 |
| api_gateway / gateway.small.v1 | Routes operations and applies an optional token-bucket rate limit | 32 slots; 1 ms; queue 200; rate limit disabled by default | 5 |
| app_service / app.small.v1 | Executes supported operation routes and synchronous invalidation policies | 4 handler slots; 2 ms; queue 100; holds handler while awaiting downstream work | 5 |
| sql_database / sql.small.v1 | Logical versioned key/value store with atomic single-key commits | 2 slots; read 20 ms, write 30 ms; queue 100; 100,000 keys | 20 |
| cache / cache.small.v1 | LRU key cache; hits return, misses fetch; version/generation-aware invalidation | 16 slots; 1 ms; queue 100; 128 keys; TTL 60 s | 8 |
| message_queue / queue.small.v1 | Bounded job buffer with leases and redelivery | 16 enqueue slots; 1 ms; enqueue wait queue 100; buffer 10,000 jobs; lease 5 s; max attempts 3 | 5 |
| worker / worker.small.v1 | Processes notification jobs into a synthetic delivery ledger | 2 slots; 50 ms; no independent prefetch backlog; deduplicate by job ID | 5 |
| object_storage / object.small.v1 | Stores and returns logical blobs; enforces storage capacity | 16 slots; 5 ms; queue 100; 1 GiB capacity; transfer time comes from links | 10 |
| cdn / cdn.small.v1 | Byte-limited LRU cache for immutable object reads | 32 slots; 1 ms; queue 200; 64 MiB capacity; TTL 60 s; misses fetch from object store | 8 |

Profile identifiers are immutable. Medium profiles use twice the slots and twice the cost; large profiles use four times the slots and four times the cost. Keep service means unchanged. For cache/CDN/object storage, capacity also scales by that factor. For queues, the job buffer scales; other waiting-room limits remain as listed. The suffix is medium.v1 or large.v1. Client has only client.v1. These deliberately simple cost/performance assumptions must be disclosed.

Instances scale provisioned capacity and cost linearly within this teaching model. Cache/CDN instances have independent contents and round-robin dispatch, so adding instances may lower effective hit rate. SQL and object nodes represent one logical store with a selected processing profile; v0.1 requires instance_count=1 for both. Their profile size can change, but independent SQL icons are independent data stores, not automatic replicas. Application, worker, gateway and load-balancer instances scale their supported slots. A queue node represents one buffer and requires instance_count=1.

## 4. Connection rules

| Source | Allowed outgoing relationship |
|---|---|
| Client | One request edge per operation to LB, gateway, app, CDN or object storage where challenge permits |
| Load balancer | One or more matching request edges to gateway/app nodes; dispatch one target |
| API gateway | One matching request edge per operation to app/CDN/object node |
| App service | One request edge per operation to SQL, cache, queue or object storage; optional invalidate edges for successful writes |
| Cache | One cache_miss edge per read operation to SQL; hit returns internally |
| SQL | No normal outgoing edge; operation result returns up the request stack |
| Queue | One or more consume edges to workers; available workers pull jobs fairly |
| Worker | Terminal notification effect in the synthetic sink |
| Object storage | Terminal get/put result |
| CDN | One cache_miss edge for object reads to object storage; hit returns internally |

Write operations cannot terminate at a cache/CDN. SQL/cache support key operations; object storage/CDN support object operations; queues/workers support job operations. A queue cannot satisfy synchronous persistence requirements. An unreachable terminal, incompatible operation kind, invalid edge kind or ambiguous operation route is a validation error. Disconnecting a billable node does not remove its cost. A synchronous invalidation edge targets all instances of its cache node and awaits all acknowledgements; this bounded built-in behavior is permitted even though general user-authored fan-out/join programs are not.

## 5. Policy controls

- **Gateway rate limit:** token refill rate and bucket size; rejected legitimate requests count against challenge success.
- **Application dependency timeout:** default 2,000 ms; cannot exceed the operation's remaining deadline. Optional max retries 0–2; retry delay 100 ms with exponential growth and seeded full jitter. Retry only operations marked retry_safe in the challenge. Writes require a modeled idempotency contract before retries can be enabled; v0.1 graded write operations disable retries.
- **Cache:** TTL from 1–120 s, profile capacity, invalidation off/synchronous. Versioned profiles set allowed assessment ranges.
- **Queue/worker:** max attempts 1–3, visibility lease 1–10 s, deduplication on/off. Failed/exhausted jobs enter a saved failure list; a separate DLQ block is expansion scope.
- **Load balancer:** round-robin routing and the fixed health-check settings above. Least-connections is later scope.
- **Network:** challenge-owned defaults in assessed mode. Learner-custom link capacity is exploratory unless the challenge explicitly exposes a priced preset.

## 6. Trace vocabulary

Every supported component emits applicable events from: arrived, queued, service_started, service_finished, downstream_started, downstream_finished, cache_hit, cache_miss, cache_evicted, cache_invalidated, write_committed, enqueue_accepted, job_leased, job_released, job_effect, job_acknowledged, timed_out, rejected, fault_started, fault_ended, response_sent, terminal_outcome.

Events reference IDs, logical time, parent request/attempt/job IDs and the affected node/edge. The UI never fabricates these events to improve the animation.

## 7. Major expansion components

| Group | Planned additions | Required modeling work before assessment support |
|---|---|---|
| Networking | DNS, regional routing, network partition, explicit region/zone | DNS caching/TTL, shared failure boundaries, partition duration and response behavior |
| Compute | Serverless functions, autoscaler | Cold start, provisioning delay, limits and time-varying cost |
| Databases | Read replica, sharded store, document/key-value store | Replication delay, key placement, read/write routing, consistency contract |
| Search and AI retrieval | Search index, vector index | Ingestion lag, lookup workload; relevance needs a separate dataset/evaluator |
| Messaging | Pub/sub, event stream, DLQ | Fan-out, offsets, ordering, consumer lag, replay and poison messages |
| Real-time | WebSocket gateway | Connection occupancy, reconnects, fan-out and ordering |
| Dependencies | Payment API, email/SMS API, external API | Response profiles, quotas, partial failures and idempotency |
| AI serving | Model endpoint, embedding service, model router | Token workloads, prefill/decode assumptions, concurrency, fallback and pricing |
| Reliability policies | Circuit breaker, bulkhead, failover | State transitions, half-open probes, capacity isolation and failure semantics |
| Security/operations | Auth policy, WAF policy, observability collector | Explicit rule checks initially; no security certification from icons |

Regions/zones are container boundaries; retry/replication policies are settings where possible. Do not force every concept into a separate canvas box.
