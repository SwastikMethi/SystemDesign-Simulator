# Implementation and delivery plan

AI System Design Simulator · v0.1

## 1. Delivery strategy

Build one complete learning experiment first, then grow to the five-challenge prototype. These are milestones, not a promise that the full scope fits in one day. The first daily-build demo can show the catalogue exercise and Prove this fix; the broader release adds the remaining supported behavior.

Use the simplest architecture in TRD. Do not build cloud deployment, accounts, a plugin system, general-purpose workflow scripting or orchestration infrastructure to support this local prototype.

## 2. Milestones and gates

| Milestone | Work | Exit gate |
|---|---|---|
| M0 — Contracts | Translate document fields into validated schemas; choose/pin dependencies; add catalogue content and two sample designs | Example files validate; profile/rubric versions are explicit |
| M1 — Headless engine | Client, application and SQL; seeded arrivals; slots/queues; network; terminal outcomes | Exact deterministic fixtures and conservation tests pass |
| M2 — First playground | React canvas, inspector, route validation, save revision, preview and result panel | User can build, run and inspect a three-node catalogue design |
| M3 — First complete assessment | Cache, invalidation/freshness, burst/cold cases, repeated seeds and evidence | Catalogue has verified passing/failing/budget fixtures |
| M4 — AI and comparisons | Provider adapter, evidence review, bounded patch proposals, baseline/candidate runs | Prove this fix works and exposes a failed candidate when applicable |
| M5 — Explain the behavior | Replay timeline, first failure, selected traces, accessible animation and hot-key experiment | Learner can explain a failed requirement from the replay |
| M6 — Full prototype | LB, gateway, queue, worker, object/CDN; remaining four challenges | Ten components and five challenges pass their support/evaluation gates |
| M7 — Release | History, evidence export, error states, refresh/restart handling, usability and performance checks | PRD P01–P12 and TEST-PLAN release checks pass |

Keep a small fixture runner available throughout development. Run existing numerical fixtures after changing engine behavior. Do not use screenshot polish as evidence that the simulation works.

## 3. First catalogue demonstration

Start with Client → App → SQL expressed as the typed routes in the sample design. Execute the burst and inspect queues. Ask the coach to propose additional app capacity and a cache or larger store profile. Simulate supported candidates using the exact same workload bundle. Show requirements and credits, then replay the relevant waiting time.

Do not script fake metric improvements for a presentation. If the proposed cache patch fails freshness, show the failure and fix its invalidation policy. That is a useful teaching moment.

## 4. Decisions to make during implementation

| Decision | Default / resolution |
|---|---|
| Product name | Keep AI System Design Simulator until the user chooses a name |
| AI provider | Use an endpoint the user can access; keep credentials/model configurable |
| UI theme | Professional dark default from UI-UX-SPEC; light theme may follow |
| State management | Start with React state/context plus a focused canvas store; add a library only if coordination requires it |
| Motion library | Start with CSS/SVG; add a small library for panel/layout transitions only if necessary |
| Runtime packaging | Local Python backend plus frontend build; Docker optional later |
| Cost model | Fictional fixed profile credits; no live cloud prices |
| Data persistence | Versioned files; no database or accounts |
| Challenge threshold changes | Review with fixtures; version the content; do not silently change old results |

These defaults allow implementation to proceed without blocking on branding or vendor selection. Actual provider credentials are supplied at runtime and never embedded in code or documentation.

## 5. Suggested build-agent handoff

Read README, PRD, TRD, SIMULATION-SPEC, COMPONENT-CATALOG and DATA-API-SPEC before editing code. Implement M0–M3 before the coach. Honor the numerical contracts, never invent metrics, and keep unsupported behavior explicitly unavailable. After each milestone, record what works, the meaningful tests run and remaining limitations. Build the first full learner journey before expanding the catalogue. Do not deploy or provision cloud infrastructure as part of this prototype task.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| Too many components delay a useful demo | Complete catalogue end-to-end, then expand by challenge |
| Plausible but false numerical model | Exact fixtures, conservation checks, explicit component semantics |
| Arbitrary AI grading | Deterministic rubric owns the verdict |
| Learner optimizes only visible averages | Separate failure rate, per-operation tails, freshness and job completion |
| A cache or replica is treated as a magic improvement | Model its actual behavior and rerun the change |
| Prototype scope becomes production planning | Label teaching profiles, modeled limits and scenario-specific outcomes |
| Replay data grows without bounds | Store bounded snapshots/selected traces and complete bounded outcome journals |

## 7. Release artifacts

Working local application, setup README, versioned challenge/profile files, numerical fixtures, representative validated designs, recorded runtime limits, and a clean demo showing a real failed requirement followed by a tested revision. Export one evidence bundle demonstrating that results can be inspected without calling the LLM again.
