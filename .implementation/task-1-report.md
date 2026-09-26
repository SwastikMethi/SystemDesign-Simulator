# Task 1 — contracts and authored content

Implemented on 26 September 2026. Authored results remain hypotheses until Task 2 executes the engine; no numerical outcome is marked verified.

## RED / GREEN

- RED: `.venv/bin/python -m pytest tests/test_contracts.py tests/test_workloads.py -q` failed during collection with `ModuleNotFoundError: No module named 'backend'` before implementation.
- GREEN: `.venv/bin/python -m pytest -q` → **12 passed in 0.75 s** after implementation.
- `uv lock --check` resolved 24 packages; schema export completed successfully.
- Both published catalogue JSON examples validate with the new Pydantic contracts. All 20 installed design fixtures compile. Reference costs are 50, 82, 82, 42, and 70 credits/hour in challenge order, each within its authored budget. Budget fixtures cost 200, 232, 232, 402, and 170 credits/hour, each above its budget. These are formula checks, not simulation verdicts.

## Public interfaces

- `backend.contracts`: `Challenge`, `DesignRevision`, `Node`, `Edge`, `Profile`, `PROFILES`, `profile_for`, `ValidationFinding`, `validate_draft(design, challenge)`, `CompiledRoute`, `CompiledDesign`, `compile_design(design, challenge)`, `design_hash(design)`, `apply_patch(design, patch, challenge)`. Draft validation returns findings and permits an empty canvas. Compilation raises `ValueError` for incomplete or invalid routes. A patch creates an isolated candidate revision and compiles it before returning.
- Runtime exchange models: `RequestOutcome`, `JobOutcome`, `MetricValue`, `RequirementOutcome`, `EvidenceItem`, `CaseResult`, `AssessmentResult`.
- `backend.content`: `list_challenges()`, `load_challenge(challenge_id)`, `load_fixture(challenge_id, fixture_name)`, `export_json_schemas(directory)`. Regenerate six JSON Schemas with `.venv/bin/python -m backend.content content/schemas`.
- `backend.workloads`: `Arrival`, `ScheduledFault`, `WorkloadCase`, `generate_case(challenge, scenario_id, seed, mode='assessment')`, `workload_hash(case)`, `bundle_hash(cases)`. Arrival times are integer microseconds. Original arrivals, payload identities, keys, initial data identity and fault times are precomputed. Storage versions belong to commit-time engine semantics.

## Authored fixtures and limits

Five versioned challenges and initial/reference/failure/budget designs are installed under `content/`. Catalogue thresholds match the published example; optional `hot_key_shift` is separate from completion cases. Failure designs target rate limiting, SQL overload, stale cache, rate limiting, and worker backlog respectively. Their expected numerical failures still need engine verification. Assessment workload generation enforces the 100,000-original-arrival cap; node and edge caps are 25 and 60, and node instances cap at 32. Schema, routes, profile settings, budget formula, seed repeatability, Zipf/uniform keys, exact seed timestamps, segment boundaries, patch rejection and hash exclusions have runnable checks.
