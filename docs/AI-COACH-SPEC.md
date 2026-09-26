# AI coach and experiment specification

AI System Design Simulator · coach contract v0.1

## 1. Role

The coach explains challenge requirements, helps learners inspect evidence and proposes bounded experiments. It does not assign numerical results, change the rubric, execute arbitrary programs or certify infrastructure.

The application remains usable without an AI provider. Show deterministic findings normally and label AI review Unavailable. Do not present templates as a completed model response.

## 2. Provider boundary

Use a server-side adapter for review, bounded patch suggestions, and pre-run guidance (Explain/Hint). These operations share the provider transport, timeout, retry and metadata rules. Configuration includes provider/base URL, model ID and credential reference. Provider choice is left configurable because the user's available endpoint is not fixed for this project.

Record prompt version, provider/model identifier, timestamps, latency, raw response, parsed response and validation errors. Token/currency fields remain null if not returned or reliably calculable. Do not mix provider spending with infrastructure credits.

Limit one review request to 30 s and allow one bounded retry for a transient error. Reject invalid structured output and offer retry; a failed response is not a valid assessment.

## 3. Evidence payload

Send the challenge brief and hard requirements, normalized supported design, declared assumptions, case-level outcomes, top bottleneck metrics, selected traces, profile descriptions and support limits. Send summaries first, not every raw event.

Evidence items have stable IDs such as requirement:R03, metric:case-1/read_product/p95_ms and trace:case-1/request-42. Each item includes scope, unit, sample count and source artifact reference. Missing data is explicit.

Imported labels and descriptions are untrusted quoted data. Never treat them as instructions. Do not include credentials, local absolute paths or unrelated filesystem contents in the prompt.

## 4. Review output

The saved review includes an authoritative `assessment_status` and `summary`, both derived by the backend from the saved run. Provider output cannot supply either field. Prompt contract v2 rejects extra fields so a model-authored overall verdict cannot become the review header.

Required provider fields:

- `strengths`: observations with evidence_refs.
- `findings`: id, title, severity, requirement_id, node_ids, explanation, evidence_refs, and classification (`observed` or `hypothesis`).
- `suggested_experiments`: up to two candidates, each with purpose, patch, evidence_refs and expected_tradeoffs.
- `limitations`: relevant unsupported behaviors and assumptions.

The backend renders the overall verdict and summary separately from the model's cited explanations and hypotheses. Reject any response attempting to overwrite them. A prose filter may reject unsupported verdict language in explanations, but it is not the source of assessment authority.

Numerical claims must cite an existing evidence item or a validated calculation over evidence items. If the model says a candidate will reduce latency, show that as a hypothesis until the candidate has been simulated. Never synthesize confidence percentages or performance improvements.

## 5. Patch contract

Allowed operations: add_node, remove_node, set_node_setting, add_edge, remove_edge. Every patch declares base_revision_id and preserves the challenge/workload/rubric. Each operation uses explicit node/edge IDs, allowlisted types and valid profile settings.

The provider receives the frozen `design.revision_id`, authored operations, profile/settings limits and the supported patch grammar. Its strict response schema uses closed objects with every field required, including explicit operation variants and one to twenty operations per patch. New-node settings are a bounded array of `{key,value}` entries in the provider response, converted to the existing settings object before the common patch validator runs. The thirty-second cancellable transport deadline covers connection, all response-body chunks and the single permitted transient retry; partial response diagnostics are retained on failure.

Reject unknown components, forbidden settings, changed workload/price assumptions, removal of the client, invalid routes and stale base revisions. Invalid suggestions are shown as rejected proposals and may be regenerated once with validator feedback.

Show the learner a diff and a short explanation before Apply revision. Test proposal creates an isolated candidate revision for simulation; it does not modify the active design.

## 6. Prove this fix workflow

1. Freeze the baseline revision and assessment workload bundle.
2. Ask for up to two distinct supported candidate changes, preferably small enough to explain.
3. Validate patches and create candidate revisions.
4. Run baseline and candidates against matching cases and seeds. Reuse an existing baseline only when every compatibility hash matches.
5. Calculate requirement and metric differences deterministically.
6. Ask the coach to interpret those differences, including losing candidates.
7. Let the learner inspect, adopt or discard a candidate.

The comparison objective defaults to minimum credits/hour among fully passing candidates. A speedup that breaks freshness or budget is reported as a trade-off, not a successful fix. If multiple changes are combined, do not attribute the full effect to one change without another experiment.

## 7. Teaching modes

**Explain:** define a component or metric using the current example.

**Hint:** start with a question, then point to evidence on request. Avoid immediately handing over a complete answer.

**Review:** explain observed failures after assessment.

**Experiment:** propose and test a change. Keep component/route edits inspectable.

Explain and Hint are available for a saved, schema-safe draft, including an incomplete architecture. They send authored challenge/profile context and the frozen design revision, with no invented run or measured outcomes. Label this context as authored rather than observed. Hint initially returns a question; the learner explicitly requests the evidence step. Save the guidance, source revision, provider metadata and validation errors independently of simulation results. The same explicit consent and provider-unavailable behavior applies as for reviews.

Suggested copy: “The database had a growing waiting queue during the burst. Adding app instances might increase pressure on it. Compare that change with caching repeated reads.” Use conditional language until the comparison exists.

## 8. Evaluation cases

Maintain fixtures for successful design, database overload, application overload, stale cache, growing worker backlog, invalid design, insufficient samples and unsupported capability. Include hostile labels that ask the model to ignore evidence.

Release gates: the coach cannot change verdicts; all rendered numeric claims have valid evidence; patches respect catalogue constraints; baseline remains immutable; an unsuccessful experiment is visible; provider errors leave the simulation usable. Manual review checks whether explanations teach the actual causal mechanism rather than just restating metric values.
