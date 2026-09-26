# Data and API specification

AI System Design Simulator · schema version 1

## 1. Data objects

| Object | Required content |
|---|---|
| Challenge | challenge_id, version, title, level, brief, concepts, allowed_component_types, operations, initial_data, workload, scenarios, requirements, budget |
| Design revision | design_id, revision_id, schema_version, challenge_id/version, nodes, edges, created_at, parent_revision_id |
| Node | id, type, label, profile_id, instance_count, settings, position |
| Edge | id, source, target, kind, operation_ids; network overrides only where the challenge permits |
| Workload bundle | bundle_id, challenge_version, seeds, scenario traces, initial state, content hashes, generator version |
| Run | run_id, mode, execution_status, design reference, version/hash manifest, case IDs, assessment_status, timestamps and artifact paths |
| Case result | scenario_id, seed, execution_status, operation metrics, node metrics, sample counts, requirement outcomes, trace references |
| Request outcome | original request ID, operation ID, arrival/deadline/terminal times, terminal status, value/version result, correctness/freshness flags |
| Job outcome | job ID, original enqueue request ID, attempts, acknowledgement/effect times, terminal state, duplicate count |
| Evidence item | evidence_id, type, unit, value, scope, sample_count, artifact reference |
| Coach review | review_id, run_id, provider/model metadata, prompt version, summary, findings, candidate patches, limitations |
| Comparison | comparison_id, baseline_run_id, workload_bundle_id, candidate revisions/runs, objective, compatibility hashes, differences |

All IDs are application-generated opaque strings, except stable authored challenge/profile/operation IDs. All timestamps are UTC ISO 8601. Durations carry unit suffixes; logical event time is `time_us`. Fractions use 0–1 internally. No NaN or Infinity in JSON; unavailable numerical fields are null with a reason.

## 2. Challenge fields

An operation defines `id`, `kind` (read_key, write_key, get_object, put_object, enqueue_job), `weight`, `request_bytes`, `response_bytes`, `deadline_ms`, and `retry_safe`. Job operations also define `job_deadline_ms`; freshness-sensitive reads define `freshness_allowance_ms`. Object upload bytes are request bytes; object download bytes are response bytes.

`workload` includes `warmup_seconds`, `measurement_seconds`, `drain_seconds`, `assessment_seeds`, and `key_distribution`. Each scenario has `id`, `required`, `warmup_rps`, measurement-relative `rate_segments` and `faults`. A segment has `start_s`, `end_s`, `rps`. Require full nonoverlapping coverage of the measurement interval.

Requirements have `id`, `description`, `metric`, `operation_ids`, `scenario_ids`, `operator`, `threshold`, `unit`, `min_samples`, and `severity`. Evaluate each listed operation separately unless the metric explicitly describes the original combined cohort, such as total cost. Empty operation_ids means system scope. See SIMULATION-SPEC for aggregation and statuses.

Canonical metric identifiers: `success_rate`, `response_p95_ms`, `response_p99_ms`, `invalid_read_count`, `freshness_violation_rate`, `acknowledged_write_missing_count`, `job_deadline_completion_rate`, `duplicate_effect_count`, `cost_credits_per_hour`. Additional diagnostic metrics may exist without becoming completion requirements.

## 3. Design validation

Require known schema/profile/challenge versions, unique IDs, finite positions and parameters, valid edge references, exactly one workload-source client, supported cardinalities and complete operation routes. Validate per-type instance constraints and profile settings. Reject arbitrary fields instead of ignoring a misspelled capacity or timeout.

Draft validation permits zero clients and missing routes so a learner can save an empty or partial canvas. It still rejects unknown fields, profiles, settings, duplicate IDs, broken edge references, and more than one client. Compilation for preview or assessment requires exactly one client and a complete compatible route for every operation. Each route records request, cache-miss, invalidation, and consume edges separately; responses reverse the request stack.

Profile instances are capped at 32 per node; SQL, object storage, queue and client remain single-instance logical resources. Assessed settings are allowlisted and bounded. Patch `set_node_setting` can update `profile_id` or `instance_count` as well as supported policy keys. An assessment may exceed a budget and receive a failed budget requirement; budget is graded rather than rejected at compilation.

Values in examples are proposed specification fixtures. Implementation must publish machine-validated Pydantic/JSON Schemas and keep the examples valid against them. Node positions are UI data and do not affect the numerical design hash. Names affect labels and prompts but not routing or physics.

The numerical hash includes node IDs, types, profiles, instance counts, settings, edge IDs, endpoints, kinds, and operation scopes. It excludes labels, positions, revision IDs, and timestamps. Export JSON Schemas with `python -m backend.content content/schemas`. `content/fixtures/{challenge_id}/{initial|reference|failure|budget}.json` are authored hypotheses until executed across all required cases.

Node, edge and operation-scope array ordering does not affect the numerical hash or execution. Route compilation uses canonical edge-ID order, including participating fault-role selection. Engine version `0.1.1` identifies this corrected behavior; comparisons reject baselines recorded with the earlier engine.

JSON Schemas describe canonical serialized values. At the Pydantic input boundary, ordinary integer fields accept losslessly convertible integer strings (for example, `"instance_count":"1"`) and normalize them to integers before storage and hashing. Strict component policy settings retain their explicit type validation. This accepted boundary normalization does not change datetime parsing or general number coercion.

The workload generator precomputes integer-microsecond original arrivals and stable payload IDs. Existing-key reads and product/note writes sample the authored uniform or Zipf distribution. `create_code` and `put_photo` receive unique new keys; this is an authored operation policy rather than a rule for all writes. Store versions advance at commit. Optional `hot_key_shift` rotates Zipf popularity by half the catalogue at measurement second 150 and cannot award completion.

## 4. Local artifact layout

| Path pattern under configured data directory | Contents |
|---|---|
| challenges/{challenge_id}/{version}.json | Installed authored challenge definition |
| designs/{design_id}/{revision_id}.json | Immutable design revision |
| workloads/{bundle_id}/manifest.json | Workload generator version and hashes |
| workloads/{bundle_id}/{scenario_id}-{seed}.jsonl.gz | Original arrivals, operation payloads and scheduled faults |
| runs/{run_id}/manifest.json | Status, versions, hashes, evidence references |
| runs/{run_id}/cases/{case_id}/outcomes.jsonl.gz | Original request/job outcomes |
| runs/{run_id}/cases/{case_id}/snapshots.jsonl.gz | Bounded replay/metric snapshots |
| runs/{run_id}/cases/{case_id}/traces.jsonl.gz | Selected full traces, including first failures |
| runs/{run_id}/assessment.json | Per-case requirements and overall outcome |
| runs/{run_id}/reviews/{review_id}.json | Saved AI review and validation metadata |
| comparisons/{comparison_id}.json | Baseline/candidate links and computed differences |
| progress.json | Challenge completion references, not duplicated metric truth |

Paths never come directly from user labels. Restrict identifiers to safe generated values. Write files atomically, and finalize the manifest last. Compression is an implementation detail, not a change to event semantics.

## 5. Version manifest

Every run includes engine_version, assessment_version, profile_version, challenge_id/version, workload_generator_version, design_hash, workload_hash and run_config_hash. Include platform/runtime versions in exports for diagnostic reproduction. The prompt/model version is recorded separately because it cannot alter engine results.

Metric rebuilding reads stored outcomes using the original assessment version where available. A changed rubric produces a new derived assessment ID; it cannot overwrite a historical result. If required evidence is absent, explain that rebuilding that metric is unavailable.

## 6. REST endpoints

Base path `/api/v1`. All POST bodies use validated JSON.

| Method and path | Purpose / response |
|---|---|
| GET /health | Backend, engine version, AI configured boolean; no credentials |
| GET /catalogue | Component types, profiles, settings and support labels |
| GET /challenges | Challenge summaries and local progress |
| GET /challenges/{id}?version=... | Full authored definition |
| POST /designs | Create design and first revision |
| GET /designs/{id} | Metadata and revision references |
| POST /designs/{id}/revisions | Validate/save immutable revision with parent_revision_id |
| GET /designs/{id}/revisions/{revision_id} | Exact revision |
| POST /designs/validate | Validation findings without saving |
| POST /runs | Freeze inputs, enqueue preview or assessment; 202 with run_id |
| GET /runs/{id} | Manifest, progress and available artifact references |
| GET /runs/{id}/events | SSE progress, snapshot and terminal-status events |
| POST /runs/{id}/cancel | Idempotent cancellation request |
| GET /runs/{id}/results | Deterministic summary and per-case requirement outcomes |
| GET /runs/{id}/cases/{case_id}/traces/{trace_id} | Selected detailed trace |
| POST /runs/{id}/reviews | Request AI review; 202 with review_id |
| GET /runs/{id}/reviews/{review_id} | Review status and validated content |
| POST /designs/{id}/guidance | Explain or Hint for a saved revision; explicit consent; 202 with guidance_id |
| GET /designs/{id}/guidance/{guidance_id} | Saved guidance, authored references, provider metadata and errors |
| POST /comparisons | Baseline plus candidate patches/revisions; 202 with comparison_id |
| GET /comparisons/{id} | Compatible run links, status, computed differences and objective |
| POST /exports | Export selected designs/runs/comparison; returns local download token |
| GET /exports/{token} | Download evidence ZIP without secrets |

Example run input:

```json
{
  "design_id": "design-example",
  "revision_id": "revision-001",
  "challenge_id": "product-catalogue",
  "challenge_version": "0.1.0",
  "mode": "assessment"
}
```

Assessment seeds/cases come from the challenge, not editable run inputs. Sandbox/optional experiments receive a distinct mode/label and cannot set a completion badge.

## 7. Status, progress and errors

Execution statuses: queued, running, completed, canceled, failed, interrupted. Assessment statuses: pass, fail, not_evaluated, incomplete. A completed simulation may have a failed assessment. An AI error is not a simulation failure.

SSE payload fields: event_id, run_id, type, case_id when applicable, progress, snapshot when applicable, and emitted_at. Use monotonic event IDs. Reconnect with Last-Event-ID when the bounded buffer still contains it; otherwise emit a resync event instructing the client to fetch the current manifest/snapshot. Disk outcomes and final manifests are authoritative, not the SSE stream.

Use idempotency keys on run/review/comparison creation to prevent double-click duplicates. Reusing a key with a different body returns conflict. Standard errors include code, message, field_errors, node_ids/edge_ids and retryable. Use 422 for invalid designs, 409 for stale revisions/compatibility conflicts, and 503 for an unavailable provider.

## 8. Export contents

An evidence export contains challenge, design revisions, profiles, workload manifest/traces, engine/rubric versions, results, selected traces, comparison and an optional validated review. Add a plain-language limitations note. Exclude credentials, environment files, raw provider authorization headers and unrelated local data. Exported evidence does not need to include an application's source code.
