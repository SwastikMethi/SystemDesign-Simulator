# Interactive first-design guide and working replay

Approved specification: the implementation plan in the conversation, 2026-09-26.

## Global constraints

- Replace the first-design checklist with spotlight guidance from an empty canvas.
- Teach Client → App service → SQL database, requirements, Preview, recorded request flow, R02 evidence, medium database upgrade, assessment, and Saved work.
- Advance on real graph/run state; recover from undo; skip/resume without changing the draft; confirm restart when dirty.
- Keep charcoal styling, keyboard access, responsive panels, and reduced motion.
- Preserve APIs, fixtures, saved work, other challenges and simulation behavior. No new dependencies or AI requirement.

### Task 1: Repair recorded playback

Auto-select a request, provide explicit System overview, bound playback to the selected request, and default to Teaching pace (at least 750ms per distinct timestamp interval). Preserve recorded timestamps and real-time speeds. Synchronize event explanation, markers, return direction and highlights. Support pause/resume, scrub, step, restart, loading/error/retry, empty traces, case changes and reduced motion.

Interfaces: existing traces/snapshots; optional ResultsView guide callbacks and stable playback anchors; RecordedGraph remains usable by comparison views.

Steps: write and run regression tests (Expected: current missing behavior fails); implement; run frontend tests and build (Expected: pass); commit.

Verification: `npm --prefix frontend test` and focused replay browser regression.

### Task 2: Guide the first architecture

Use a small first-design controller, spotlight card and stable anchors. Add three components with readable positions via existing graph helpers; teach both connection forms; highlight requirements and Preview; explain real replay; inspect R02; select the database Profile and upgrade to sql.medium.v1; assess; point to Saved work. Expand drawers/scroll targets, keep targets usable by keyboard, support skip/resume/restart and missing prerequisite recovery. Completion must match the current saved revision. Start walkthrough uses emptyGraph; keep fixtures unchanged.

Interfaces: graph/run state from App, minimal Editor guide props, ResultsView replay/evidence callbacks from Task 1. Guide survives run start but resets when another workspace is opened.

Steps: write and run state/browser regression tests (Expected: old checklist fails); implement; run frontend suite and full lesson browser checks at 1440/1024 (Expected: pass); commit.

Verification: `npm --prefix frontend test` and `npm --prefix frontend run test:e2e -- e2e/walkthrough.spec.ts`.

### Task 3: Verify and review

Check complete lesson, keyboard controls, undo/resume, restart, canceled/failed runs, reduced motion, replay boundaries and trace failures. Run full browser suite, frontend unit tests/build, and backend walkthrough tests. Review the final changes in fresh context; fix important findings with a regression test. Update README and implementation report. Keep the user's existing local service/data intact; its built frontend is refreshed by the build.

Verification: `npm --prefix frontend test`, `npm --prefix frontend run build`, `npm --prefix frontend run test:e2e`, `.venv/bin/python -m pytest tests/test_walkthrough.py` (Expected: all pass).

## Review focus

Check tutorial progress against dirty/frozen revisions; run/case/trace async races; undo and skip/resume; target visibility/focus and pointer access; teaching-time mapping with equal timestamps, transfer boundaries and terminal events; comparison rendering compatibility. Never fabricate trace data or mark a preview complete.
