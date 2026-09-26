# Workspace design direction

The approved UI spec is the visual authority. Use an engineering lab, with architecture occupying the largest surface. Avoid a generic analytics dashboard or a landing-page hero.

Palette: deep navy #0B1220 background; #131E30 surfaces; #2A3952 boundaries; #F1F5F9 primary text; #B7C4D8 secondary text; #62C4FF action/selection. Status colors add an icon and readable label: #60D6AB pass, #FFC66D warning, #FF8996 fail. Verify actual contrast.

Typography: system sans-serif (SF Pro/system on the target Mac), 16 px reading copy, 14 px compact controls; tabular numerals for measured values. Labels use sentence case. The challenge title anchors the page. No gradient hero, ornamental glow, or constant pulse.

Layout: 56 px application header; quiet navigation between Challenges and Saved work; challenge workspace below it. Left palette about 220 px; central dotted canvas; right inspector 320 px; bottom expandable timeline. At 1024 px use palette/inspector drawers that do not cover the active control. Results and comparison are workspace tabs retaining challenge/revision identity.

```
┌ Challenge / revision             Requirements  Preview  Assess ┐
├ Palette ─────┬ Canvas / Results / Compare ──────┬ Inspector ────┤
│ search       │ operation filter               │ selected node │
│ component    │                                │ profile       │
│ purposes     │   architecture and evidence    │ policy forms  │
│              │                                │ requirements  │
├──────────────┴────────────────────────────────┴───────────────┤
│ Playback  pause / step / speed       scenario / seed          │
└──────────────────────────────────────────────────────────────┘
```

The memorable element is the living architecture: typed edges, measured queue/slot states, and an evidence-selected path. Everything surrounding it stays quiet. Animations answer playback or user actions; no decorative movement. Empty results explain how to run. Optional AI sits after deterministic requirements, with explicit unavailable/retry state.

Review against brief: keep the provided palette and system typography rather than inventing a new brand. Use the five genuinely ranked challenge levels as numbers; do not number unrelated panels. Use fewer containers in the central work area so the canvas does not become another card in a card grid. No invented sample metrics in production views.
