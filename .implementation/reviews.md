# Independent implementation reviews

## Task 2 — engine

Initial review of `521ca66`: three Important findings.

1. Disconnected app nodes could absorb a required outage because implicit fault selection sorted all nodes, including unused ones.
2. Shared worker completion woke only its originating queue, stranding accepted jobs from another queue while capacity was idle.
3. Pool promotion and job dispatch executed inline at completion priority, before same-time deadlines.

Fix `ee4628b` resolves participating logical fault roles, exposes a pure mapping helper for comparisons, schedules actual work at DISPATCH priority with capacity reservation, and wakes a fair global queue arbiter. Five regressions were added; 31 numerical tests passed. Forty targeted authored cases retained their unrounded requirement values and sample counts.

Scoped independent re-review: **Approved**, all three addressed, no new Critical/Important issues in the fix. API enforcement of the fault mapping remains an integration check owned by Task 3.

## Task 3 — API, storage, coach

Initial review of `f509234`: Needs fixes.

1. High: deletion's progress fallback could credit a passing comparison candidate after its comparison and previously credited baseline were deleted.
2. High: malformed imported workloads returned 500 and left a partially imported design because writes preceded full validation.
3. Important: coach validation accepted a false verdict sentence, “The assessment passed all requirements.”
4. Important: malformed provider JSON lost raw response evidence because parsing happened before persistence.

Fix round 1 (`3eec5ce`) addressed progress fallback, staged import, and raw malformed-response retention. Scoped review found overall summary authority still depended on a synonym filter, malformed usage could strand a review, and a missing target instance could bypass comparison's fault guard.

Fix round 2 (`1167a5f`, `05cf8a1`) makes the overall summary/status server-owned, preserves terminal failure for malformed provider metadata, validates required instance existence in the shared fault resolver, and rejects incompatible comparisons. Imports additionally enforce a 100 MiB aggregate expanded-workload limit; a canonical 15-case catalogue bundle measured 72,597,152 bytes. Sixteen focused API/coach tests passed; one already-verified long numerical integration test was deselected.

Scoped independent re-review: **Approved**, no new Critical/Important regression. The locked FastAPI/Starlette TestClient emits a deprecation warning recommending `httpx2`; production still uses the configured `httpx` adapter. No arbitrary suppression or unrelated dependency was added.

## Integration checks requested by reviewers

- Actual API retrieval of outcomes including `accepted_us`, snapshots, traces, and evidence links.
- Preview, experiment, imported evidence, and comparison candidates cannot independently grant completion.
- Matched comparisons enforce fault applicability as well as workload/version hashes.
- Provider failures retain deterministic results and inspectable diagnostic evidence.

Reviewers accepted reported executed tests without repeating full suites. Focused reproductions established the bugs above. Live-provider access remains unavailable; no live-provider result is claimed.

## Task 4 — frontend

Independent review of frozen `08a5382` (including `RecordedGraph` from `337ccd8`): **Needs fixes**.

1. Important: a valid coach proposal crashes because the UI treats the backend's string `expected_tradeoffs` as an array and calls `.join()`.
2. Important: a new baseline can retain the old baseline's comparison, causing differences and graph overlays to be attributed to the wrong run.
3. Important: an old run's event stream and fetch responses can replace results after the learner opens another workspace; an old terminal response can close the new subscription.
4. Important: a save response clears the dirty flag even when edits occurred while saving, allowing assessment of an older graph than the one displayed.
5. Important: evidence selection uses only requirement ID, so catalogue R01's write row opens the read operation's evidence.
6. Important: reopening a saved design/run/comparison does not initialize the optional experiment scenario; the displayed option and submitted empty value differ.

Minor findings: challenge completion status remains stale until reload, and saving an edited revision can hide the unassessed badge while leaving the old result indicator. Both are included in the same correction round.

The reviewer executed focused reproductions of the valid-coach rendering crash and operation-specific evidence mismatch. The shared comparison selector already includes both scenario and seed; no finding remains there. Pre-run Explain/Hint was already assigned as pending scope and was excluded from this frozen review. One consolidated correction was sent to the frontend owner.

Scoped round 1 (`e76b8c9`) addressed all six Important findings and both Minor findings. Build, four focused unit tests, the full real-server journey and narrow editor, and a delayed-response race check passed. The new Explain/Hint panel matches its backend contract.

The scoped reviewer reproduced two new Important regressions in the context-reset changes: leaving during a pending load strands `busy=true`, and failed run creation restores the prior run without its active identity/subscription. Both are assigned to the same owner in correction round 2; they require focused failure/navigation checks, not another numerical matrix run.

Scoped round 2 (`5a38139`): both regressions **ADDRESSED**, no new Critical/Important breakage. Leaving clears context-owned busy state; both rollback branches restore active identity, results, comparison and subscription through a shared activation path. Build, four unit checks and two focused real-server lifecycle checks pass. Independent verdicts: **Spec compliance Approved; task quality Approved**.
## Final whole-branch review — d7296cb

`/root/final_review` (gpt-6-astra) reviewed `1b280c8..d7296cb`. Initial verdict **With fixes**: no Critical findings, seven Important findings concerning canonical fault selection, strict provider schema, patch context, total provider deadline, authoritative failure evidence, child response identity, and modal focus behavior. Complete findings, reproductions and minor triage are in [final-review.md](final-review.md).

The consolidated correction includes `ca610b6`, `3742082` and `625da92`, with refreshed verification evidence through `2b41d2b`. One independent scoped re-review of `d7296cb..2b41d2b` returned **Approved**: F1–F7 and M2 are addressed; M1 is addressed under the documented normalization ruling. No new Critical/Important breakage or additional out-of-scope observations remain. The reviewer inspected regression assertions and recorded outputs without repeating the suites. Implementation and review are complete; live-provider quality and the five-person learning study remain explicitly unverified.
