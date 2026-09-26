# Product requirements

AI System Design Simulator · v0.1 · 26 September 2026

## 1. Product goal

Help developers learn system design by making design decisions, observing modeled behavior, and improving an architecture using evidence. A learner should understand both the result and the reason behind it.

Primary audience: developers learning backend architecture and engineers preparing for system-design discussions. The prototype is an educational local application, not a production capacity-planning service.

## 2. Problem

Architecture diagrams often leave behavior unspecified. Learners can memorize that a cache or queue is useful without understanding when it helps, when it fails, or what new trade-offs it introduces. AI feedback can sound convincing while having no measured support.

This product turns a diagram into an explicit executable model. It connects requirements to experiments, metrics to traces, and suggestions to before/after comparisons.

## 3. Product principles

1. Requirements are visible before the learner builds.
2. Multiple different architectures may pass.
3. Adding more components does not automatically improve a result.
4. Every displayed measurement comes from the engine or a disclosed cost formula.
5. AI recommendations are hypotheses until tested.
6. Unsupported behavior is labeled Not evaluated.
7. A small understandable prototype is preferable to a large catalogue of decorative blocks.

## 4. Included in v0.1

| ID | Requirement | Acceptance condition |
|---|---|---|
| P01 | Ranked challenge library | Five playable challenges with concepts, measurable requirements, and support status |
| P02 | Architecture playground | Add, connect, configure, duplicate, delete, undo/redo, zoom, and save ten supported component types |
| P03 | Explicit request routes | Reads, writes, object operations, and enqueue/consume paths have validated semantics |
| P04 | Simulation | Seeded event simulation records requests, waiting, processing, network transfer, and terminal outcomes |
| P05 | Assessment | Every requirement shows Pass, Fail, Not evaluated, or Incomplete with evidence |
| P06 | AI explanation | Summaries identify evidence and remain separate from deterministic verdicts |
| P07 | Prove this fix | Up to two valid candidate changes are compared with an immutable baseline using matching workloads |
| P08 | First-failure replay | User can inspect the trace or aggregate window that first violates a requirement |
| P09 | Assumption tests | Catalogue includes warm/cold cache and concentrated-demand scenarios |
| P10 | Local history and export | Designs, assessed revisions, summaries, and evidence can be saved and exported |
| P11 | Accessible animation | Playback supports pause, speed control, step-through, and reduced motion |
| P12 | Failure handling | AI failure does not erase simulation results; interrupted simulations cannot pass |

## 5. Main user stories

- As a beginner, I can understand the purpose of each component and start from sensible defaults.
- As a learner, I can identify which requirement failed and inspect the supporting request or time window.
- As an experimenter, I can change one design decision and compare it fairly with the previous version.
- As an advanced learner, I can examine the assumptions behind a passing result.
- As a builder, I can export a reproducible explanation of the problem, design, result, and change.

## 6. Experience

The challenge library opens into a desktop-first canvas. A requirements panel remains reachable throughout the exercise. Components expose basic settings first; detailed processing profiles appear in an Advanced section.

Quick preview gives immediate feedback but cannot mark a challenge complete. Assess design runs the full versioned suite. The results panel shows requirement outcomes before cost/latency comparisons and AI advice.

AI hints are opt-in. Before a first attempt, offer questions and explanations; reveal a complete proposed design only on an explicit learner action. The user may inspect a reference approach after an attempt. It is one acceptable approach, not an answer key the learner must match.

## 7. Comparison behavior

The learner can compare the current revision, one saved revision, or up to two proposed candidates. Comparisons require the same challenge version, workload bundle, component profile version, and assessment rules.

Show: requirement changes, metrics per scenario, cost difference, configuration changes, assumptions, and trade-offs. If no candidate passes, say so. A cheaper candidate that violates a hard requirement is not recommended as a successful solution.

Use the phrase Best among tested alternatives only when supported by a declared objective, initially lowest credits/hour among candidates that pass every required scenario/seed.

## 8. Initial scope and expansion

The first milestone is one complete catalogue exercise. The release expands to the five challenges and ten components specified in CHALLENGE-SPEC and COMPONENT-CATALOG.

Later: changing product requirements, learner predictions, adaptive challenge recommendations, real-service calibration experiments, regional design, transactional inventory/payment challenges, real-time chat, and AI-serving architecture.

Not in v0.1: accounts, collaboration, public leaderboards, cloud provisioning, executing arbitrary user code, Kubernetes orchestration, exact vendor capacity prediction, custom ML training, billing, a production monitoring integration, or full consensus-protocol simulation.

## 9. Success measures

Product validation targets, not achieved results:

- In a small usability study, at least four of five participants can explain one failed requirement and one tested improvement without coaching from the facilitator.
- A first-time learner can complete the catalogue build/run/inspect/compare journey with in-app guidance.
- Every accepted AI numeric claim resolves to a saved metric or a transparent computation over saved metrics.
- The default playground remains interactive during assessment on the target M1 Max / 32 GB machine; measure against TEST-PLAN budgets.
- Every released challenge has independently inspected passing and failing fixtures in the simulator. Human review validates the exercise and rubric, not production reliability.

No fabricated learning-impact, latency, or adoption claims should appear in a demo or README.

## 10. Definition of done

All P01–P12 acceptance conditions pass. Five challenges have working routes, reference fixtures, and verified scoring. A learner can finish a run with AI unavailable, then request a grounded review when the provider becomes available. Reopening a completed run reproduces its saved outcome without new model calls. A clean demonstration shows an initial failure, supporting evidence, a tested revision, and the remaining trade-offs.
