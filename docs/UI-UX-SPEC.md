# UI, interaction and animation specification

AI System Design Simulator · v0.1

## 1. Visual direction

Create a professional engineering workspace with a black-and-charcoal palette, balanced readable density, and a clear canvas. The architecture and measured evidence should be the most prominent visual elements. Apply this direction consistently to the library, editing, recorded playback, comparison, saved work and dialogs.

Tokens: background #000000, surface #141414, raised surface #202020, structural border #363636, control border #707070, primary text #F4F4F4, secondary text #A3A3A3. Primary actions use white with black text; selection and focus use a light outline. Semantic colors are pass/added #8BBA98, warning/changed #D2B174 and fail/removed #DD8D8D. Use explicit labels and line styles alongside these colors. Normal text targets 4.5:1 contrast; essential control boundaries target 3:1. Structural dividers are decorative and intentionally quieter.

Use the native system sans-serif and tabular numerals for metrics. Page titles are 28 px, section headings 20 px, body and controls 14 px, primary explanatory prose 16 px, and metadata 12 px. Prefer regular/medium text with semibold headings. Controls are 36 px high with 6 px corners; dialogs have 8 px corners. Borders define useful groups and shadows belong to overlays. Avoid decorative glow, gradients, constant pulsing and unnecessary 3D effects.

## 2. Main screens

| Screen | Content and primary action |
|---|---|
| Challenge library | Five aligned rows ordered by level; brief, concepts and progress; Load starter or Start empty |
| Playground | Requirements, component palette, canvas, inspector and run controls; Preview or Assess |
| Results | Requirement checklist, per-case metrics, evidence, AI review; Inspect failure or Test proposal |
| Comparison | Baseline/candidate diff, matched scenarios, requirement changes, cost and latency; Adopt revision |
| Saved work | Local designs and runs; reopen, export or delete an explicitly selected item |

Results and comparison may be workspace tabs rather than separate routes. Do not add a large admin/settings dashboard for the prototype. Provider settings and appearance fit in a small settings drawer.

## 3. Playground layout

Desktop target: 1440×900, usable from 1024 px width. Global header 48 px, workspace context/actions approximately 64 px, workspace tabs 36 px. At widths of at least 1200 px, use a 208 px palette and 304 px inspector; the canvas takes the remaining width. At narrower widths, palette and inspector become drawers positioned within the editor. Recorded playback has its own evidence workspace.

- Header: challenge title and revision/save status; quieter Guide/AI coach utilities; grouped Save, Preview and Assess design actions. Requirements appears once in the workspace tabs.
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

First: a short deterministic verdict, scenario/operation selectors and requirements checklist. Second: selected evidence and recorded replay, with the trace beside the canvas on wide screens and below it on narrower screens. Third: an expandable Operation metrics table containing all measurements, grouped by operation, including units, sample counts and unavailable reasons. Optional AI explanation remains visually subordinate to deterministic evidence.

Each row shows requirement, target, observation, status and Inspect evidence. Use Pass / Fail / Not evaluated / Incomplete text. A result with no samples shows Unavailable and the reason.

p95 help text: “95% of the successful responses were at or below this duration. Check failures alongside this value.” Credits help text explains fictional fixed profile rates and omitted cloud billing dimensions.

AI findings distinguish Observed from Hypothesis. Test proposal appears only for a validated patch. A failed provider call says “Simulation complete. AI explanation unavailable.”

## 9. Comparison and first-failure replay

Comparison uses the existing overlay diff with a shared scenario/seed selector. Present candidate revisions as compact selectable rows. Size result columns to the actual baseline and alternatives, without an empty reserved column. Show verdicts, costs and requirement changes together, with complete measured operation differences available below. Use explicit signs and units for changes. Production views never populate fake metrics.

The first-failure view shows timeline, selected request path, waiting/processing/network durations, and related evidence. An aggregate failure opens its time window. Do not pretend a single slow request alone proves the root cause of an aggregate bottleneck.

The learner can adopt a candidate revision while retaining the original and its results. Display Best among tested alternatives only if assessment has supplied that classification.

## 10. Accessibility and usability checks

Check keyboard navigation, visible focus, form labels, color contrast, reduced motion, panel resizing, long names and empty/error states. Use live announcements for major run state changes, not every metric update. Provide a text/list representation of nodes and connections.

Manually test the full catalogue journey at 1440×900 and 1024×768, and results at 390 px width. Wide tables may scroll within their containers; the page itself must not overflow horizontally. Check long labels and all six dialogs. Inspect a 30-second recording for readable labels, meaningful transitions and absence of invented learning/training animations. This application uses an existing model; a spinner must not claim it is training a new one.
