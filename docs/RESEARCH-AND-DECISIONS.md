# Research baseline and decision record

AI System Design Simulator · researched 26 September 2026

## 1. Research scope

Reviewed current product pages, public repository documentation, simulation documentation, reliability guidance and a relevant research paper. Competitor capabilities below are claims in their public material, not an independent benchmark or end-to-end test of those products. This is not an exhaustive novelty search.

## 2. Closest existing projects

| Source | Relevant public description | Implication for this prototype |
|---|---|---|
| [Breakscale repository](https://github.com/xevrion/breakscale) | Visual component modelling, discrete-event engine, finite queues, failures and seeded repeatability | Draw-and-simulate and chaos controls are established features; inspect modeling details rather than imitating only visuals |
| [SysSimulator](https://syssimulator.com/) | Browser design canvas, traffic/chaos simulation, blueprints and approximate cloud cost signals | A large component library or cost card alone is not a distinctive product position |
| [ChaosBench](https://chaosbench.com/) | Clarify, architect, chaos and defend workflow with AI critique | Interview questioning and incidents already exist; prioritize learning from controlled experiments |
| [Adeeb67 system-design-simulator](https://github.com/Adeeb67/system-design-simulator) | Documents simulation, scoring, reviews, challenges and comparisons; README says current review is deterministic without external LLM calls | Be precise about what is rule-based and what actually uses an LLM |

Do not copy claims that every simulation result is a real-world measurement. An event simulator still relies on abstractions and parameters. If borrowing implementation code, inspect its current license and satisfy its conditions; this specification does not require a fork.

## 3. Technical and methodological sources

1. [SimPy shared resources](https://simpy.readthedocs.io/en/stable/simpy_intro/shared_resources.html). Supports event-driven modeling of finite capacity and waiting. It does not supply ready-made accurate SQL/cache/cloud models.
2. [Google SRE Workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/). Separates user-oriented latency/availability from pipeline freshness/correctness and storage behavior. This informs metric selection, not the invented challenge thresholds.
3. [Grafana k6: Open and closed models](https://grafana.com/docs/k6/latest/using-k6/scenarios/concepts/open-vs-closed/). Explains why closed-loop load can taper when the target slows. This supports precomputed open-arrival traffic for capacity challenges.
4. [FoundationDB: Simulation and testing](https://apple.github.io/foundationdb/testing.html). Describes deterministic repeatability and combining simulation with real performance/failure testing. FoundationDB's integrated testing system is substantially deeper than the proposed educational prototype.
5. [AWS: Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/). Explains duplicate-effect risks and request identity. This informs separate attempt/effect accounting; it does not justify a universal exactly-once claim.
6. [React Flow documentation](https://reactflow.dev/learn). Reference for custom nodes/edges, validation, interactions and persistence. React Flow is the canvas foundation, not the simulation engine.
7. [AI for Distributed Systems Design: Scalable Cloud Optimization Through Repeated LLMs Sampling And Simulators](https://arxiv.org/abs/2510.18897), Jacopo Tagliabue, submitted 20 October 2025. A preliminary policy-design study using an LLM generate-and-verify loop with a domain simulator. Relevant to AI proposals plus deterministic evaluation; not proof that an arbitrary architecture can be globally optimized.

## 4. Main decisions

| ID | Decision | Rationale |
|---|---|---|
| D01 | Deterministic engine/rubric own measurements and verdicts | AI prose alone cannot establish performance |
| D02 | Five graded challenges and ten modeled types in v0.1 | Enough breadth to teach core concepts while allowing complete implementation |
| D03 | Broad advanced catalogue documented, gated by support | Avoid misleading decorative components and unimplemented assessments |
| D04 | Python/SimPy backend, React/React Flow frontend | Clear separation of numerical behavior from a polished interaction layer |
| D05 | Original arrivals precomputed and reused for comparisons | Reduces confounding when designs are changed |
| D06 | Prove this fix is the main feature | Makes AI advice inspectable and exposes failed hypotheses |
| D07 | No single arbitrary architecture score | Visible requirements and trade-offs are easier to interpret |
| D08 | Fixed synthetic profiles and credits | Keeps the prototype simple without pretending to quote provider prices |
| D09 | Local single-user files | Appropriate for a mini-project; no auth/database/cloud infrastructure needed |
| D10 | No custom model training | Existing LLMs can review structured evidence and propose bounded edits |
| D11 | Repeat assessment across five seeds | Basic robustness check; not a production statistical guarantee |
| D12 | Comparison winner means best among tested candidates | The search is bounded and cannot prove global optimality |

## 5. Distinctive feature hypotheses

Prove this fix, first-failure replay and explicit assumption testing are recommended product priorities. The combination is intended to make the learning experience distinctive; research does not establish that no competitor offers similar features.

Later experiments: ask learners to predict the bottleneck, evolve the same product's requirements, compare simpler passing designs, and track misconceptions. Evaluate these with usability sessions before expanding the product.

## 6. Authored assumptions that require validation

The default service times, capacities, cost multipliers, challenge traffic, deadlines, sample counts and performance budgets are prototype design choices. They were not measured from AWS, PostgreSQL, Redis or the user's machine. Execute fixtures, assess feasibility and review the educational behavior before calling content verified.

The user's M1 Max / 32 GB target is a deployment constraint. It is not evidence that every proposed scenario completes within the target wall time. AI endpoint access and credential format remain runtime configuration decisions.

## 7. How to describe the finished project accurately

Permitted after implementation and verification: “An interactive system-design lab with a deterministic simulator, requirement checks and AI-suggested changes tested against the same workload.”

Avoid: “Predicts exactly how your production system will perform,” “proves your system is secure,” “finds the globally optimal architecture,” or invented performance/learning statistics. Publish observed demo results together with their workload and teaching-model assumptions.
