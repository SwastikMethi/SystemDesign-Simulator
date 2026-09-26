# Small hands-on walkthrough

Approved in conversation: a 3–5 minute hands-on task with a simple checklist in the existing Guide. No interactive step tracker, AI requirement, new dependencies, engine changes or API/schema changes. Preserve the black-and-charcoal UI and the five regular challenges.

## Task 1: Add and verify the complete walkthrough

- Add `first-design` (version 0.1.0, level 1), titled **Your first design**, with Client → App → Database and one `read_note` operation. Reuse notes initial data and operation defaults. Allow only client, app service and SQL database.
- Use `app.small.v1` and `sql.small.v1`; changing only the database to `sql.medium.v1` must pass. One required steady scenario at 120 rps, seed 101, 10 s warmup, 30 s measurement, 5 s drain. Keep Preview unchanged.
- Require success ≥99.5%, successful response p95 ≤250 ms, and cost ≤50 credits/hour; at least 100 success/latency samples. Initial/failure use small SQL, reference uses medium, budget uses large.
- Register content for both API loading and the numerical-fixture CLI. Show Walkthrough · About 5 minutes above the five unchanged regular challenge rows, with Start walkthrough and normal progress.
- Open the existing Guide on start and keep it available: inspect components/requirements; Preview and inspect failed latency; select Database and change Profile to sql.medium.v1; Assess design and confirm pass; reopen Saved work. Use Open architecture as its action. Keep generic guidance for the original challenges.
- Update README and challenge documentation, including the explicit shortened workload exception and fixture totals.

### Steps and expected evidence

1. Write real simulation regression cases and a browser journey at 1440 and 1024 px. Update the content inventory assertion while retaining all five original IDs/order.
2. Run `.venv/bin/python -m pytest -q tests/test_walkthrough.py tests/test_contracts.py::test_all_content_compiles_and_costs` and `npm --prefix frontend run test:e2e -- e2e/walkthrough.spec.ts`. Expected RED: new content and walkthrough entry missing.
3. Implement the content and UI above; rerun focused checks. Expected GREEN: intentional starter failures, passing manual upgrade, over-budget failure, preview cannot complete, saved pass reopens.
4. Run `.venv/bin/python -m pytest -q`, `npm --prefix frontend test`, and `npm --prefix frontend run build`. Expected: all pass. Execute the four walkthrough fixtures through the CLI and inspect desktop/narrow screenshots.
5. Commit the implementation. Run `npm --prefix frontend run test:e2e` through the completion wrapper once (expected: all pass), then obtain one independent review of this change range.

### Review focus

Ensure adding the walkthrough does not change the original five challenge identities/order or fixtures; every loader/CLI can resolve the new ID; the instructions match the real inspector and result controls; progress is earned only by assessment; guide focus and narrow layout remain usable; stale responses and existing saved work keep their existing protections.
