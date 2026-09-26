# Challenge and curriculum specification

AI System Design Simulator · authored content v0.1

## 1. Authoring requirements

Each challenge contains a stable ID/version, plain-language brief, concepts, allowed components/policies, initial data, operations, workload cases, hard requirements, optional experiments and fixture references. Workloads and rubrics are authored and reviewed before release; AI may explain them but cannot secretly change them.

Every released challenge needs at least one passing fixture, one failure fixture for its main lesson, and an overprovisioned fixture that fails its budget. The fixtures must be executed by the implemented engine before being labeled verified. This package proposes content and thresholds; it does not assert that those fixtures have already passed.

Machine-readable definitions and proposed initial/reference/failure/budget designs live in `content/challenges/` and `content/fixtures/`. Compilation and budget checks alone do not verify their numerical outcomes.

The five curriculum challenges use the assessment warmup/measurement/drain lengths and five seeds in SIMULATION-SPEC. The introductory walkthrough below explicitly uses a shorter assessment. Fixed-rate scenarios apply through warmup and measurement. Burst scenarios use normal rate in warmup, 0–120 s and 180–300 s measurement, and peak rate from 120–180 s. Workload payloads and per-seed traces are stored for comparison reuse.

## 2. Common grading rules

- At least 99.5% original request success per operation, scenario and seed unless the brief specifies a different threshold.
- p95 thresholds apply to successful responses and are always shown with success rate; failures cannot be hidden.
- All successful data reads must reference the correct key and a version that exists in the committed history.
- Single-key acknowledged writes must be present in the logical persistent store at the acknowledgement point. Retaining an old version after a later valid overwrite is not required.
- Original arrivals determine denominators, including rejected or timed-out requests.
- Cost budgets use total provisioned credits/hour, not real currency.
- Unsupported required capabilities make a challenge unavailable, not automatically passed.

## 3. Initial challenge definitions

### Walkthrough — Your first design

ID: first-design; version 0.1.0; level 1 in the data contract, presented separately as a walkthrough above the five curriculum challenges. Allow 3–5 minutes to learn the editor, requirements, results and saved work through the existing Guide checklist.

- Starter: Client → App → Database, using `app.small.v1` and `sql.small.v1`; only client, app service and SQL database components are available.
- Operation: read_note 100%; 1 KiB request/response payloads; 2 s deadline; 1,000 notes at version 0 with uniform key selection.
- Assessment: one required steady scenario at 120 rps, seed 101, 10 s warmup, 30 s measurement and 5 s drain. Preview keeps the existing 10/60/30-second protocol and cannot complete the task.
- Targets: success ≥99.5%, successful read p95 ≤250 ms, each with at least 100 measured samples; total cost ≤50 fictional credits/hour.
- Lesson: preview the failing starter, inspect R02 evidence, then change only Database's Profile to `sql.medium.v1` and assess again. This increases provisioned cost from 25 to 45 credits/hour while improving service capacity.
- Initial and failure fixtures use the undersized database. The reference uses medium SQL; the budget fixture uses large SQL and costs 85 credits/hour.
- Completion and saved evidence use the regular assessment/history mechanisms. Instructions remain available through Guide; there is no separate step-tracking state or AI dependency.

### C01 — Team notes

ID: team-notes; level 1. Learn basic request/response flow and persistence.

Brief: Build a small service where a team reads and updates notes. An update must be stored before the user is told it succeeded.

- Operations: read_note 80%, write_note 20%; 1 KiB request/response payloads; 2 s request deadline.
- Initial data: 1,000 notes at version 0; uniform key selection; writes assign a new logical version.
- Cases: steady at 10 rps; burst at 10→40 rps.
- Targets: common success rule; p95 read <=250 ms and write <=400 ms; acknowledged write persistence; zero invalid reads; budget <=50 credits/h.
- Suggested components: client, app, SQL. Other supported components are optional and costed.
- Failure lesson: a write path ending at cache or queue is not the required persistence path.
- A passing solution need not contain a load balancer or cache.

### C02 — URL lookup service

ID: url-shortener; level 2. Learn read-heavy access and caching.

Brief: Serve redirects from existing short codes and create new short-code mappings. The unique-code creation algorithm is supplied by the workload and is not graded.

- Operations: resolve_code 98%, create_code 2%; request 256 B, response 512 B; 2 s deadline.
- Initial data: 10,000 mappings; Zipf popularity exponent 1.2 for reads; create operations receive unique new keys.
- Cases: steady 50 rps; burst 50→250 rps.
- Targets: common success rule; p95 resolve <=150 ms and create <=400 ms; correct mapping; acknowledged creation persistence; budget <=100 credits/h.
- Lesson: lowering repeated read traffic to a constrained store can matter more than adding application handlers.
- Scope limit: no uniqueness-algorithm, malicious URL or custom-domain assessment.

### C03 — Product catalogue

ID: product-catalogue; level 3. Learn burst handling, cache invalidation and freshness.

Brief: Serve product details while editors change those details. The site must remain responsive during a traffic spike and cannot serve old product versions indefinitely.

- Operations: read_product 95%, write_product 5%; request 512 B, read response 2 KiB, write response 256 B; 2 s deadline.
- Initial data: 1,000 products at version 0; read/write keys from a Zipf distribution with exponent 1.2.
- Cases: steady 40 rps; burst 40→200 rps; cold_cache with the same burst and clear-all-cache event at measurement t=120 s.
- Targets: common success rule; p95 read <=200 ms and write <=400 ms; zero invalid reads; zero freshness violations with 5 s allowance; acknowledged write persistence; budget <=100 credits/h.
- Optional assumption experiment: shift the popular key set halfway through the run. The experiment does not alter the completion badge.
- Suggested comparisons: additional app capacity, a cache with correct invalidation, larger SQL profile. Neither approach is automatically preferred.
- Canonical machine-readable definition: examples/catalogue-challenge.json.

### C04 — Photo delivery

ID: photo-delivery; level 4. Learn byte transfer, object storage and content caching.

Brief: Upload immutable photos and serve them repeatedly. Large content should be evaluated using bytes and link capacity as well as request count.

- Operations: get_photo 95%, put_photo 5%; uploads and returned photos are 1 MiB; non-payload requests/responses are 512 B; deadline 10 s.
- Initial data: 100 objects of 1 MiB; Zipf exponent 1.2 for reads; uploads have unique object keys. Stored bytes include initial data and successful uploads.
- Cases: steady 20 rps; burst 20→80 rps; cold_cdn uses the burst and clears CDN entries at t=120 s.
- Targets: common success rule; p95 get <=750 ms and put <=2,000 ms; correct object identity/size; acknowledged upload persistence; no capacity-exceeded successful writes; budget <=100 credits/h.
- A direct client-to-object-store upload is permitted. CDN supports immutable reads only in v0.1.
- Scope limit: image transformation, metadata indexing, signed URLs and mutable-object invalidation are not assessed.

### C05 — Notification processing

ID: notifications; level 5. Learn asynchronous acknowledgement, backlog and completion deadlines.

Brief: Accept notification jobs quickly and deliver them to the synthetic recipient sink within ten seconds. Returning Accepted is not the end of the task.

- Operation: enqueue_notification 100%; 512 B payload, 256 B acknowledgement; user acknowledgement deadline 2 s; job deadline 10 s from original arrival.
- Initial data: empty queue and delivery ledger; unique job IDs supplied by the workload.
- Cases: steady 20 rps; burst 20→100 rps.
- Targets: common request success rule; p95 acknowledgement <=150 ms; >=99% of original enqueue intents produce their first correct effect within 10 s; zero duplicate effects; budget <=80 credits/h.
- Suggested components: client, app, queue and workers. Scale worker slots only when supported by backlog evidence.
- Scope limit: no real email/SMS provider, queue-node crash durability or exactly-once network guarantee.

## 4. Full ranked expansion

After the initial five, introduce resilient API (application failure), flash-sale inventory, chat, social feed, payment workflow, global application, and AI inference platform. This is a curriculum proposal; advanced challenges must wait for their state/failure models and evaluators.

Rank by new concepts and interacting constraints, not user count alone. Attach prerequisites such as caches, queues, consistency or retries. Let learners browse later concepts without claiming that an unavailable simulation is playable.

## 5. Hints, references and learner progress

Hint 1 asks a diagnostic question. Hint 2 points to a relevant metric/path. Hint 3 proposes an experiment. Reference approaches become visible after an attempt or an explicit reveal. Using hints does not invalidate a completed exercise; record their use for the learner, not a public ranking.

Completion is tied to challenge/rubric/profile versions and a passing assessed design revision. Later edits show Unassessed changes until rerun. Upgrading content leaves historical completion attached to its old version rather than silently rescoring it.

## 6. Content review checklist

Confirm that the brief, operations and metric denominators agree; all required behavior is supported; failure fixtures teach the intended concept; at least one feasible configuration fits the budget; references do not imply one mandatory topology; sample counts are sufficient; and the language explains assumptions without claiming production capacity.
