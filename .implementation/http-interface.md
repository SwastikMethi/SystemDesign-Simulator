# HTTP integration contract

Machine-readable contract: [`backend/openapi.json`](../backend/openapi.json). Runtime OpenAPI is `/openapi.json`. The API prefix is `/api/v1`; the local backend defaults to port 8000. Responses use exact Pydantic schemas from `backend/api/models.py` and `backend/contracts/__init__.py`.

## Core frontend flows

| Request | Response |
|---|---|
| `GET /health` | `{status, engine_version, ai_configured, ai_model}`; never a credential |
| `GET /catalogue` | `{component_types:[{type,label,purpose,profiles,settings,support_label}],profiles:[Profile]}` |
| `GET /challenges` | `{items:[{challenge_id,version,title,level,brief,concepts,support_status,progress}]}` |
| `GET /challenges/{id}` | Full `Challenge` |
| `GET /challenges/{id}/fixtures/{initial\|reference}` | Full `DesignRevision`; reference is an explicit reveal |
| `POST /designs` | Body `{challenge_id,challenge_version,nodes,edges}` → 201 `{design_id,revision_id,revision}` |
| `POST /designs/{id}/revisions` | Body `{parent_revision_id,nodes,edges}` → 201 `{design_id,revision_id,revision}` |
| `POST /designs/validate` | Body same as create → `{valid_draft,runnable,findings,design_hash}` |
| `POST /runs` | Body `{design_id,revision_id,challenge_id,challenge_version,mode,workload_bundle_id?,experiment_scenario_id?,experiment_seed?}` → 202 `{run_id,execution_status:"queued",assessment_status:"not_evaluated"}` |
| `GET /runs/{id}` | `RunManifest`: run, design, challenge, workload and version/hash IDs, statuses, progress, cases, artifact refs |
| `GET /runs/{id}/results` | `{run_id,assessment:AssessmentResult|null,cases:CaseResult[]}`; `assessment.case_results` is the authoritative complete assessed suite, `cases` also exposes partial runs |
| `GET /runs/{id}/cases/{case_id}/snapshots` | `{case_id,items:[Snapshot]}` |
| `GET /runs/{id}/cases/{case_id}/outcomes` | `{case_id,requests:[RequestOutcome],jobs:[JobOutcome]}`; job outcomes include `accepted_us` |
| `GET /runs/{id}/cases/{case_id}/traces/{trace_id}` | `Trace` |
| `GET /runs/{id}/events` | SSE event `{event_id,run_id,type,case_id,progress,snapshot,emitted_at}`; send `Last-Event-ID`; `resync` means refetch manifest and snapshots |

`MetricValue` is `{value,unit,sample_count,unavailable_reason}`. All case metrics and assessment verdicts come from the engine/rubric; no frontend calculation should award completion. Preview and experiment modes cannot pass the assessment. POST creation routes accept `Idempotency-Key`.
Comparison candidate run manifests carry `comparison_id`; a passing comparison candidate requires a separate learner-selected assessment before updating challenge progress.

## Saved evidence and experiments

| Request | Response |
|---|---|
| `GET /collection` | `{items:[{id,kind,title,challenge_id,created_at,status}]}` |
| `DELETE /designs/{id}`, `DELETE /runs/{id}`, `DELETE /comparisons/{id}` | `{deleted:true,id}`; referenced or active data returns 409 |
| `POST /runs/{id}/snapshots` | Body `{title,case_id,time_us}` → 201 `SavedSnapshot` |
| `GET /snapshots`, `GET /snapshots/{id}` | `{items:[SavedSnapshot]}` and one `SavedSnapshot` |
| `DELETE /snapshots/{id}` | `{deleted:true,id}` |
| `POST /runs/{id}/reviews` | Body `{consent:true,comparison_id?}` → 202 `{review_id,status:"queued"}`; requires configured AI |
| `GET /runs/{id}/reviews/{review_id}` | `ReviewRecord` with status, validated findings, patches, limitations, usage/cost nullable |
| `POST /comparisons` | Body `{baseline_run_id,candidates:[{patch? or revision_id?,design_id?}]}` → 202 `{comparison_id,status:"queued"}` |
| `GET /comparisons/{id}` | `ComparisonRecord` with baseline/candidate links, objective, latency/cost differences, winner or `tied_run_ids`, and `rejected_candidates:[{index,status:"rejected",validation_error,candidate}]` |
| `POST /exports` | Body `{design_ids,run_ids,comparison_ids}` → 201 `{token,download_url}` |
| `GET /exports/{token}` | Evidence ZIP download |
| `POST /imports` | Multipart field `file` (ZIP) → `{imported_design_ids,imported_workload_bundle_ids,imported_run_ids,trusted:false}` |

Review creation is the learner opt-in to a provider call; no call occurs during simulation or comparison. A `comparison_id` review scopes evidence IDs by run, including losing candidates. Imported bundles receive new IDs and retain `trusted:false` as evidence. An exact full canonical assessment bundle may be explicitly rerun in assessment mode against installed versions; other imports run only as experiments without a completion badge. Application data comes from `AISD_DATA_DIR` (default `.data`). Provider settings are server-side `AISD_AI_BASE_URL`, `AISD_AI_MODEL`, `AISD_AI_API_KEY`.
