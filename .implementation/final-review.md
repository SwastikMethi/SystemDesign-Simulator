# Final whole-branch review

Reviewer: `/root/final_review`, gpt-6-astra. Frozen range: `1b280c8..d7296cb`. Verdict: **With fixes**. No Critical findings; seven Important findings below. The reviewer inspected contracts, numerical engine, assessment, storage, API, coach, frontend, replay and tests. Broad suites were not repeated. Focused read-only Python checks reproduced the hash/outcome defect, missing coach revision, invalid patch schema and both deferred minors. The browser attempt was blocked by the sandbox and a pending approval, then aborted; modal and asynchronous UI findings are source-supported.

## Important findings (reviewer's complete correction list)

### F1 — Equivalent design hashes can produce different outage results

`backend/simulation/__init__.py:227,235`; `backend/contracts/__init__.py:502`.

Fault selection uses compiled traversal order, which depends on input edge order, while the numerical hash sorts edges. A valid URL-shortener topology with a load balancer feeding `app` and `app-b`, both connected to SQL, has the same hash after reversing its edge array. The identical application-outage workload targets `app` before reversal and `app-b` afterward. One request returns `dependency_error` versus `success`.

Identical compatibility identities therefore do not identify identical numerical behavior. Canonicalize participating-role selection independently of input ordering, retaining the disconnected-node protection. Assert identical hashes, bindings and outcomes after node/edge array permutations.

### F2 — Review response schema is incompatible with strict OpenAI Structured Outputs

`backend/coach/__init__.py:55,181`.

`Experiment.patch: dict[str, Any]` generates `{"type":"object","additionalProperties":true}`, then the adapter sends it with `strict:true`. The reviewer captured the generated schema locally. Strict structured objects require `additionalProperties:false`; this request is rejected before review generation, including responses with no suggestions. See the [official Structured Outputs documentation](https://developers.openai.com/api/docs/guides/structured-outputs).

Supply a bounded, explicit provider-facing patch schema and convert it into the existing validated patch contract. Test the actual outbound schema recursively; do not merely mock an accepted response.

### F3 — Coach lacks information required to propose an accepted patch

`backend/coach/__init__.py:221`; `backend/contracts/__init__.py:507`.

Review context contains only design `nodes` and `edges`; it omits `revision_id`. Neither the prompt nor the arbitrary-object schema explains the accepted patch operations. Captured `request_review` context had design keys `['nodes', 'edges']`; the frozen revision ID appeared nowhere in the payload.

Even a provider accepting the schema cannot reliably produce the exact `base_revision_id` demanded by `apply_patch`; valid-looking suggestions fail the entire review. Include the frozen revision identifier and explicit patch grammar. Construct a supported proposal using only the captured outbound context, then verify `validate_review` and comparison acceptance.

### F4 — Provider budget is not a wall-clock deadline

`backend/coach/__init__.py:191`.

`httpx` applies the supplied timeout to individual connection/read/write operations. The installed `httpcore` body-reading loop passes the same read timeout into each successive read. The code checks its deadline only before attempts. A provider sending body chunks less than 29 seconds apart, or connection and response phases cumulatively exceeding 30 seconds, can keep a review/guidance thread occupied substantially beyond the promised budget.

Enforce an overall cancellable deadline around transport and retry. Add a bounded delayed/chunked transport regression proving terminal failure within the total budget while preserving diagnostic evidence.

### F5 — Failure navigation ignores saved first-violation evidence

`frontend/src/results/ResultsView.tsx:50,60`; `backend/assessment/__init__.py:114`.

`Inspect evidence` compares evidence IDs directly with trace IDs. The backend stores the trace ID in `EvidenceItem.artifact_ref`. `Jump to first failure` independently chooses a non-success request or non-delivered job. Successful stale reads, duplicate-effect jobs marked delivered and late delivered jobs are missed; unrelated warmup failures can be selected. Aggregate failures can be associated with an arbitrary request.

Resolve the selected outcome's evidence IDs to their saved artifact references. Use the recorded trace for first violations and the recorded calculation window for aggregates. Cover stale successful reads, duplicate effects, late delivery and an aggregate latency failure.

### F6 — Replay and comparison child requests allow stale evidence responses

`frontend/src/results/ResultsView.tsx:33`; `frontend/src/results/ExperimentView.tsx:29`.

Snapshot/trace/design fetches and comparison polling update state without cancellation or checking the current case, trace, candidate or comparison identity. Selecting A then B while A's snapshots are delayed lets A replace B's replay state. Starting another comparison on the same baseline while an old poll is in flight can restore the old comparison; candidate revision responses can overwrite the selected candidate's graph. Parent workspace/run guards do not protect these within-workspace transitions.

Guard each effect's responses with its current identity or cancellation flag and clear obsolete child state. Extend the delayed-response browser pattern to case/trace changes and successive comparisons on one baseline.

### F7 — Modal dialogs lack required keyboard focus behavior

`frontend/src/App.tsx:121,122,123`; `frontend/src/editor/Editor.tsx:95`; `frontend/src/coach/GuidancePanel.tsx:31`.

Modal `div`s provide neither focus confinement nor Escape handling/restoration. Most also omit initial focus transfer; Add component only adds `autoFocus`. Opening Settings or Guide with Enter then tabbing leaves focus in or traversing the underlying application. Add component permits tabbing outside its declared modal. Keyboard/screen-reader users can interact with obscured controls.

Prefer native modal `<dialog>` behavior, or implement initial focus, Tab/Shift-Tab confinement, Escape and return focus. Test those behaviors for each dialog through the existing approved browser-test flow.

## Deferred-minor triage

- **M1 — Integer-string coercion:** `backend/contracts/__init__.py:17,208`. `"instance_count":"1"` validates and normalizes to integer `1`, while JSON Schema requires integer. Nonblocking: numerical integrity is preserved, but validators accept different input sets. Strict integers or explicit coercion documentation are options; global datetime strictness would need separate care.
- **M2 — Operation-scope ordering:** `backend/contracts/__init__.py:502`. Reversing `operation_ids` changes the hash unnecessarily. Nonblocking redundant work/candidate identities. Sort operation IDs in the hash representation and assert equality. Distinct from F1's same-hash/different-outcome defect.

## Declined to judge and coordinator rulings

- Live-provider teaching quality and five-person study: explicitly unperformed/disclosed; no quality or learning-impact claim is made.
- Real-cloud accuracy: outside the educational model's scope.
- Accounts, remote exposure, multiple users and cloud deployment: excluded by the local single-user plan.
- In-app browsing of quarantined imported historical runs: historical evidence is retained but not shown in history. TEST-PLAN §6.6 requires reimporting supported design/workload data and reproducing it. Coordinator accepts this scope: imported evidence remains untrusted, and a fresh compatible run provides in-app replay. README must state this limit explicitly. Cost if wrong: add a read-only imported-history view; existing evidence stays preserved.

The coordinator accepts M1 as nonblocking and will document normalization, preserving the current JSON-friendly boundary behavior. M2 is small and shares F1's hash work, so the consolidated correction includes it.
