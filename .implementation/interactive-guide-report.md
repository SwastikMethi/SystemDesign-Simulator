# Interactive guide and replay verification

Plan: [interactive-guide-plan.md](interactive-guide-plan.md). Base: `c497aef`.

## Delivered

Start walkthrough opens an empty canvas. The guide points to the actual component and connection controls, explains requirements, runs a preview, follows a recorded request through Client → App service → SQL database and back, opens R02 evidence, teaches the medium database upgrade, and finishes only after a passing assessment of the current revision. Skip/resume preserves the draft; undo restores missing prerequisite steps; restarting confirms unsaved changes. Keyboard users can add and connect components through the same controls.

Replay selects a saved request automatically, has an explicit System overview, and bounds playback to the selected recording. Teaching pace makes short hops visible while keeping timestamps and measurements unchanged. Pause/resume, stepping, seeking, restart, return direction, reduced motion, loading, retry and empty-recording states are covered. The guided lesson selects an actual successful saved request reaching SQL; failed requests and aggregate requirement evidence remain available.

React Flow's controlled node measurements are retained during animation so components and packet markers stay visible. The guided replay reserves a side column at desktop/tablet widths so its card does not cover playback controls. No dependencies, API contracts, fixtures or simulation behavior changed.

## Verification

- Frontend unit tests: **13 passed** after the final renderer correction.
- Backend walkthrough calibration: **6 passed**.
- Focused real-server replay and guide tests: **6 passed in 38.3 seconds**, including the complete lesson at 1440×900 and 1024×768, pointer hit targets, visible packets/components, keyboard actions, undo, restart and saved-run resume.
- TypeScript and production build: **passed**, including the final browser suite's startup build. Vite reports a bundle-size advisory above 500 kB; no dependency or bundling changes were added.
- Full browser suite on `9ca158f`: **17 passed in 5.9 minutes**, including the existing catalogue journeys, comparison/export paths, asynchronous request races, modal accessibility, recovery, replay and the complete guided lesson at both widths.
- Inspected viewport screenshots of replay at both sizes: all three components and moving request markers are visible, and the guide leaves playback controls clear. Start, upgrade and passing-assessment screenshots are in `frontend/screenshots/interactive-guide-*.png`.

Observed failing regressions before fixes: no initial request selected; no recording retry; walkthrough began with three existing nodes; a sampled request stopped before SQL; the guide intercepted the Reduced motion pointer target at 1024px; continuous animation lost the packet marker because node dimensions were reset. The corresponding behavior now has runnable browser or unit coverage.

## Independent review

`gpt-6-astra` reviewed `c497aef..0eea282`, the approved plan and execution evidence. It found **one Important issue**, the guide overlapping playback controls at 1024px, and no Critical or Minor findings. A direct pointer-target assertion reproduced the overlap before the side-column correction. Subsequent visual verification exposed the shared node-measurement issue; the same regression now asserts visible packets and components while playing. Both corrections passed the focused suite. No findings were deferred and no behavior was declined for judgment.

## Execution record

- Task 1: `c1a0706` — request playback and regression coverage.
- Task 2: `0eea282` — action-driven guide, progress rules and complete lesson coverage.
- Task 3 correction: `9ca158f` — retained renderer measurements and accessible guided playback controls.
- All three plan tasks are complete. The final suite finished successfully during a conversation interruption; its completed log was checked on resuming. Completion records use the executed checks above without repeating a successful suite for bookkeeping.
- Continued on `feat/system-design-simulator`; merging and publishing were not requested.
- Browser tests use an isolated server and temporary data directory. The existing app on port 8770 and saved data were preserved; production builds refresh its frontend assets. Unrelated `.env.example` edits were not inspected, staged or modified.
