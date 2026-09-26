# AI System Design Simulator

A local learning lab for building an architecture, running reproducible traffic, inspecting failures, and testing changes against an unchanged baseline.

Five challenges cover notes, URL shortening, product catalogues, photo delivery, and notifications. Ten component types model request routing, queues, stores, caching, workers, load balancing, and delivery. Simulation and deterministic rules produce the assessment; an optional AI coach explains saved evidence and proposes testable changes.

## Run locally

Requires Python **3.13**, [uv](https://docs.astral.sh/uv/), and Node.js with npm. The recorded development environment uses Python 3.13.12 and Node 25.2.1.

```sh
uv sync --locked
cd frontend
npm ci
npm run build
cd ..
.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. If that port is occupied, choose another with `--port 8770` and open the corresponding address. Keep the service bound to loopback; this application is designed for one local user. Designs, immutable revisions, workload bundles, run evidence, and progress live in `.data/`. Set `AISD_DATA_DIR` to use another directory.

For frontend development, keep the backend running and run `npm run dev` inside `frontend/`. Open http://127.0.0.1:5173; Vite proxies API requests to port 8000. Set `AISD_API_TARGET=http://127.0.0.1:8770` when starting Vite if your backend uses that alternate port. API documentation is at the backend's `/docs` address.

## First exercise

1. Open **Product catalogue**, inspect the requirements, and start with its initial design.
2. Use **Quick preview** for a short experiment, then **Assess design** for all required scenarios and five seeds. Preview cannot earn completion.
3. Inspect a failed requirement and its trace or aggregate evidence. Playback only reads saved results.
4. Change the architecture or reveal the reference after an attempt. Compare the saved revision with the immutable assessed baseline.
5. Inspect both improvements and regressions, adopt a revision explicitly, and export the evidence from saved work.

Edits create unassessed changes; they never rewrite an earlier result. Comparisons use the same incoming workload and rank passing alternatives by fictional credits/hour. Equal-cost alternatives remain tied. A failed or interrupted run cannot complete a challenge.

## Optional AI coach

The simulator works without a provider. To enable reviews, set these variables in the shell that starts the backend:

```sh
export AISD_AI_BASE_URL='https://your-provider.example/v1'
export AISD_AI_MODEL='your-model-id'
export AISD_AI_API_KEY='your-key'
```

Use an OpenAI-compatible Chat Completions endpoint with JSON-schema response support. Provider calls require an explicit guidance or review action and consent. Explain and Hint use a saved draft and authored challenge context; reviews use recorded results. The key stays on the server. AI never changes the deterministic verdict, and a proposed patch must pass the same validation as a manual edit. Missing usage or provider cost remains unknown. Invalid responses retain their errors for inspection.

## Verification

```sh
.venv/bin/python -m pytest -q
.venv/bin/python -m backend.fixtures --output .implementation/fixture-results.json
cd frontend
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

The browser tests start a fresh backend with temporary data on port 8771. Keep that port free, or set `AISD_FRONTEND_URL` to a separately running isolated test application. Recordings and exported evidence are retained under `frontend/test-results/`.

The full fixture command executes all 20 initial/reference/failure/budget designs across **240 cases**. To measure only the catalogue reference:

```sh
.venv/bin/python -m backend.fixtures --challenge product-catalogue --fixture reference --output .implementation/catalogue-benchmark.json
```

On an Apple M1 Max with 32 GiB RAM, the recorded catalogue benchmark completed 15 cases in **30.47 seconds**, using approximately **119.4 MiB additional peak RSS**. This is a headless engine measurement; it excludes AI, browser rendering, and API artifact writing. See [acceptance evidence](docs/ACCEPTANCE.md) and [benchmark data](.implementation/catalogue-benchmark.json) for the exact scope and remaining validation.

## Model and limits

- Capacities, costs, traffic, and service distributions are teaching assumptions. Credits are fictional infrastructure units.
- Each assessment evaluates every required scenario at seeds 101, 202, 303, 404, and 505, with 60 seconds of warmup, 300 seconds of measurement, and 30 seconds of drain per case.
- Limits are 25 nodes, 60 edges, 32 instances per node, 100,000 original arrivals and 2,000,000 events per case, and two comparison candidates. Reaching the event cap makes the run incomplete.
- One simulation process executes cases sequentially. Canceling or restarting preserves available evidence and does not resume an unfinished simulation silently.
- Exports contain version and hash evidence. Imports preserve historical evidence as untrusted; a fresh graded rerun requires exact compatibility with the installed canonical workload. Importing an old pass never awards completion.
- Results describe this model and its tested scenarios. They do not certify production infrastructure or identify a globally optimal architecture.

The optional live-provider smoke test and five-person learning study have not been performed. Automated provider tests use controlled responses and do not establish model quality or learning impact.

## Project map

| Path | Purpose |
|---|---|
| `backend/contracts/`, `backend/workloads.py` | Validated data, route compilation, reproducible inputs |
| `backend/simulation/`, `backend/assessment/` | Event engine and deterministic assessment |
| `backend/api/`, `backend/storage/`, `backend/coach/` | Local API, persistence, jobs, optional provider |
| `frontend/` | React/TypeScript workspace and playback |
| `content/` | Five authored challenges, profiles, schemas, and fixtures |
| [docs/README.md](docs/README.md) | Original specification and document authority |
| [docs/BUILD-PLAN.md](docs/BUILD-PLAN.md) | Approved implementation plan |
| [docs/ACCEPTANCE.md](docs/ACCEPTANCE.md) | Verification evidence and release limits |

Regenerate shared contracts after intentional schema changes:

```sh
.venv/bin/python -m backend.content content/schemas
cd frontend
npm run generate:api
```

`backend/openapi.json` is the checked-in API contract. Export it from the application after backend API changes before regenerating TypeScript types.
