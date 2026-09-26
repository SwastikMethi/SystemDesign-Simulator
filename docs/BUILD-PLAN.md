# AI System Design Simulator implementation

Approved execution plan, 26 September 2026. The source documents in this directory own product, numerical, component, challenge, UI, coach, and API semantics. The conversation approved the full M0–M7 scope and an OpenAI-compatible server-side coach.

## Global constraints

Local single-user application; React/TypeScript/Vite/React Flow; FastAPI/Pydantic/SimPy; versioned JSON and compressed JSONL. No accounts, database, cloud provisioning, custom model training, arbitrary code execution, fake metrics, or AI grading.

Time is integer microseconds. Same-time priority is faults/state changes, completions/commits, expiry, arrivals/dispatch, snapshots. Original requests have one terminal outcome. Workloads are precomputed and reused. Numerical hashes exclude labels and positions. Assess each scenario at seeds 101, 202, 303, 404, 505; 60 s warmup, 300 s measurement, 30 s drain. Preview is steady seed 101 with 10/60/30 s. Cases cap at 100,000 original arrivals and 2,000,000 events. Designs cap at 25 nodes/60 edges. Comparisons cap at two candidates.

## Task 1: Contracts and authored content (M0)

Create Python project with uv lockfile and Pydantic schemas, all immutable profiles, all five authored challenge JSON files and initial/reference/failure/budget designs. Examples must validate without changing authored thresholds. Add draft versus runnable validation, compilation with complete typed routes, profile constraints, dataset identity, numerical hashes, and bounded settings. Drafts may be saved with incomplete routes; assessment requires full route validation. Add canonical workload generator and bundle hash utilities. No numerical result may be marked verified until engine execution. Tests cover strict schema/route validation, seed repeatability, uniform/Zipf distributions, segment boundaries, hash exclusions, profile costs and invalid patches. Document schema clarifications in DATA-API-SPEC and owning docs. Output report .implementation/task-1-report.md.

## Task 2: Simulator, assessment, numerical fixtures (M1/M3/M6 engine)

Implement all ten modeled components with explicit event priorities, network serialization, finite FIFO queues/slots, request deadlines/late work, caches/invalidation races, store histories, object capacity, queue leases/redelivery/deduplication, all three fault types, LB checks, gateway limits and allowed service retries. Persist exact bounded outcomes, one-second snapshots, first failure evidence and at most 100 detailed traces per case. Implement all deterministic metrics, four assessment statuses, per-case evaluation and comparison/ranking. Provide reusable headless run_case/run_suite interface and fixture runner. Verify all five challenges' passing/failing/budget fixtures across all scenarios/seeds and benchmark catalogue. No threshold relaxation. Tests must prove exact timing, conservation, races, insufficient evidence, repeatability and scoring. Report .implementation/task-2-report.md.

## Task 3: Local application API, jobs, storage, coach (M2/M4/M5/M7 backend)

Implement API contract plus history, snapshots, safe deletion and import APIs. Atomic immutable files; process-isolated sequential simulation jobs; bounded job queue; SSE/resync; cancel/restart; idempotency; version manifests. Run creation can reuse only compatible trusted workload bundles. Comparisons freeze baseline, validate up to two patches or saved revisions, preserve losers and expose objective/differences. Coach uses configurable OpenAI-compatible JSON-schema Chat Completions adapter; 30 s request budget with one transient retry; evidence references and server-rendered numerical placeholders; review and patch validation. No LLM mock in production. Imported/exported ZIP evidence has path/size/secret protections and cannot itself award completion. Tests cover complete API journeys, failures, patch immutability, prompt injection, imports and local-only security. Generate OpenAPI for frontend. Report .implementation/task-3-report.md.

## Task 4: Interactive frontend (M2/M4/M5/M6/M7 UI)

Create professional dark workspace matching UI-UX-SPEC. Five challenge library, first-time guidance, fully editable React Flow graph, profiles/policy inspector, labels/routes, keyboard node/edge forms, undo/redo, duplicate/delete, validation, immutable save/drafts, preview/assessment controls, SSE progress/cancel/reconnect, requirements-first results, evidence drilldown, playback with speed/step/reduced-motion/100-marker cap, comparison diff with explicit adoption and losing candidates, coach opt-in disclosure/hints/reviews, history/export/import/delete. Real API data only. Handle empty/error/provider-unavailable states. Scope styles and use CSS/SVG; system sans serif and tabular numbers. Responsive at 1440x900 and 1024x768; viewing on mobile. API types generated from OpenAPI. Vitest behavioral tests plus real-server Playwright journeys. Report .implementation/task-4-report.md.

## Task 5: Integration and release (M7)

Run complete meaningful tests, fixture verification and numerical benchmark. Inspect rendered UI in browser and keyboard/reduced-motion behavior. Test restart, replay without model calls, export/import/reproduction, full learner journey. Fix all blocking defects, update README with exact commands and measured limits, preserve report/evidence and one demonstration recording. Final reviewer independently inspects all changes. PRD P01–P12 must be mapped to concrete evidence. No unverified usability study or live-provider claim.

## Contract rulings approved in the plan

- Save schema-safe drafts; require full compilation to run.
- Add history/deletion, recorded snapshot retrieval, multipart imports and compatible workload reuse APIs.
- Patch settings include profile_id, instance_count and supported policy settings.
- Coupled operations share one logical store; per-key versions advance at commit; freshness observes client completion.
- Fault selectors preserve stable logical IDs; type-wide cache clear is a no-op for a cacheless design.
- Optional demand shift rotates Zipf popularity by 500 of the 1,000 catalogue keys at measurement second 150; it cannot award completion.
- AI numeric claims render from structured evidence/calculation references.

## Review focus

Deadline/fault ties; stale fills and late writes; duplicate job effects; hash/version compatibility; archive/prompt/path attacks; UI confusing old results with a changed design. Every review must check spec compliance and code quality. Every milestone requires executed evidence, not assumed success.
