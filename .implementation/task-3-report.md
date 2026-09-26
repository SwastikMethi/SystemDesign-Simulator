# Task 3 — local API, jobs, storage and coach

Implemented the FastAPI application and checked-in `backend/openapi.json` (29 routes). `backend.main:app` serves `/api/v1`, and serves `frontend/dist` from the same origin when built. The frontend contract is `.implementation/http-interface.md`.

## RED / GREEN

- RED: `tests/test_coach.py::test_declared_calculation_and_worded_number_are_checked` failed because declared calculations were rejected as bare digits. GREEN: evidence operands are validated for numeric values, matching type/unit/metric suffix and nonzero samples, then rendered by the server. Unsupported spoken quantities fail.
- RED: `tests/test_api.py::test_cost_objective_keeps_ties_visible` failed because ranking had no tie representation. GREEN: equal-cost passing alternatives return `tied_run_ids` and no unique winner.
- Full suite after real worker integration and comparison changes: `.venv/bin/python -m pytest -q` → **49 passed in 104.36 s**. Targeted checks after the additive outcome route, SPA serving, and comparison progress guard: **5 passed in 5.92 s**. `uv lock --check` passed. OpenAPI generation asserts `JobOutcome.accepted_us` and `RunManifest.comparison_id` are present.

## Integration evidence

- Real API journey: create a reference design; assess the full product-catalogue workload; observe completed/pass and progress; compare a failure design; retain the losing candidate and deterministic cost/requirement/latency differences; protect baseline deletion while referenced; clear completion when the referenced run is later deleted. The integration check passed and took about 89 s in isolation.
- Preview run creates immutable workload, outcome, snapshot, trace and assessment artifacts. Export/import round trip passed. An imported preview bundle ran as an ungraded experiment, while assessment reuse was rejected. A full canonical imported assessment bundle was accepted for explicit fresh assessment; the test canceled that extra run after verifying its trusted-workload flag. Arbitrary or modified imports remain experiment-only.
- Coach provider calls require explicit `{consent:true}` and server-side configuration. A mocked provider response with an unsupported numeric claim was saved as a failed, inspectable review with raw response and validation error; no credential appeared in the response. No live provider key was available for a live smoke test.

## Boundaries and limits

- `backend.simulation.run_case` and `backend.assessment.assess_suite` execute only in a spawned child. One child runs at a time through a bounded queue; the API process owns statuses, idempotency, cancel requests, restart interruption, SSE/resync and final manifests.
- Saved design revisions and workload/case artifacts are immutable. JSON manifests are atomic; the final run manifest follows case artifact writes. IDs, paths, ZIP entries and decompressed size are validated. Imports never copy stored verdicts into progress. A passing comparison candidate remains isolated until the learner explicitly runs an assessment outside the comparison.
- The coach uses one direct OpenAI-compatible structured Chat Completions request with a 30 s budget and at most one transient retry. Local validation rejects unknown evidence, unsupported quantities, verdict claims and invalid patches. Missing provider usage/cost stays null.
- Default local launch is `uvicorn backend.main:app --host 127.0.0.1 --port 8000` with one worker. API host/origin checks accept loopback only. `AISD_DATA_DIR` and optional AI settings are documented in `.env.example`.

## Review fix round 1

- RED: five focused regressions failed on the original implementation: progress fell back to an isolated passing comparison candidate; malformed imported workload JSON returned 500 after saving a design; coach text asserted an overall pass; malformed provider content lost its raw response; the API could not preserve that raw content in a failed review.
- GREEN: completion awards and deletion fallback share one eligibility check. ZIP entries and JSON are read and validated before any design/workload/evidence write; generated import directories are cleaned up if a write fails. Overall verdict claims are rejected while requirement-level observations remain available. Provider parse errors carry raw content and validation metadata into the saved failed review.
- Comparison creation now compares the engine's `fault_bindings` for every frozen workload case. Candidates that remap a required non-clear fault are retained as rejected proposals with a case-specific reason; cache/CDN clear faults remain topology-flexible.
- `.venv/bin/python -m pytest tests/test_api.py tests/test_coach.py -q -k 'not assessment_comparison_preserves_loser_and_progress'` → **14 passed, 1 deselected, 1 warning in 7.92 s**. The review paths and fault-binding integration were directly covered; the long baseline/comparison numerical run was previously green.
