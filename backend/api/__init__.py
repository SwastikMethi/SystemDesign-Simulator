"""Versioned local HTTP API."""

from __future__ import annotations

import asyncio
import gzip
import io
import json
import os
import re
import shutil
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, File, Header, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import ValidationError

from backend.api.jobs import ASSESSMENT_VERSION, ENGINE_VERSION, Jobs, completion_eligible, now
from backend.api.models import *
from backend.content import list_challenges, load_challenge, load_fixture
from backend.coach import PROMPT_VERSION, ProviderOutputError, render_review, request_review, validate_review
from backend.contracts import PROFILES, SETTINGS, Challenge, DesignRevision, apply_patch, compile_design, design_hash, validate_draft
from backend.storage import Store, digest, new_id, valid_id
from backend.simulation import fault_bindings
from backend.workloads import GENERATOR_VERSION, WorkloadCase, bundle_hash, generate_case

PROFILE_VERSION = "0.1.0"
MAX_IMPORT_BYTES = 50 * 1024 * 1024
MAX_EXPANDED_WORKLOAD_BYTES = 100 * 1024 * 1024


def profile_hash() -> str:
    return digest([profile.model_dump(mode="json") for profile in PROFILES.values()])


def rank_alternatives(costs: dict[str, int], statuses: dict[str, str]) -> tuple[str | None, list[str]]:
    passing = [run_id for run_id, status in statuses.items() if status == "pass"]
    if not passing:
        return None, []
    cheapest = min(costs[run_id] for run_id in passing)
    tied = sorted(run_id for run_id in passing if costs[run_id] == cheapest)
    return (tied[0], []) if len(tied) == 1 else (None, tied)


def problem(status: int, code: str, message: str, **extra: Any) -> HTTPException:
    return HTTPException(status_code=status, detail=Error(code=code, message=message, **extra).model_dump(mode="json"))


def _challenge(challenge_id: str, version: str | None = None) -> Challenge:
    try:
        challenge = load_challenge(valid_id(challenge_id))
    except ValueError:
        raise problem(404, "not_found", "Challenge not found") from None
    if version is not None and version != challenge.version:
        raise problem(404, "not_found", "Challenge version not found")
    return challenge


def _design(store: Store, design_id: str, revision_id: str) -> DesignRevision:
    try:
        return store.get_design(valid_id(design_id), valid_id(revision_id))
    except (ValueError, FileNotFoundError):
        raise problem(404, "not_found", "Design revision not found") from None


def _manifest(store: Store, run_id: str) -> RunManifest:
    try:
        return RunManifest.model_validate(store.run_manifest(valid_id(run_id)))
    except (ValueError, FileNotFoundError, ValidationError):
        raise problem(404, "not_found", "Run not found") from None


def _make_revision(data: dict, challenge: Challenge) -> DesignRevision:
    try:
        revision = DesignRevision.model_validate(data)
    except ValidationError as exc:
        raise problem(422, "invalid_design", str(exc)) from None
    findings = validate_draft(revision, challenge)
    if findings:
        raise problem(422, "invalid_design", "; ".join(f.message for f in findings), node_ids=[i for f in findings for i in f.node_ids], edge_ids=[i for f in findings for i in f.edge_ids])
    return revision


def _cases(challenge: Challenge, body: RunInput) -> list[WorkloadCase]:
    if body.mode == "assessment":
        if body.experiment_scenario_id is not None or body.experiment_seed is not None:
            raise problem(422, "invalid_run", "Assessment cases are fixed by the challenge")
        return [generate_case(challenge, s.id, seed) for s in challenge.scenarios if s.required for seed in challenge.workload.assessment_seeds]
    if body.mode == "preview":
        if body.experiment_scenario_id is not None or body.experiment_seed is not None:
            raise problem(422, "invalid_run", "Preview case is fixed by the challenge")
        return [generate_case(challenge, next(s.id for s in challenge.scenarios if s.required), 101, "preview")]
    if body.experiment_scenario_id is None or body.experiment_seed is None:
        raise problem(422, "invalid_run", "Experiment scenario and seed are required")
    if not 0 <= body.experiment_seed <= 2**31 - 1:
        raise problem(422, "invalid_run", "Invalid experiment seed")
    return [generate_case(challenge, body.experiment_scenario_id, body.experiment_seed, "experiment")]


def create_app(data_dir: Path | None = None, frontend_dir: Path | None = None) -> FastAPI:
    app = FastAPI(title="AI System Design Simulator", version="0.1.0")
    app.state.data_dir = Path(data_dir or os.getenv("AISD_DATA_DIR", ".data"))
    app.state.store = None
    app.state.jobs = None
    app.state.lock = threading.RLock()

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        detail = exc.detail if isinstance(exc.detail, dict) and "code" in exc.detail else Error(code="http_error", message=str(exc.detail)).model_dump(mode="json")
        return JSONResponse(detail, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = {".".join(map(str, error["loc"])): error["msg"] for error in exc.errors()}
        return JSONResponse(Error(code="invalid_request", message="Request validation failed", field_errors=errors).model_dump(mode="json"), status_code=422)

    def store() -> Store:
        if app.state.store is None:
            with app.state.lock:
                if app.state.store is None:
                    app.state.store = Store(app.state.data_dir)
                    app.state.store.interrupt_unfinished()
        return app.state.store

    def jobs() -> Jobs:
        if app.state.jobs is None:
            with app.state.lock:
                if app.state.jobs is None:
                    app.state.jobs = Jobs(store())
        return app.state.jobs

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        try:
            host = urlsplit("http://" + request.headers.get("host", "")).hostname
        except ValueError:
            host = None
        origin = request.headers.get("origin")
        if host not in {"localhost", "127.0.0.1", "::1", "testserver"}:
            return Response(content=Error(code="forbidden_host", message="Loopback host required").model_dump_json(), status_code=403, media_type="application/json")
        if origin and not re.fullmatch(r"http://(?:localhost|127\.0\.0\.1|\[::1\])(?::\d{1,5})?", origin):
            return Response(content=Error(code="forbidden_origin", message="Loopback origin required").model_dump_json(), status_code=403, media_type="application/json")
        if request.method in {"POST", "DELETE"} and origin is None and request.headers.get("sec-fetch-site") == "cross-site":
            return Response(content=Error(code="forbidden_origin", message="Origin required").model_dump_json(), status_code=403, media_type="application/json")
        if request.method == "OPTIONS" and origin:
            return Response(status_code=204, headers={"Access-Control-Allow-Origin": origin, "Access-Control-Allow-Methods": "GET,POST,DELETE,OPTIONS", "Access-Control-Allow-Headers": "Content-Type,Idempotency-Key,Last-Event-ID", "Vary": "Origin"})
        response = await call_next(request)
        if origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
        return response

    @app.get("/api/v1/health", response_model=Health)
    def health():
        return Health(engine_version=ENGINE_VERSION, ai_configured=bool(os.getenv("AISD_AI_API_KEY") and os.getenv("AISD_AI_MODEL") and os.getenv("AISD_AI_BASE_URL")), ai_model=os.getenv("AISD_AI_MODEL"))

    @app.get("/api/v1/catalogue", response_model=Catalogue)
    def catalogue():
        names = {"client": ("Client", "Workload source"), "load_balancer": ("Load balancer", "Distribute requests"), "api_gateway": ("API gateway", "Rate limit requests"), "app_service": ("App service", "Handle application requests"), "sql_database": ("SQL database", "Store versioned keys"), "cache": ("Cache", "Serve repeated reads"), "message_queue": ("Message queue", "Acknowledge queued jobs"), "worker": ("Worker", "Process queued jobs"), "object_storage": ("Object storage", "Store objects"), "cdn": ("CDN", "Cache objects")}
        return Catalogue(component_types=[ComponentInfo(type=kind, label=label, purpose=purpose, profiles=[p.id for p in PROFILES.values() if p.component_type == kind], settings={key: {"min": rule[1], "max": rule[2]} if len(rule) == 3 and isinstance(rule[0], type) else {"choices": list(rule)} for key, rule in SETTINGS[kind].items()}) for kind, (label, purpose) in names.items()], profiles=list(PROFILES.values()))

    @app.get("/api/v1/challenges", response_model=ChallengeList)
    def challenges():
        progress = store().read_json(store().path("progress").with_suffix(".json")) if store().path("progress").with_suffix(".json").exists() else {}
        return ChallengeList(items=[ChallengeSummary(challenge_id=c.challenge_id, version=c.version, title=c.title, level=c.level, brief=c.brief, concepts=c.concepts, progress="passed" if progress.get(c.challenge_id) else "in_progress" if any(r.challenge_id == c.challenge_id for d in store().ids("designs") for r in store().revisions(d)) else "unstarted") for c in list_challenges()])

    @app.get("/api/v1/challenges/{challenge_id}", response_model=Challenge)
    def challenge(challenge_id: str, version: str | None = None):
        return _challenge(challenge_id, version)

    @app.get("/api/v1/challenges/{challenge_id}/fixtures/{name}", response_model=DesignRevision)
    def fixture(challenge_id: str, name: str):
        if name not in {"initial", "reference"}:
            raise problem(404, "not_found", "Fixture not found")
        try:
            return load_fixture(challenge_id, name)
        except ValueError:
            raise problem(404, "not_found", "Fixture not found") from None

    @app.post("/api/v1/designs", response_model=DesignCreated, status_code=201)
    def create_design(body: DesignInput):
        c = _challenge(body.challenge_id, body.challenge_version)
        design_id, revision_id = new_id("design"), new_id("revision")
        revision = _make_revision(dict(schema_version=1, design_id=design_id, revision_id=revision_id, challenge_id=c.challenge_id, challenge_version=c.version, created_at=now(), parent_revision_id=None, nodes=[n.model_dump(mode="json") for n in body.nodes], edges=[e.model_dump(mode="json") for e in body.edges]), c)
        store().save_design(revision)
        return DesignCreated(design_id=design_id, revision_id=revision_id, revision=revision)

    @app.get("/api/v1/designs/{design_id}", response_model=DesignMetadata)
    def design_metadata(design_id: str):
        revisions = store().revisions(valid_id(design_id))
        if not revisions:
            raise problem(404, "not_found", "Design not found")
        revisions.sort(key=lambda r: r.created_at)
        return DesignMetadata(design_id=design_id, challenge_id=revisions[0].challenge_id, challenge_version=revisions[0].challenge_version, latest_revision_id=revisions[-1].revision_id, revision_ids=[r.revision_id for r in revisions])

    @app.post("/api/v1/designs/{design_id}/revisions", response_model=DesignCreated, status_code=201)
    def create_revision(design_id: str, body: RevisionInput):
        parent = _design(store(), design_id, body.parent_revision_id)
        latest = design_metadata(design_id)
        if latest.latest_revision_id != body.parent_revision_id:
            raise problem(409, "stale_revision", "Parent is not the latest revision")
        c = _challenge(parent.challenge_id, parent.challenge_version)
        revision_id = new_id("revision")
        revision = _make_revision(dict(schema_version=1, design_id=design_id, revision_id=revision_id, challenge_id=c.challenge_id, challenge_version=c.version, created_at=now(), parent_revision_id=body.parent_revision_id, nodes=[n.model_dump(mode="json") for n in body.nodes], edges=[e.model_dump(mode="json") for e in body.edges]), c)
        store().save_design(revision)
        return DesignCreated(design_id=design_id, revision_id=revision_id, revision=revision)

    @app.get("/api/v1/designs/{design_id}/revisions/{revision_id}", response_model=DesignRevision)
    def get_revision(design_id: str, revision_id: str):
        return _design(store(), design_id, revision_id)

    @app.post("/api/v1/designs/validate", response_model=ValidationResult)
    def validate_design(body: DesignInput):
        c = _challenge(body.challenge_id, body.challenge_version)
        revision = DesignRevision(schema_version=1, design_id="draft", revision_id="draft", challenge_id=c.challenge_id, challenge_version=c.version, created_at=datetime.now(timezone.utc), parent_revision_id=None, nodes=body.nodes, edges=body.edges)
        findings = validate_draft(revision, c)
        runnable = False
        if not findings:
            try:
                compile_design(revision, c)
                runnable = True
            except ValueError as exc:
                findings.append(ValidationFinding(code="incomplete_route", message=str(exc)))
        return ValidationResult(valid_draft=not any(f.code != "incomplete_route" for f in findings), runnable=runnable, findings=findings, design_hash=design_hash(revision) if runnable else None)

    @app.post("/api/v1/runs", response_model=RunAccepted, status_code=202)
    def create_run(body: RunInput, idempotency_key: str | None = Header(default=None)):
        c = _challenge(body.challenge_id, body.challenge_version)
        design = _design(store(), body.design_id, body.revision_id)
        if (design.challenge_id, design.challenge_version) != (c.challenge_id, c.version):
            raise problem(409, "compatibility", "Design and challenge versions differ")
        try:
            compiled = compile_design(design, c)
        except ValueError as exc:
            raise problem(422, "invalid_run", str(exc)) from None
        imported_workload = False
        if body.workload_bundle_id:
            try:
                old = store().read_json(store().path("workloads", valid_id(body.workload_bundle_id), "manifest").with_suffix(".json"))
            except (ValueError, FileNotFoundError):
                raise problem(404, "not_found", "Workload bundle not found") from None
            if old["challenge_version"] != c.version or old.get("challenge_hash") != digest(c.model_dump(mode="json")) or old["generator_version"] != GENERATOR_VERSION or old.get("challenge_id") != c.challenge_id:
                raise problem(409, "compatibility", "Workload bundle versions differ")
            imported_workload = not old.get("trusted", False)
            canonical_assessment = imported_workload and body.mode == "assessment" and old.get("canonical_verified", False)
            if imported_workload and not canonical_assessment:
                if body.mode != "experiment" or body.experiment_scenario_id is not None or body.experiment_seed is not None:
                    raise problem(409, "compatibility", "Unverified imports can only run as ungraded experiments")
                try:
                    cases = [WorkloadCase.model_validate(store().read_gzip_jsonl(store().path("workloads", body.workload_bundle_id, case_id).with_suffix(".jsonl.gz"))[0]) for case_id in old["case_hashes"]]
                except (ValueError, FileNotFoundError, IndexError, KeyError):
                    raise problem(409, "compatibility", "Imported workload cases are unavailable") from None
            else:
                try:
                    cases = _cases(c, body)
                except ValueError as exc:
                    raise problem(422, "invalid_run", str(exc)) from None
            workload_digest = bundle_hash(cases)
            if old["workload_hash"] != workload_digest or any(case.challenge_id != c.challenge_id or case.challenge_version != c.version for case in cases):
                raise problem(409, "compatibility", "Workload content hash differs")
            if not imported_workload or canonical_assessment:
                try:
                    stored_cases = [WorkloadCase.model_validate(store().read_gzip_jsonl(store().path("workloads", body.workload_bundle_id, f"{case.scenario_id}-{case.seed}").with_suffix(".jsonl.gz"))[0]) for case in cases]
                except (ValueError, FileNotFoundError, IndexError):
                    raise problem(409, "compatibility", "Stored workload is unavailable") from None
                if bundle_hash(stored_cases) != workload_digest:
                    raise problem(409, "compatibility", "Stored workload was modified")
            bundle_id = body.workload_bundle_id
        else:
            try:
                cases = _cases(c, body)
            except ValueError as exc:
                raise problem(422, "invalid_run", str(exc)) from None
            workload_digest = bundle_hash(cases)
            bundle_id = new_id("bundle")
        config_hash = digest({"mode": body.mode, "workload_hash": workload_digest, "engine_version": ENGINE_VERSION, "assessment_version": ASSESSMENT_VERSION})
        key_path = None
        if idempotency_key:
            if len(idempotency_key) > 120 or not re.fullmatch(r"[A-Za-z0-9_-]+", idempotency_key):
                raise problem(422, "invalid_idempotency_key", "Invalid idempotency key")
            key_path = store().path("idempotency", digest("run:" + idempotency_key)).with_suffix(".json")
        with app.state.lock:
            if key_path and key_path.exists():
                record = store().read_json(key_path)
                if record["body_hash"] != digest(body.model_dump(mode="json")):
                    raise problem(409, "idempotency_conflict", "Key already used with different input")
                return RunAccepted(run_id=record["id"])
            run_id = new_id("run")
            if not body.workload_bundle_id:
                for case in cases:
                    store().write_gzip_jsonl(store().path("workloads", bundle_id, f"{case.scenario_id}-{case.seed}").with_suffix(".jsonl.gz"), [case.model_dump(mode="json")])
                store().write_json(store().path("workloads", bundle_id, "manifest").with_suffix(".json"), dict(bundle_id=bundle_id, challenge_id=c.challenge_id, challenge_version=c.version, challenge_hash=digest(c.model_dump(mode="json")), generator_version=GENERATOR_VERSION, workload_hash=workload_digest, case_hashes={f"{case.scenario_id}-{case.seed}": digest(case.model_dump(mode="json")) for case in cases}, trusted=True), immutable=True)
            manifest = RunManifest(run_id=run_id, mode=body.mode, execution_status="queued", assessment_status="not_evaluated", design_id=design.design_id, revision_id=design.revision_id, challenge_id=c.challenge_id, challenge_version=c.version, challenge_hash=digest(c.model_dump(mode="json")), engine_version=ENGINE_VERSION, assessment_version=ASSESSMENT_VERSION, profile_version=PROFILE_VERSION, profile_hash=profile_hash(), workload_generator_version=GENERATOR_VERSION, design_hash=compiled.design_hash, workload_hash=workload_digest, run_config_hash=config_hash, workload_bundle_id=bundle_id, case_ids=[f"{case.scenario_id}-{case.seed}" for case in cases], created_at=datetime.now(timezone.utc), artifact_refs={"assessment": f"runs/{run_id}/assessment.json"}, trusted_workload=not imported_workload or canonical_assessment)
            store().save_run_manifest(manifest.model_dump(mode="json"))
            if not jobs().enqueue(run_id, c, design, cases):
                store().manifest_path(run_id).unlink(missing_ok=True)
                raise problem(503, "queue_full", "Simulation queue is full", retryable=True)
            if key_path:
                store().write_json(key_path, {"body_hash": digest(body.model_dump(mode="json")), "id": run_id}, immutable=True)
            return RunAccepted(run_id=run_id)

    @app.get("/api/v1/runs/{run_id}", response_model=RunManifest)
    def get_run(run_id: str):
        return _manifest(store(), run_id)

    @app.post("/api/v1/runs/{run_id}/cancel", response_model=RunManifest)
    def cancel_run(run_id: str):
        manifest = _manifest(store(), run_id)
        if manifest.execution_status in {"queued", "running"}:
            jobs().cancel(run_id)
        return _manifest(store(), run_id)

    @app.get("/api/v1/runs/{run_id}/events")
    async def run_events(run_id: str, request: Request, last_event_id: int | None = Header(default=None)):
        _manifest(store(), run_id)
        async def stream():
            cursor = last_event_id or 0
            while True:
                events = list(jobs().events[run_id])
                if not events:
                    event = jobs().emit(run_id, "resync")
                    yield f"id: {event['event_id']}\ndata: {json.dumps(event)}\n\n"
                    cursor = event["event_id"]
                    events = []
                if events and cursor and cursor < events[0]["event_id"] - 1:
                    event = jobs().emit(run_id, "resync")
                    yield f"id: {event['event_id']}\ndata: {json.dumps(event)}\n\n"
                    cursor = event["event_id"]
                for event in events:
                    if event["event_id"] > cursor:
                        yield f"id: {event['event_id']}\ndata: {json.dumps(event)}\n\n"
                        cursor = event["event_id"]
                if await request.is_disconnected():
                    return
                if _manifest(store(), run_id).execution_status in {"completed", "canceled", "failed", "interrupted"}:
                    return
                await asyncio.sleep(.5)
        return StreamingResponse(stream(), media_type="text/event-stream")

    @app.get("/api/v1/runs/{run_id}/results", response_model=RunResults)
    def run_results(run_id: str):
        manifest = _manifest(store(), run_id)
        cases = [CaseResult.model_validate(store().read_json(store().case_path(run_id, case_id, "result.json"))) for case_id in manifest.completed_case_ids]
        assessment_path = store().path("runs", run_id, "assessment").with_suffix(".json")
        assessment = AssessmentResult.model_validate(store().read_json(assessment_path)) if assessment_path.exists() else None
        return RunResults(run_id=run_id, assessment=assessment, cases=cases)

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}/snapshots", response_model=SnapshotPage)
    def snapshots(run_id: str, case_id: str):
        manifest = _manifest(store(), run_id)
        if case_id not in manifest.case_ids:
            raise problem(404, "not_found", "Case not found")
        path = store().case_path(run_id, case_id, "snapshots.jsonl.gz")
        return SnapshotPage(case_id=case_id, items=store().read_gzip_jsonl(path) if path.exists() else [])

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}/outcomes", response_model=OutcomePage)
    def outcomes(run_id: str, case_id: str):
        manifest = _manifest(store(), run_id)
        if case_id not in manifest.case_ids:
            raise problem(404, "not_found", "Case not found")
        path = store().case_path(run_id, case_id, "outcomes.jsonl.gz")
        records = store().read_gzip_jsonl(path) if path.exists() else []
        return OutcomePage(case_id=case_id, requests=[RequestOutcome.model_validate({k: v for k, v in record.items() if k != "kind"}) for record in records if record["kind"] == "request"], jobs=[JobOutcome.model_validate({k: v for k, v in record.items() if k != "kind"}) for record in records if record["kind"] == "job"])

    @app.get("/api/v1/runs/{run_id}/cases/{case_id}/traces/{trace_id}", response_model=Trace)
    def trace(run_id: str, case_id: str, trace_id: str):
        manifest = _manifest(store(), run_id)
        if case_id not in manifest.case_ids:
            raise problem(404, "not_found", "Case not found")
        path = store().case_path(run_id, case_id, "traces.jsonl.gz")
        if path.exists():
            for record in store().read_gzip_jsonl(path):
                if record.get("trace_id") == trace_id:
                    return record
        raise problem(404, "not_found", "Trace not found")

    @app.get("/api/v1/collection", response_model=Collection)
    def collection():
        items = []
        for design_id in store().ids("designs"):
            revisions = store().revisions(design_id)
            if revisions:
                revisions.sort(key=lambda r: r.created_at)
                first = revisions[0]
                items.append(CollectionItem(id=design_id, kind="design", title=_challenge(first.challenge_id).title, challenge_id=first.challenge_id, created_at=first.created_at))
        for run_id in store().ids("runs"):
            try:
                run = _manifest(store(), run_id)
                items.append(CollectionItem(id=run_id, kind="run", title=_challenge(run.challenge_id).title, challenge_id=run.challenge_id, created_at=run.created_at, status=run.execution_status))
            except HTTPException:
                continue
        base = store().path("comparisons")
        if base.exists():
            for path in base.glob("*.json"):
                try:
                    record = ComparisonRecord.model_validate(store().read_json(path))
                    baseline = _manifest(store(), record.baseline_run_id)
                    items.append(CollectionItem(id=record.comparison_id, kind="comparison", title=_challenge(baseline.challenge_id).title, challenge_id=baseline.challenge_id, created_at=baseline.created_at, status=record.status))
                except (ValueError, HTTPException):
                    continue
        return Collection(items=sorted(items, key=lambda item: item.created_at, reverse=True))

    @app.delete("/api/v1/designs/{design_id}", response_model=DeleteResult)
    def delete_design(design_id: str):
        valid_id(design_id)
        folder = store().path("designs", design_id)
        if not folder.exists():
            raise problem(404, "not_found", "Design not found")
        if any(_manifest(store(), run_id).design_id == design_id for run_id in store().ids("runs")):
            raise problem(409, "referenced", "Design has saved runs")
        shutil.rmtree(folder)
        return DeleteResult(deleted=True, id=design_id)

    @app.delete("/api/v1/runs/{run_id}", response_model=DeleteResult)
    def delete_run(run_id: str):
        manifest = _manifest(store(), run_id)
        if manifest.execution_status in {"queued", "running"}:
            raise problem(409, "active_run", "Cancel the run before deleting it")
        base = store().path("comparisons")
        if base.exists() and any(run_id in (record.get("baseline_run_id"), *record.get("candidate_run_ids", [])) for path in base.glob("*.json") if (record := store().read_json(path))):
            raise problem(409, "referenced", "Run belongs to a comparison")
        shutil.rmtree(store().path("runs", run_id))
        progress_path = store().path("progress").with_suffix(".json")
        if progress_path.exists():
            progress = store().read_json(progress_path)
            if progress.get(manifest.challenge_id, {}).get("run_id") == run_id:
                alternatives = [_manifest(store(), item) for item in store().ids("runs")]
                passing = [item for item in alternatives if item.challenge_id == manifest.challenge_id and completion_eligible(item)]
                if passing:
                    newest = max(passing, key=lambda item: item.finished_at)
                    progress[manifest.challenge_id] = {"run_id": newest.run_id, "challenge_version": newest.challenge_version, "design_hash": newest.design_hash, "completed_at": newest.finished_at.isoformat()}
                else:
                    progress.pop(manifest.challenge_id, None)
                store().write_json(progress_path, progress)
        return DeleteResult(deleted=True, id=run_id)

    @app.delete("/api/v1/comparisons/{comparison_id}", response_model=DeleteResult)
    def delete_comparison(comparison_id: str):
        path = store().path("comparisons", valid_id(comparison_id)).with_suffix(".json")
        if not path.exists():
            raise problem(404, "not_found", "Comparison not found")
        record = ComparisonRecord.model_validate(store().read_json(path))
        if record.status in {"queued", "running"}:
            raise problem(409, "active_comparison", "Comparison is still running")
        path.unlink()
        return DeleteResult(deleted=True, id=comparison_id)

    @app.post("/api/v1/runs/{run_id}/snapshots", response_model=SavedSnapshot, status_code=201)
    def save_snapshot(run_id: str, body: SaveSnapshotInput):
        manifest = _manifest(store(), run_id)
        if body.case_id not in manifest.case_ids:
            raise problem(404, "not_found", "Case not found")
        path = store().case_path(run_id, body.case_id, "snapshots.jsonl.gz")
        if not path.exists():
            raise problem(409, "not_ready", "No saved snapshots yet")
        snapshots_data = store().read_gzip_jsonl(path)
        item = next((value for value in snapshots_data if value.get("time_us") == body.time_us), None)
        if item is None:
            raise problem(404, "not_found", "Snapshot time not found")
        snapshot_id = new_id("snapshot")
        saved = SavedSnapshot(snapshot_id=snapshot_id, title=body.title, run_id=run_id, case_id=body.case_id, time_us=body.time_us, created_at=datetime.now(timezone.utc), snapshot=item)
        store().write_json(store().path("snapshots", snapshot_id, "snapshot").with_suffix(".json"), saved.model_dump(mode="json"), immutable=True)
        return saved

    @app.get("/api/v1/snapshots", response_model=SnapshotList)
    def saved_snapshots():
        return SnapshotList(items=[SavedSnapshot.model_validate(store().read_json(store().path("snapshots", item, "snapshot").with_suffix(".json"))) for item in store().ids("snapshots")])

    @app.get("/api/v1/snapshots/{snapshot_id}", response_model=SavedSnapshot)
    def saved_snapshot(snapshot_id: str):
        try:
            return SavedSnapshot.model_validate(store().read_json(store().path("snapshots", valid_id(snapshot_id), "snapshot").with_suffix(".json")))
        except (ValueError, FileNotFoundError):
            raise problem(404, "not_found", "Saved snapshot not found") from None

    @app.delete("/api/v1/snapshots/{snapshot_id}", response_model=DeleteResult)
    def delete_snapshot(snapshot_id: str):
        path = store().path("snapshots", valid_id(snapshot_id))
        if not path.exists():
            raise problem(404, "not_found", "Saved snapshot not found")
        shutil.rmtree(path)
        return DeleteResult(deleted=True, id=snapshot_id)

    @app.post("/api/v1/runs/{run_id}/reviews", response_model=ReviewAccepted, status_code=202)
    def create_review(run_id: str, body: ReviewRequest, idempotency_key: str | None = Header(default=None)):
        manifest = _manifest(store(), run_id)
        if manifest.execution_status != "completed":
            raise problem(409, "not_ready", "Run must complete before review")
        comparison = get_comparison(body.comparison_id) if body.comparison_id else None
        if comparison and (comparison.status != "completed" or comparison.baseline_run_id != run_id):
            raise problem(409, "compatibility", "Comparison is not complete for this baseline")
        settings = health()
        if not settings.ai_configured:
            raise problem(503, "provider_unavailable", "AI provider is not configured", retryable=True)
        idempotency_path = store().path("idempotency", digest(f"review:{run_id}:{idempotency_key}")) .with_suffix(".json") if idempotency_key else None
        with app.state.lock:
            if idempotency_path and idempotency_path.exists():
                record = store().read_json(idempotency_path)
                if record["body_hash"] != digest(body.model_dump(mode="json")):
                    raise problem(409, "idempotency_conflict", "Key already used with different input")
                return ReviewAccepted(review_id=record["id"])
            review_id = new_id("review")
            assessment_summary = {"pass": "Assessment passed.", "fail": "Assessment failed.", "incomplete": "Assessment evidence is incomplete.", "not_evaluated": "This run was not assessed."}[manifest.assessment_status]
            record = ReviewRecord(review_id=review_id, run_id=run_id, status="queued", provider=os.getenv("AISD_AI_BASE_URL"), model=settings.ai_model, prompt_version=PROMPT_VERSION, created_at=datetime.now(timezone.utc), assessment_status=manifest.assessment_status, summary=assessment_summary)
            path = store().path("runs", run_id, "reviews", review_id).with_suffix(".json")
            store().write_json(path, record.model_dump(mode="json"))
            if idempotency_path:
                store().write_json(idempotency_path, {"body_hash": digest(body.model_dump(mode="json")), "id": review_id}, immutable=True)
        def work():
            current = record.model_dump(mode="json")
            try:
                challenge = _challenge(manifest.challenge_id, manifest.challenge_version)
                design = _design(store(), manifest.design_id, manifest.revision_id)
                results = run_results(run_id)
                evidence = [item for case in results.cases for item in case.evidence]
                summary = {"assessment_status": manifest.assessment_status, "case_results": [{"case_id": c.case_id, "operation_metrics": {op: {key: value.model_dump(mode="json") for key, value in metrics.items()} for op, metrics in c.operation_metrics.items()}, "requirement_outcomes": [r.model_dump(mode="json") for r in c.requirement_outcomes]} for c in results.cases]}
                if comparison:
                    evidence = [item.model_copy(update={"evidence_id": f"{run_id}:{item.evidence_id}"}) for item in evidence]
                    for candidate_id in comparison.candidate_run_ids:
                        candidate_results = run_results(candidate_id)
                        evidence.extend(item.model_copy(update={"evidence_id": f"{candidate_id}:{item.evidence_id}"}) for case in candidate_results.cases for item in case.evidence)
                    summary["comparison"] = comparison.model_dump(mode="json")
                parsed, raw, usage, latency = request_review(challenge, design, evidence, summary)
                current.update(raw_response=raw, usage=usage, latency_ms=latency)
                validated = validate_review(parsed, evidence, design, challenge)
                current.update(render_review(validated, evidence), status="completed")
            except ProviderOutputError as exc:
                current.update(status="failed", error=str(exc)[:500], validation_errors=[str(exc)[:500]], raw_response=exc.raw_response, usage=exc.usage, latency_ms=exc.latency_ms)
            except Exception as exc:
                current.update(status="failed", error=str(exc)[:500], validation_errors=[str(exc)[:500]])
            current["finished_at"] = now()
            try:
                saved = ReviewRecord.model_validate(current)
            except ValidationError:
                fallback = record.model_dump(mode="json")
                fallback.update(status="failed", finished_at=current["finished_at"], error="Invalid provider response metadata", validation_errors=["Invalid provider response metadata"], raw_response=current.get("raw_response") if isinstance(current.get("raw_response"), str) else None)
                saved = ReviewRecord.model_validate(fallback)
            store().write_json(path, saved.model_dump(mode="json"))
        threading.Thread(target=work, daemon=True).start()
        return ReviewAccepted(review_id=review_id)

    @app.get("/api/v1/runs/{run_id}/reviews/{review_id}", response_model=ReviewRecord)
    def get_review(run_id: str, review_id: str):
        _manifest(store(), run_id)
        try:
            return ReviewRecord.model_validate(store().read_json(store().path("runs", run_id, "reviews", valid_id(review_id)).with_suffix(".json")))
        except (ValueError, FileNotFoundError):
            raise problem(404, "not_found", "Review not found") from None

    @app.post("/api/v1/comparisons", response_model=ComparisonAccepted, status_code=202)
    def create_comparison(body: ComparisonInput, idempotency_key: str | None = Header(default=None)):
        baseline = _manifest(store(), body.baseline_run_id)
        if baseline.mode != "assessment" or baseline.execution_status != "completed" or baseline.assessment_status not in {"pass", "fail"} or not baseline.trusted_workload:
            raise problem(409, "compatibility", "Baseline requires a complete trusted assessment")
        assessment_path = store().path("runs", baseline.run_id, "assessment").with_suffix(".json")
        if not assessment_path.exists():
            raise problem(409, "compatibility", "Baseline assessment bundle is missing")
        challenge = _challenge(baseline.challenge_id, baseline.challenge_version)
        base_design = _design(store(), baseline.design_id, baseline.revision_id)
        candidates: list[DesignRevision] = []
        candidate_indices: list[int] = []
        rejected: list[dict[str, Any]] = []
        seen_hashes = {baseline.design_hash}
        for index, choice in enumerate(body.candidates):
            try:
                if (choice.patch is None) == (choice.revision_id is None):
                    raise ValueError("Choose exactly one patch or saved revision")
                if choice.patch is not None:
                    candidate = apply_patch(base_design, choice.patch, challenge)
                    candidate = candidate.model_copy(update={"design_id": new_id("design"), "revision_id": new_id("revision"), "created_at": datetime.now(timezone.utc)})
                else:
                    candidate = _design(store(), choice.design_id or baseline.design_id, choice.revision_id)
                if (candidate.challenge_id, candidate.challenge_version) != (challenge.challenge_id, challenge.version):
                    raise ValueError("Candidate challenge version differs")
                compile_design(candidate, challenge)
                candidate_hash = design_hash(candidate)
                if candidate_hash in seen_hashes:
                    raise ValueError("Candidate repeats baseline or another candidate")
                seen_hashes.add(candidate_hash)
                candidates.append(candidate)
                candidate_indices.append(index)
            except (ValueError, ValidationError, HTTPException) as exc:
                rejected.append({"index": index, "status": "rejected", "validation_error": exc.detail["message"] if isinstance(exc, HTTPException) else str(exc)[:500], "candidate": choice.model_dump(mode="json")})
        bundle_path = store().path("workloads", baseline.workload_bundle_id, "manifest").with_suffix(".json")
        if not bundle_path.exists():
            raise problem(409, "compatibility", "Baseline workload bundle is missing")
        bundle = store().read_json(bundle_path)
        if not bundle.get("trusted") or bundle["workload_hash"] != baseline.workload_hash or bundle["challenge_version"] != challenge.version or bundle.get("challenge_hash") != baseline.challenge_hash or baseline.challenge_hash != digest(challenge.model_dump(mode="json")) or bundle["generator_version"] != GENERATOR_VERSION or baseline.profile_version != PROFILE_VERSION or baseline.profile_hash != profile_hash() or baseline.engine_version != ENGINE_VERSION or baseline.assessment_version != ASSESSMENT_VERSION:
            raise problem(409, "compatibility", "Baseline versions or workload hashes differ")
        cases = []
        for case_id in baseline.case_ids:
            path = store().path("workloads", baseline.workload_bundle_id, case_id).with_suffix(".jsonl.gz")
            try:
                cases.append(WorkloadCase.model_validate(store().read_gzip_jsonl(path)[0]))
            except (ValueError, FileNotFoundError, IndexError):
                raise problem(409, "compatibility", "Workload case is unavailable") from None
        if bundle_hash(cases) != baseline.workload_hash:
            raise problem(409, "compatibility", "Workload content hash differs")
        try:
            baseline_bindings = [fault_bindings(challenge, base_design, case) for case in cases]
        except ValueError as exc:
            raise problem(409, "compatibility", f"Baseline fault target is invalid: {exc}") from None
        compatible_candidates = []
        for index, candidate in zip(candidate_indices, candidates):
            try:
                changed = [f"{case.scenario_id}-{case.seed}" for case, binding in zip(cases, baseline_bindings) if fault_bindings(challenge, candidate, case) != binding]
            except ValueError as exc:
                rejected.append({"index": index, "status": "rejected", "validation_error": str(exc)[:500], "candidate": body.candidates[index].model_dump(mode="json")})
                continue
            if changed:
                rejected.append({"index": index, "status": "rejected", "validation_error": f"Required fault binding changes in case {changed[0]}", "candidate": body.candidates[index].model_dump(mode="json")})
            else:
                compatible_candidates.append(candidate)
        candidates = compatible_candidates
        key_path = store().path("idempotency", digest(f"comparison:{idempotency_key}")) .with_suffix(".json") if idempotency_key else None
        with app.state.lock:
            if key_path and key_path.exists():
                saved = store().read_json(key_path)
                if saved["body_hash"] != digest(body.model_dump(mode="json")):
                    raise problem(409, "idempotency_conflict", "Key already used with different input")
                return ComparisonAccepted(comparison_id=saved["id"])
            if jobs().pending.qsize() + len(candidates) > jobs().capacity:
                raise problem(503, "queue_full", "Simulation queue is full", retryable=True)
            comparison_id = new_id("comparison")
            candidate_run_ids = []
            for candidate in candidates:
                if candidate.design_id != baseline.design_id and not store().path("designs", candidate.design_id, candidate.revision_id).with_suffix(".json").exists():
                    store().save_design(candidate)
                run_id = new_id("run")
                candidate_run_ids.append(run_id)
                manifest = RunManifest(run_id=run_id, mode="assessment", execution_status="queued", assessment_status="not_evaluated", design_id=candidate.design_id, revision_id=candidate.revision_id, challenge_id=challenge.challenge_id, challenge_version=challenge.version, challenge_hash=baseline.challenge_hash, engine_version=ENGINE_VERSION, assessment_version=ASSESSMENT_VERSION, profile_version=PROFILE_VERSION, profile_hash=baseline.profile_hash, workload_generator_version=GENERATOR_VERSION, design_hash=design_hash(candidate), workload_hash=baseline.workload_hash, run_config_hash=baseline.run_config_hash, workload_bundle_id=baseline.workload_bundle_id, case_ids=baseline.case_ids, created_at=datetime.now(timezone.utc), artifact_refs={"assessment": f"runs/{run_id}/assessment.json"}, comparison_id=comparison_id)
                store().save_run_manifest(manifest.model_dump(mode="json"))
                if not jobs().enqueue(run_id, challenge, candidate, cases):
                    raise problem(503, "queue_full", "Simulation queue is full", retryable=True)
            record = ComparisonRecord(comparison_id=comparison_id, baseline_run_id=baseline.run_id, workload_bundle_id=baseline.workload_bundle_id, status="queued" if candidates else "completed", candidate_revision_ids=[c.revision_id for c in candidates], candidate_run_ids=candidate_run_ids, rejected_candidates=rejected, winner_run_id=baseline.run_id if not candidates and baseline.assessment_status == "pass" else None)
            comparison_path = store().path("comparisons", comparison_id).with_suffix(".json")
            store().write_json(comparison_path, record.model_dump(mode="json"))
            if key_path:
                store().write_json(key_path, {"body_hash": digest(body.model_dump(mode="json")), "id": comparison_id}, immutable=True)
        def watch():
            current = record.model_dump(mode="json")
            current["status"] = "running"
            store().write_json(comparison_path, current)
            while True:
                runs = [_manifest(store(), item) for item in candidate_run_ids]
                if all(run.execution_status in {"completed", "failed", "canceled", "interrupted"} for run in runs):
                    break
                time.sleep(.25)
            if any(run.execution_status != "completed" for run in runs):
                current.update(status="failed", error="Candidate simulation did not complete")
            else:
                alternatives = [baseline, *runs]
                statuses = {run.run_id: run.assessment_status for run in alternatives}
                costs = {run.run_id: compile_design(_design(store(), run.design_id, run.revision_id), challenge).cost_credits_per_hour for run in alternatives}
                winner_id, tied_ids = rank_alternatives(costs, statuses)
                baseline_outcomes = {(o.requirement_id, o.scenario_id, o.seed, o.operation_id): o.status for o in run_results(baseline.run_id).assessment.requirement_outcomes}
                baseline_cases = {case.case_id: case for case in run_results(baseline.run_id).cases}
                differences = []
                for run in runs:
                    candidate_results = run_results(run.run_id)
                    assessment = candidate_results.assessment
                    changed = [{"requirement_id": outcome.requirement_id, "scenario_id": outcome.scenario_id, "seed": outcome.seed, "operation_id": outcome.operation_id, "baseline": baseline_outcomes.get((outcome.requirement_id, outcome.scenario_id, outcome.seed, outcome.operation_id)), "candidate": outcome.status} for outcome in assessment.requirement_outcomes if baseline_outcomes.get((outcome.requirement_id, outcome.scenario_id, outcome.seed, outcome.operation_id)) != outcome.status]
                    latency_deltas = []
                    for case in candidate_results.cases:
                        original = baseline_cases.get(case.case_id)
                        if original is None:
                            continue
                        for operation_id, metrics in case.operation_metrics.items():
                            for metric_name in ("response_p95_ms", "response_p99_ms"):
                                candidate_metric = metrics.get(metric_name)
                                baseline_metric = original.operation_metrics.get(operation_id, {}).get(metric_name)
                                if candidate_metric and baseline_metric and candidate_metric.value is not None and baseline_metric.value is not None:
                                    latency_deltas.append({"case_id": case.case_id, "operation_id": operation_id, "metric": metric_name, "baseline_ms": baseline_metric.value, "candidate_ms": candidate_metric.value, "delta_ms": candidate_metric.value - baseline_metric.value})
                    differences.append({"run_id": run.run_id, "assessment_status": run.assessment_status, "cost_credits_per_hour": costs[run.run_id], "cost_delta_credits_per_hour": costs[run.run_id] - costs[baseline.run_id], "requirement_status_changes": changed, "latency_deltas": latency_deltas})
                current.update(status="completed", winner_run_id=winner_id, tied_run_ids=tied_ids, differences=differences)
            store().write_json(comparison_path, current)
        if candidates:
            threading.Thread(target=watch, daemon=True).start()
        return ComparisonAccepted(comparison_id=comparison_id)

    @app.get("/api/v1/comparisons/{comparison_id}", response_model=ComparisonRecord)
    def get_comparison(comparison_id: str):
        try:
            record = ComparisonRecord.model_validate(store().read_json(store().path("comparisons", valid_id(comparison_id)).with_suffix(".json")))
        except (ValueError, FileNotFoundError):
            raise problem(404, "not_found", "Comparison not found") from None
        if record.status in {"queued", "running"} and any(_manifest(store(), run_id).execution_status in {"failed", "canceled", "interrupted"} for run_id in record.candidate_run_ids):
            record.status = "failed"
            record.error = "Candidate run stopped before comparison completed"
            store().write_json(store().path("comparisons", comparison_id).with_suffix(".json"), record.model_dump(mode="json"))
        return record

    @app.post("/api/v1/exports", response_model=ExportToken, status_code=201)
    def create_export(body: ExportInput):
        if not (body.design_ids or body.run_ids or body.comparison_ids):
            raise problem(422, "empty_export", "Select evidence to export")
        entries: dict[str, bytes] = {}
        def add(path: str, value: bytes):
            if len(entries) >= 500 or sum(map(len, entries.values())) + len(value) > MAX_IMPORT_BYTES:
                raise problem(422, "export_too_large", "Evidence export exceeds 50 MB")
            entries[path] = value
        selected_designs = set(body.design_ids)
        selected_runs = set(body.run_ids)
        selected_comparisons = set(body.comparison_ids)
        for comparison_id in body.comparison_ids:
            comparison = get_comparison(comparison_id)
            add(f"comparisons/{comparison_id}.json", json.dumps(comparison.model_dump(mode="json")).encode())
            selected_runs.update([comparison.baseline_run_id, *comparison.candidate_run_ids])
        for run_id in selected_runs:
            run = _manifest(store(), run_id)
            selected_designs.add(run.design_id)
            folder = store().path("runs", run_id)
            for path in folder.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    add(f"runs/{run_id}/{path.relative_to(folder).as_posix()}", path.read_bytes())
            bundle = store().path("workloads", run.workload_bundle_id)
            for path in bundle.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    add(f"workloads/{run.workload_bundle_id}/{path.relative_to(bundle).as_posix()}", path.read_bytes())
            add(f"challenges/{run.challenge_id}/{run.challenge_version}.json", _challenge(run.challenge_id, run.challenge_version).model_dump_json().encode())
        for design_id in selected_designs:
            revisions = store().revisions(valid_id(design_id))
            if not revisions:
                raise problem(404, "not_found", "Selected design not found")
            for revision in revisions:
                add(f"designs/{design_id}/{revision.revision_id}.json", revision.model_dump_json().encode())
            c = _challenge(revisions[0].challenge_id, revisions[0].challenge_version)
            add(f"challenges/{c.challenge_id}/{c.version}.json", c.model_dump_json().encode())
        add("profiles.json", json.dumps([p.model_dump(mode="json") for p in PROFILES.values()]).encode())
        add("LIMITATIONS.txt", b"Simulated evidence only. Imported data cannot award challenge completion. AI review does not determine verdicts.\n")
        add("manifest.json", json.dumps({"schema_version": 1, "platform": "ai-system-design-simulator", "engine_version": ENGINE_VERSION, "assessment_version": ASSESSMENT_VERSION, "profile_version": PROFILE_VERSION, "created_at": now()}).encode())
        token = new_id("export")
        path = store().path("exports", token).with_suffix(".zip")
        path.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(path, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
            for name, blob in entries.items():
                archive.writestr(name, blob)
        return ExportToken(token=token, download_url=f"/api/v1/exports/{token}")

    @app.get("/api/v1/exports/{token}")
    def download_export(token: str):
        path = store().path("exports", valid_id(token)).with_suffix(".zip")
        if not path.exists():
            raise problem(404, "not_found", "Export not found")
        return FileResponse(path, filename="system-design-evidence.zip", media_type="application/zip")

    @app.post("/api/v1/imports", response_model=ImportResult, status_code=201)
    async def import_evidence(file: UploadFile = File(...)):
        blob = await file.read(MAX_IMPORT_BYTES + 1)
        if len(blob) > MAX_IMPORT_BYTES:
            raise problem(422, "import_too_large", "ZIP exceeds 50 MB")
        try:
            archive = zipfile.ZipFile(io.BytesIO(blob))
        except zipfile.BadZipFile:
            raise problem(422, "invalid_zip", "Invalid evidence ZIP") from None
        infos = archive.infolist()
        if len(infos) > 500 or sum(i.file_size for i in infos) > MAX_IMPORT_BYTES:
            raise problem(422, "import_too_large", "ZIP contents exceed limits")
        allowed_root = {"manifest.json", "profiles.json", "LIMITATIONS.txt"}
        for info in infos:
            path = Path(info.filename)
            if info.is_dir():
                continue
            if info.filename.startswith("/") or "\\" in info.filename or ".." in path.parts or any(not part or part.startswith(".") for part in path.parts) or (info.external_attr >> 16) & 0o170000 == 0o120000:
                raise problem(422, "unsafe_zip", "ZIP has an unsafe path or link")
            if len(path.parts) > 5 or (len(path.parts) == 1 and info.filename not in allowed_root) or (len(path.parts) > 1 and path.parts[0] not in {"designs", "challenges", "workloads", "runs", "comparisons"}):
                raise problem(422, "unsafe_zip", "ZIP has unsupported entries")
            if info.file_size > MAX_IMPORT_BYTES or (info.compress_size and info.file_size > info.compress_size * 100):
                raise problem(422, "unsafe_zip", "ZIP entry exceeds limits")
        entries: dict[str, bytes] = {}
        for info in infos:
            if info.is_dir():
                continue
            if info.filename in entries:
                raise problem(422, "invalid_zip", "ZIP contains duplicate entries")
            try:
                entries[info.filename] = archive.read(info)
            except (zipfile.BadZipFile, RuntimeError, OSError, ValueError):
                raise problem(422, "invalid_zip", "ZIP contains unreadable entries") from None

        parsed_json: dict[str, Any] = {}
        for name, content in entries.items():
            if name.endswith(".json"):
                try:
                    parsed_json[name] = json.loads(content)
                except (ValueError, UnicodeError):
                    raise problem(422, "invalid_zip", f"Invalid JSON: {name}") from None

        def read_json_entry(name: str) -> dict[str, Any]:
            try:
                value = parsed_json[name]
            except KeyError:
                raise problem(422, "invalid_zip", f"Invalid JSON: {name}") from None
            if not isinstance(value, dict):
                raise problem(422, "invalid_zip", f"Expected JSON object: {name}")
            return value

        if "manifest.json" not in entries:
            raise problem(422, "invalid_zip", "Evidence manifest missing")
        manifest = read_json_entry("manifest.json")
        if manifest.get("schema_version") != 1 or manifest.get("platform") != "ai-system-design-simulator":
            raise problem(422, "invalid_zip", "Unsupported evidence manifest")
        import_id = new_id("import")
        prepared_designs: list[DesignRevision] = []
        prepared_bundles: list[tuple[str, Challenge, list[WorkloadCase], dict[str, Any], bool]] = []
        prepared_runs: list[tuple[Path, bytes]] = []
        imported_design_ids: list[str] = []
        imported_bundle_ids: list[str] = []
        imported_run_ids: list[str] = []
        design_map: dict[str, str] = {}
        for info in infos:
            path = Path(info.filename)
            if info.is_dir() or path.parts[0] != "designs":
                continue
            if len(path.parts) != 3 or not info.filename.endswith(".json"):
                raise problem(422, "invalid_zip", "Invalid design entry")
            try:
                raw = read_json_entry(info.filename)
                original = DesignRevision.model_validate(raw)
                c = _challenge(original.challenge_id, original.challenge_version)
                if validate_draft(original, c):
                    raise ValueError("invalid design")
                new_design_id = design_map.setdefault(original.design_id, new_id("design"))
                revision = original.model_copy(update={"design_id": new_design_id, "revision_id": new_id("revision"), "parent_revision_id": None, "created_at": datetime.now(timezone.utc)})
                prepared_designs.append(revision)
                if new_design_id not in imported_design_ids:
                    imported_design_ids.append(new_design_id)
            except (ValueError, ValidationError, KeyError) as exc:
                raise problem(422, "invalid_design", str(exc)) from None
        source_bundles = {Path(name).parts[1] for name in entries if Path(name).parts[0] == "workloads" and len(Path(name).parts) > 1}
        expanded_workload_bytes = 0
        for source_id in sorted(source_bundles):
            try:
                valid_id(source_id)
            except ValueError:
                raise problem(422, "invalid_zip", "Invalid workload bundle ID") from None
            prefix = f"workloads/{source_id}/"
            names = [name for name in entries if name.startswith(prefix)]
            if prefix + "manifest.json" not in names or any(not name.endswith((".json", ".jsonl.gz")) or len(Path(name).parts) != 3 for name in names):
                raise problem(422, "invalid_zip", "Incomplete workload bundle")
            raw_manifest = read_json_entry(prefix + "manifest.json")
            if not isinstance(raw_manifest.get("case_hashes"), dict) or not raw_manifest["case_hashes"]:
                raise problem(422, "invalid_zip", "Workload case manifest is missing")
            expected_names = {prefix + "manifest.json", *(prefix + str(case_id) + ".jsonl.gz" for case_id in raw_manifest["case_hashes"])}
            if set(names) != expected_names:
                raise problem(422, "invalid_zip", "Unexpected workload entries")
            try:
                challenge = _challenge(raw_manifest.get("challenge_id", ""), raw_manifest.get("challenge_version"))
            except HTTPException:
                raise problem(422, "invalid_zip", "Unknown workload challenge") from None
            cases = []
            for case_id in raw_manifest["case_hashes"]:
                try:
                    valid_id(case_id)
                except ValueError:
                    raise problem(422, "invalid_zip", "Invalid workload case ID") from None
                name = prefix + case_id + ".jsonl.gz"
                if name not in names:
                    raise problem(422, "invalid_zip", "Workload case missing")
                remaining = MAX_EXPANDED_WORKLOAD_BYTES - expanded_workload_bytes
                if remaining <= 0:
                    raise problem(422, "import_too_large", "Expanded workload contents exceed limit")
                try:
                    with gzip.GzipFile(fileobj=io.BytesIO(entries[name])) as expanded:
                        content = expanded.read(min(MAX_IMPORT_BYTES, remaining) + 1)
                    if len(content) > remaining:
                        raise problem(422, "import_too_large", "Expanded workload contents exceed limit")
                    if len(content) > MAX_IMPORT_BYTES:
                        raise ValueError("expanded workload case exceeds limit")
                    expanded_workload_bytes += len(content)
                    case = WorkloadCase.model_validate(json.loads(content.splitlines()[0]))
                except (ValueError, ValidationError, IndexError, OSError):
                    raise problem(422, "invalid_zip", "Invalid workload case") from None
                if case.challenge_id != challenge.challenge_id or case.challenge_version != challenge.version or case.scenario_id not in {s.id for s in challenge.scenarios} or any(arrival.operation_id not in {op.id for op in challenge.operations} for arrival in case.arrivals):
                    raise problem(422, "invalid_zip", "Workload case is incompatible with challenge")
                if len(case.arrivals) > 100_000:
                    raise problem(422, "invalid_zip", "Workload arrival cap exceeded")
                cases.append(case)
            if bundle_hash(cases) != raw_manifest.get("workload_hash"):
                raise problem(422, "invalid_zip", "Workload content hash differs")
            canonical_cases = [generate_case(challenge, scenario.id, seed) for scenario in challenge.scenarios if scenario.required for seed in challenge.workload.assessment_seeds] if raw_manifest.get("generator_version") == GENERATOR_VERSION else []
            canonical_verified = len(cases) == len(canonical_cases) and bundle_hash(cases) == bundle_hash(canonical_cases)
            bundle_id = new_id("bundle")
            imported_bundle_ids.append(bundle_id)
            prepared_bundles.append((bundle_id, challenge, cases, raw_manifest, canonical_verified))
        for info in infos:
            path = Path(info.filename)
            if not info.is_dir() and path.parts[0] == "runs" and len(path.parts) > 1:
                if len(path.parts) < 3:
                    raise problem(422, "invalid_zip", "Invalid run evidence entry")
                try:
                    run_id = valid_id(path.parts[1])
                except ValueError:
                    raise problem(422, "invalid_zip", "Invalid run ID") from None
                if run_id not in imported_run_ids:
                    imported_run_ids.append(run_id)
                destination = store().path("imports", import_id, "runs", run_id).joinpath(*path.parts[2:])
                prepared_runs.append((destination, entries[info.filename]))
        try:
            for revision in prepared_designs:
                store().save_design(revision)
            for bundle_id, challenge, cases, raw_manifest, canonical_verified in prepared_bundles:
                for case in cases:
                    store().write_gzip_jsonl(store().path("workloads", bundle_id, f"{case.scenario_id}-{case.seed}").with_suffix(".jsonl.gz"), [case.model_dump(mode="json")])
                store().write_json(store().path("workloads", bundle_id, "manifest").with_suffix(".json"), {"bundle_id": bundle_id, "challenge_id": challenge.challenge_id, "challenge_version": challenge.version, "challenge_hash": digest(challenge.model_dump(mode="json")), "generator_version": raw_manifest.get("generator_version"), "workload_hash": bundle_hash(cases), "case_hashes": {f"{case.scenario_id}-{case.seed}": digest(case.model_dump(mode="json")) for case in cases}, "trusted": False, "canonical_verified": canonical_verified, "import_id": import_id}, immutable=True)
            for destination, content in prepared_runs:
                store().write_bytes(destination, content, immutable=True)
        except Exception:
            for design_id in imported_design_ids:
                shutil.rmtree(store().path("designs", design_id), ignore_errors=True)
            for bundle_id in imported_bundle_ids:
                shutil.rmtree(store().path("workloads", bundle_id), ignore_errors=True)
            shutil.rmtree(store().path("imports", import_id), ignore_errors=True)
            raise
        return ImportResult(imported_design_ids=imported_design_ids, imported_workload_bundle_ids=imported_bundle_ids, imported_run_ids=imported_run_ids)

    site = Path(frontend_dir) if frontend_dir is not None else Path(__file__).resolve().parents[2] / "frontend" / "dist"

    @app.get("/{full_path:path}", include_in_schema=False)
    def frontend(full_path: str):
        if full_path.startswith("api/") or full_path in {"api", "openapi.json", "docs", "redoc"}:
            raise problem(404, "not_found", "Route not found")
        if not (site / "index.html").is_file():
            raise problem(404, "frontend_unavailable", "Build frontend/dist and restart the backend")
        target = (site / full_path).resolve()
        if not target.is_relative_to(site.resolve()):
            raise problem(404, "not_found", "Asset not found")
        if target.is_file():
            return FileResponse(target)
        if full_path.startswith("assets/") or Path(full_path).suffix:
            raise problem(404, "not_found", "Asset not found")
        return FileResponse(site / "index.html")

    return app
