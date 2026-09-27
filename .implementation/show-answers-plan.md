# Show answers and preview reference solutions

Spec: the approved conversation plan. Add direct AI answers and read-only reference previews for all six challenges. Reveal is explicit and available before a run; previews never load, save, complete, or change a draft. Existing hints and explanations retain their validation and consent behavior. Reuse installed dependencies, diagrams, dialogs, and reference fixtures.

## Global constraints

- Continue in the existing feature workspace. Preserve user environment files and saved data.
- Add reference explanations outside versioned challenge definitions so saved evidence remains compatible.
- AI answers use the existing explanation field and qualitative authored context, never invented simulation measurements.
- Inline answers must resolve a completed hint from the same saved design and revision.

### Task 1: Reference content and answer API

Interfaces: GET /api/v1/challenges/{challenge_id}/reference returns {design, explanation}; guidance mode gains answer and optional source_guidance_id in requests and records. Existing records default the new field to null.

1. Add tests covering all reference challenges without a run/provider, immutable source designs, standalone and source-hint answers, invalid sources, schema/claim validation, consent and failure behavior.
2. Run .venv/bin/python -m pytest tests/test_guidance.py -q. Expected: new feature tests fail for absent endpoint/mode/context.
3. Add content/reference-answers.json and a minimal content loader and typed response. Extend the existing guidance API, prompt and validator; retain the current provider adapter and polling/storage lifecycle.
4. Run the focused tests. Expected: all pass. Export OpenAPI and generate frontend types.

### Task 2: Answer actions and read-only previews

Interfaces: consume the Task 1 API and generated types. Source answer takes its question and optional explanation from the saved hint. Reference preview is an App-level sibling dialog so coach state and focus survive.

1. Add browser tests for preview before a run/without AI, dirty graph and undo preservation, result and lesson preservation, answer mode and inline source context, failure retry, nested focus and supported widths.
2. Run the new browser tests. Expected: fail at the absent reference and answer controls.
3. Add Answer mode and inline Show answer, retaining hint context for retries. Add View reference solution to the coach and Requirements. Reuse RecordedGraph with a reference caption; render settings, connections and explanation in a responsive read-only dialog with retry.
4. Update documentation. Run backend suite, frontend unit tests/build and browser suite. Expected: pass; existing bundle-size advisory may remain.
5. Review the complete change, address important findings, smoke-test the configured provider and restart the local app with the existing environment.

## Review focus

Check source ownership/revision validation, provider schema matching Answer, stale polling and mode changes, retry context, reference modal focus return, no draft/run/lesson mutations, all six authored explanations matching their fixtures, and old guidance record compatibility. Do not read or include .env or .env.example secrets in review output.
