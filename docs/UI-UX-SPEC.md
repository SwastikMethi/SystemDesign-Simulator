# UI, interaction and animation specification

AI System Design Simulator · v0.1

## 1. Visual direction

Create a professional engineering workspace with a clear canvas, restrained accents and purposeful movement. The architecture and its behavior should be the most prominent visual elements.

Suggested tokens: background #0B1220, surface #131E30, border #2A3952, primary text #F1F5F9, secondary text #B7C4D8, selection/action #62C4FF, pass #60D6AB, warning #FFC66D, fail #FF8996. Verify contrast in the actual rendered UI; do not assume these combinations all satisfy every text size. Use icons and labels alongside status colors.

Use a readable system sans-serif and tabular numerals for metrics. Minimum body text 14 px; primary reading text 16 px. Avoid decorative glow over labels, constant pulsing, tiny metric text and unnecessary 3D effects.

## 2. Main screens

| Screen | Content and primary action |
|---|---|
| Challenge library | Five cards ordered by level; brief, concepts, status, last result; Open challenge |
| Playground | Requirements, component palette, canvas, inspector and run controls; Preview or Assess |
| Results | Requirement checklist, per-case metrics, evidence, AI review; Inspect failure or Test proposal |
| Comparison | Baseline/candidate diff, matched scenarios, requirement changes, cost and latency; Adopt revision |
| Saved work | Local designs and runs; reopen, export or delete an explicitly selected item |

Results and comparison may be workspace tabs rather than separate routes. Do not add a large admin/settings dashboard for the prototype. Provider settings and appearance fit in a small settings drawer.

## 3. Playground layout

Desktop target: 1440×900, usable from 1024 px width. Header 56 px. Left palette approximately 220 px. Right inspector 300–360 px. Centre uses remaining width. Bottom timeline is collapsed to 56 px during editing and expandable during playback.

- Header: challenge title, revision/save status, Requirements, Preview, Assess design.
- Left: search, component groups, ten available blocks, short purpose labels.
- Centre: dotted canvas, clear labels, typed edge labels, minimap only on demand, fit-to-view.
- Right: selected node/edge controls; toggles to Coach and Requirements.
- Bottom: virtual-time cursor, play/pause, step, playback speed, event markers and metric tracks.

At narrower widths, palette and inspector become drawers. Mobile supports viewing results; full touch architecture editing is not a v0.1 release requirement.

## 4. First-time journey

1. Open the catalogue challenge and read its brief plus five key requirements.
2. Choose Start empty or Load starter. The starter is labeled Unassessed and may fail.
3. Add nodes and connect routes. Explain invalid connections beside the selected edge.
4. Preview normal traffic. A short callout identifies a metric worth inspecting.
5. Run full assessment. Explain that this uses multiple scenarios and seeds.
6. Open a failed requirement to highlight the relevant node, trace or metric window.
7. Request AI review if desired; first-use provider disclosure is concise and skippable.
8. Test a suggested patch and inspect the before/after result.

The learner should never have to understand every advanced setting to begin.

## 5. Canvas behavior

Nodes show type, name, profile/instances and a compact state badge. During playback show up to two context-relevant values: busy slots and queue size for compute, hit rate for cache, backlog for queue. Detailed values live in the inspector.

Edges identify operation and relationship. Distinguish request, cache miss, invalidation and queue consumption with labels and line styles. Selecting an operation dims unrelated edges. Response paths can be temporarily revealed by selecting a trace.

Provide keyboard alternatives to dragging: Add component dialog, searchable node list, source/target selectors and inspector forms. Undo/redo includes graph edits and settings. Deletion shows affected connections before confirmation when multiple nodes are selected.

## 6. Animation contract

| Event | Visual treatment | Source of truth |
|---|---|---|
| Request movement | Small directional marker on the relevant edge | Recorded trace events or labeled sampled traffic |
| Increasing queue | Stable queue bar/stack and numeric count | Snapshot queue depth |
| Cache hit | Brief hit badge; return along the selected trace | cache_hit event |
| Cache miss | Marker continues to store; miss badge | cache_miss event |
| Failure | Status/icon change and timeline marker; no flashing | Fault/error event |
| Recovery | Status returns with a short transition | Engine event, not a fixed UI timer |
| Proposed edit | Highlight added/changed/removed nodes and settings | Validated patch diff |
| Result completion | Requirement rows settle into labeled states | Final assessment response |

Use 120–180 ms for small interactions and 180–250 ms for panel transitions. Camera movement is user-controlled; avoid jumping to every event. Aim for 60 fps while keeping simulation independent of frame rate.

At high traffic, cap visible moving markers at 100 and label the animation Sampled traffic. Numerical counts use the full simulated workload. A selected request displays its exact recorded sequence; playback time compression is explicit. Interpolation affects positions only, never counts or outcomes.

Reduced motion disables traveling markers, pulsing and animated camera changes. Use step highlights, instant metric updates and static directional arrows. Pause freezes the playback cursor, not the underlying completed evidence.

## 7. Simulation states

Editing → Validating → Queued → Running → Completed. Validation can return to Editing; an active run can become Canceled, Failed or Interrupted. AI review has an independent Idle/Requested/Available/Failed state.

Show case progress such as Case 4 of 15 and the current simulated time. Do not display invented percentage progress for an opaque model request. After completion, offer Replay from start and Jump to first failure.

An assessment is tied to a frozen revision. Editing during playback creates a new draft; a prominent Unassessed changes badge prevents confusing an old passing result with the new design.

## 8. Results hierarchy

First: a short deterministic verdict and requirements checklist. Second: three or four key metrics, with scenario and operation selectors. Third: supporting traces and AI explanation.

Each row shows requirement, target, observation, status and Inspect evidence. Use Pass / Fail / Not evaluated / Incomplete text. A result with no samples shows Unavailable and the reason.

p95 help text: “95% of the successful responses were at or below this duration. Check failures alongside this value.” Credits help text explains fictional fixed profile rates and omitted cloud billing dimensions.

AI findings distinguish Observed from Hypothesis. Test proposal appears only for a validated patch. A failed provider call says “Simulation complete. AI explanation unavailable.”

## 9. Comparison and first-failure replay

Comparison defaults to synchronized canvases or an overlay diff, with a shared scenario/seed selector. Show requirements before a compact cost/latency table. Use explicit signs and units for changes. Label any illustrative empty-state numbers as examples; production views never populate fake metrics.

The first-failure view shows timeline, selected request path, waiting/processing/network durations, and related evidence. An aggregate failure opens its time window. Do not pretend a single slow request alone proves the root cause of an aggregate bottleneck.

The learner can adopt a candidate revision while retaining the original and its results. Display Best among tested alternatives only if assessment has supplied that classification.

## 10. Accessibility and usability checks

Check keyboard navigation, visible focus, form labels, color contrast, reduced motion, panel resizing, long names and empty/error states. Use live announcements for major run state changes, not every metric update. Provide a text/list representation of nodes and connections.

Manually test the full catalogue journey at 1440×900 and 1024×768. Inspect a 30-second recording for readable labels, meaningful transitions and absence of invented learning/training animations. This application uses an existing model; a spinner must not claim it is training a new one.
