# Professional black-and-charcoal UI redesign

Approved in conversation: full interface refresh, black and charcoal, balanced readable density. The architecture and measured evidence define the interface. Base commit: `2c0d7c7`.

### Task 1: Refresh and verify the complete interface

- Establish shared neutral tokens: #000000 background, #141414 panels, #202020 raised surfaces, #363636 dividers, #F4F4F4 text, #A3A3A3 secondary text. White primary actions; muted semantic statuses with labels. Native system typography, 28/20/16/14/12px scale, 36px controls, 6px control and 8px modal radii.
- Compact shell and workspace actions; remove duplicate Requirements action. Align challenge rows. Editor uses 208px palette / flexible canvas / 304px inspector at >=1200px, drawers below. Update editable and recorded graph styles together.
- Prioritize requirement outcomes, selected evidence and replay. Put complete operation measurements in an expandable accessible table. Use compact candidate rows and comparison columns sized to actual alternatives. Refresh requirements, saved work, all dialogs and empty/error/loading states.
- Consolidate existing CSS and remove hardcoded canvas colors. Preserve backend contracts, data, state guards, keyboard editing, native-dialog focus, consent and reduced motion. Update docs/UI-UX-SPEC.md. No dependency or font additions.
- Run frontend unit tests, production build, complete browser suite and visual inspection at 1440x900, 1024x768 and 390px. Add one browser check for narrow result containment and accessible complete operation measurements. Verify contrast and focus. Inspect library/editor/requirements/results/comparison/history/dialogs.

Expected: all frontend checks pass, existing full learner journeys and race/focus checks remain intact, no page-wide overflow or clipped controls, consistent styling across all screens. Final independent review covers the UI diff and accessibility/responsive edge cases.
