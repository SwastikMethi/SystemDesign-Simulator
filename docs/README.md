# AI System Design Simulator — prototype documentation

Version 0.1 · 26 September 2026 · Product and implementation specifications

For application setup and measured verification, start with the [project README](../README.md) and [acceptance evidence](ACCEPTANCE.md). This directory defines the product's intended behavior and document authority.

Build an interactive lab where a learner selects a challenge, draws an architecture, simulates traffic, checks requirements, and tests AI-suggested improvements.

The defining feature is **Prove this fix**: an AI recommendation becomes a reversible design change that is evaluated against the original design under the same workload. The application must show unsuccessful recommendations too.

## Read in this order

| Document | What it answers |
|---|---|
| [PRD.md](PRD.md) | Who is this for, what does the prototype do, and when is it complete? |
| [UI-UX-SPEC.md](UI-UX-SPEC.md) | How do the playground, animations, replay, and comparison work? |
| [TRD.md](TRD.md) | How should the application be implemented? |
| [SIMULATION-SPEC.md](SIMULATION-SPEC.md) | What is actually simulated and how are results calculated? |
| [COMPONENT-CATALOG.md](COMPONENT-CATALOG.md) | Which components exist, what do they model, and what comes later? |
| [CHALLENGE-SPEC.md](CHALLENGE-SPEC.md) | What are the five initial challenges and their assessment requirements? |
| [AI-COACH-SPEC.md](AI-COACH-SPEC.md) | How does AI produce grounded feedback and testable changes? |
| [DATA-API-SPEC.md](DATA-API-SPEC.md) | What data, files, and API contracts connect the application? |
| [TEST-PLAN.md](TEST-PLAN.md) | How are the engine, scoring, UI, and AI verified? |
| [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) | What should be built first, and what are the release gates? |
| [RESEARCH-AND-DECISIONS.md](RESEARCH-AND-DECISIONS.md) | Which research supports the approach, and which choices are assumptions? |

[examples/catalogue-challenge.json](examples/catalogue-challenge.json) and [examples/catalogue-starter-design.json](examples/catalogue-starter-design.json) illustrate the canonical catalogue challenge and a deliberately simple starting design. They are specification examples, not executed simulations or validated reference solutions.

## Scope in one minute

- Five assessed challenges: notes, URL shortener, product catalogue, photo delivery, notifications.
- Ten working component types: client, load balancer, API gateway, application service, SQL database, cache, message queue, worker, object storage, CDN.
- React + TypeScript + React Flow frontend; Python + FastAPI + SimPy backend.
- Local, single-user application. Files store progress, designs, and run evidence.
- Existing LLM accessed through a configurable server-side provider adapter. No custom model training.
- Simulation calculates metrics; deterministic rules assess requirements; AI explains and suggests experiments.
- Initial signature features: Prove this fix, first-failure replay, and explicit assumption tests.
- Wider component catalogue and harder challenges are documented expansion scope. Unsupported behavior cannot receive a passing assessment.

## Core journey

1. Read the challenge and its measurable requirements.
2. Build or edit a design using supported components and labeled routes.
3. Run a quick preview, then the full assessment.
4. Inspect failed requirements, component queues, and request traces.
5. Review an AI explanation with links to evidence.
6. Test up to two proposed changes against the unchanged baseline.
7. Adopt a passing revision, explain the trade-off, and save the result.

## Document authority

PRD owns scope. SIMULATION-SPEC owns numerical semantics. COMPONENT-CATALOG owns component behavior and profiles. CHALLENGE-SPEC owns workload and requirement definitions. DATA-API-SPEC owns persisted/API field names. UI-UX-SPEC owns interaction and presentation. AI-COACH-SPEC owns AI permissions and output rules. TEST-PLAN owns release gates.

Version all contracts together. Do not silently alter a challenge threshold to make a reference design pass. If a contradiction is found, resolve it in its owning document and update dependents before implementation continues.

## Honest boundaries

All default capacities and costs are teaching assumptions. Credits are fictional infrastructure units, not cloud quotations. Results apply to the specified simulation scenarios; they are not production certification, monthly availability forecasts, or proof of a globally optimal design.

This directory preserves the specification package. The application, executed simulation fixtures, and runtime measurements now live in the repository; see the links above for their current verification status. Cloud deployment remains outside scope.
