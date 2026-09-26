# Module integration boundary

Frozen coordinator handoff after contract implementation. Amendments must be communicated to the owning agents and recorded here. This enables independent work in disjoint modules; final integration must run real components together.

## Engine → application service

`backend.simulation.run_case(challenge: Challenge, design: DesignRevision, workload: WorkloadCase, *, on_progress=None, should_cancel=None) -> CaseArtifacts`

`CaseArtifacts` contains `result: CaseResult`, `outcomes: list[RequestOutcome]`, `jobs: list[JobOutcome]`, `snapshots: list[Snapshot]`, `traces: list[Trace]`. Artifact members are Pydantic models supporting `model_dump(mode='json')`. Engine owns `Snapshot`, `Trace` and `TraceEvent` schemas. `Snapshot` exposes `time_us` and `nodes` keyed by node ID, containing numeric `busy_slots`, `available_slots`, `queue_depth` and applicable `cache_hits`, `cache_misses` or `backlog`. `Trace` exposes `trace_id`, `request_id`, `operation_id`, and `events`; events expose `time_us`, `event`, `node_id`, `edge_id`, `request_id`, `attempt_id`, `job_id`, and `details` where applicable.

`on_progress` receives coarse dictionaries with `time_us` and optional `snapshot` serialized object. It does not perform network I/O itself. `should_cancel()` returns a boolean and is checked between bounded batches of events. Canceled/capped work preserves available evidence and cannot pass.

`backend.assessment.assess_suite(challenge: Challenge, case_results: list[CaseResult], *, mode='assessment') -> AssessmentResult`. Completeness checks against all required scenarios/seeds in assessment mode. Preview/experiment cannot set completion. Aggregates derive from case evidence, never model output.

The API process writes files and owns job statuses/version manifests. It executes `run_case` only inside the simulation child process, one case at a time, and writes each completed case immediately. Engine can expose a headless `run_suite` convenience runner for fixtures; API orchestration does not depend on it. Backend storage can persist request/job outcomes as separate tagged records in one JSONL journal.

## HTTP → frontend

DATA-API-SPEC owns paths and field names. API schemas/OpenAPI are authoritative. Before frontend work begins, API implementer publishes the expanded endpoint shapes here or in a checked-in OpenAPI file. Frontend may build isolated components using test-only fixtures, but production paths must use actual API responses. Never ship fake simulation or model output.

All case metrics use `MetricValue {value, unit, sample_count, reason}`. The exact existing Pydantic schemas must be used, not independent frontend approximations. Baseline/candidate differences and ranking are computed on the server.

## Ownership during independent work

- Engine: backend/simulation/, backend/assessment/, backend/fixtures.py, numerical tests and fixture corrections with coordinator notification.
- Application service: backend/api/, backend/storage/, backend/coach/, backend/main.py, API/storage/coach tests and API documentation.
- Frontend: frontend/ and root frontend launcher/config only after API shape publication.
- Coordinator: progress, task/review packaging, acceptance evidence and integration instructions. Shared contracts are modified only after coordination.

Dependencies/install manifests are changed by one nominated owner at a time. Git commits stage explicit owned paths, never the whole working tree. Workers do not revert or stage each other's work.
