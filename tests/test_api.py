import gzip
import io
import json
import time
import zipfile

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.content import load_fixture


def client(tmp_path):
    return TestClient(create_app(tmp_path))


def test_cost_objective_keeps_ties_visible():
    from backend.api import rank_alternatives
    assert rank_alternatives({"baseline": 50, "candidate": 50}, {"baseline": "pass", "candidate": "pass"}) == (None, ["baseline", "candidate"])
    assert rank_alternatives({"baseline": 50, "candidate": 60}, {"baseline": "pass", "candidate": "pass"}) == ("baseline", [])


def test_built_frontend_serves_navigation_without_masking_api(tmp_path):
    site = tmp_path / "dist"
    (site / "assets").mkdir(parents=True)
    (site / "index.html").write_text("<h1>simulator</h1>")
    (site / "assets" / "app.js").write_text("window.ready=true")
    http = TestClient(create_app(tmp_path / "data", frontend_dir=site))
    assert "simulator" in http.get("/challenges/product-catalogue").text
    assert http.get("/assets/app.js").text == "window.ready=true"
    assert http.get("/assets/missing.js").status_code == 404
    assert http.get("/api/v1/not-a-route").status_code == 404


def test_passing_comparison_candidate_does_not_award_completion(tmp_path):
    from collections import defaultdict, deque
    from datetime import datetime, timezone
    from threading import RLock
    from backend.api.jobs import Jobs
    from backend.api.models import RunManifest
    from backend.storage import Store

    store = Store(tmp_path)
    manifest = RunManifest(run_id="run-candidate", mode="assessment", execution_status="running", assessment_status="not_evaluated", design_id="design-test", revision_id="revision-test", challenge_id="product-catalogue", challenge_version="0.1.0", challenge_hash="hash", engine_version="0.1.0", assessment_version="0.1.0", profile_version="0.1.0", profile_hash="hash", workload_generator_version="1", design_hash="hash", workload_hash="hash", run_config_hash="hash", workload_bundle_id="bundle-test", case_ids=["case-test"], created_at=datetime.now(timezone.utc), comparison_id="comparison-test")
    store.save_run_manifest(manifest.model_dump(mode="json"))
    jobs = object.__new__(Jobs)
    jobs.store, jobs.events, jobs.lock = store, defaultdict(lambda: deque(maxlen=256)), RLock()
    jobs._finish("run-candidate", "completed", "pass")
    assert not store.path("progress").with_suffix(".json").exists()


def test_deleting_credited_run_ignores_passing_comparison_candidate(tmp_path):
    from datetime import datetime, timezone
    from backend.api.models import RunManifest
    from backend.storage import Store

    store = Store(tmp_path)
    common = dict(mode="assessment", execution_status="completed", assessment_status="pass", design_id="design-test", revision_id="revision-test", challenge_id="product-catalogue", challenge_version="0.1.0", challenge_hash="hash", engine_version="0.1.0", assessment_version="0.1.0", profile_version="0.1.0", profile_hash="hash", workload_generator_version="1", design_hash="hash", workload_hash="hash", run_config_hash="hash", workload_bundle_id="bundle-test", case_ids=["case-test"], created_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc))
    store.save_run_manifest(RunManifest(run_id="run-credited", **common).model_dump(mode="json"))
    store.save_run_manifest(RunManifest(run_id="run-candidate", comparison_id="comparison-deleted", **common).model_dump(mode="json"))
    store.write_json(store.path("progress").with_suffix(".json"), {"product-catalogue": {"run_id": "run-credited"}})
    http = client(tmp_path)
    assert http.delete("/api/v1/runs/run-credited").status_code == 200
    assert "product-catalogue" not in store.read_json(store.path("progress").with_suffix(".json"))


def test_restart_terminalizes_abandoned_review_and_completed_candidate_comparison(tmp_path):
    from datetime import datetime, timezone
    from backend.api.models import ComparisonRecord, ReviewRecord, RunManifest
    from backend.storage import Store

    store = Store(tmp_path)
    common = dict(mode="assessment", execution_status="completed", assessment_status="pass", design_id="design-test", revision_id="revision-test", challenge_id="product-catalogue", challenge_version="0.1.0", challenge_hash="hash", engine_version="0.1.0", assessment_version="0.1.0", profile_version="0.1.0", profile_hash="hash", workload_generator_version="1", design_hash="hash", workload_hash="hash", run_config_hash="hash", workload_bundle_id="bundle-test", case_ids=["case-test"], created_at=datetime.now(timezone.utc), finished_at=datetime.now(timezone.utc))
    store.save_run_manifest(RunManifest(run_id="run-baseline", **common).model_dump(mode="json"))
    store.save_run_manifest(RunManifest(run_id="run-candidate", comparison_id="comparison-abandoned", **common).model_dump(mode="json"))
    review_path = store.path("runs", "run-baseline", "reviews", "review-abandoned").with_suffix(".json")
    review = ReviewRecord(review_id="review-abandoned", run_id="run-baseline", status="queued", assessment_status="pass", summary="Assessment passed.", raw_response="partial provider evidence", created_at=datetime.now(timezone.utc))
    store.write_json(review_path, review.model_dump(mode="json"))
    running_review_path = store.path("runs", "run-baseline", "reviews", "review-running").with_suffix(".json")
    store.write_json(running_review_path, review.model_copy(update={"review_id": "review-running", "status": "running"}).model_dump(mode="json"))
    comparison_path = store.path("comparisons", "comparison-abandoned").with_suffix(".json")
    comparison = ComparisonRecord(comparison_id="comparison-abandoned", baseline_run_id="run-baseline", workload_bundle_id="bundle-test", status="running", candidate_revision_ids=["revision-test"], candidate_run_ids=["run-candidate"], rejected_candidates=[{"index": 1, "status": "rejected", "validation_error": "invalid patch"}])
    store.write_json(comparison_path, comparison.model_dump(mode="json"))

    restarted = client(tmp_path)
    recovered_review = restarted.get("/api/v1/runs/run-baseline/reviews/review-abandoned").json()
    recovered_running_review = restarted.get("/api/v1/runs/run-baseline/reviews/review-running").json()
    recovered_comparison = restarted.get("/api/v1/comparisons/comparison-abandoned").json()
    assert recovered_review["status"] == "failed"
    assert "restart" in recovered_review["error"].lower()
    assert recovered_review["finished_at"]
    assert recovered_review["raw_response"] == "partial provider evidence"
    assert recovered_running_review["status"] == "failed"
    assert "restart" in recovered_running_review["error"].lower()
    assert recovered_comparison["status"] == "failed"
    assert "restart" in recovered_comparison["error"].lower()
    assert recovered_comparison["candidate_run_ids"] == ["run-candidate"]
    assert recovered_comparison["rejected_candidates"] == comparison.rejected_candidates
    assert restarted.get("/api/v1/runs/run-candidate").json()["execution_status"] == "completed"


def test_comparison_rejects_changed_required_fault_binding(tmp_path, monkeypatch):
    import backend.api as api
    from datetime import datetime, timezone
    from backend.api.models import RunManifest
    from backend.content import load_challenge
    from backend.contracts import AssessmentResult, Fault, design_hash
    from backend.simulation import fault_bindings
    from backend.storage import Store, digest
    from backend.workloads import GENERATOR_VERSION, bundle_hash, generate_case

    challenge = load_challenge("product-catalogue")
    scenario = challenge.scenarios[0].model_copy(update={"faults": [Fault(type="app_instance_unavailable", at_s=30, target_component_type="app_service", target_instance_id="app-1")]})
    challenge = challenge.model_copy(update={"scenarios": [scenario, *challenge.scenarios[1:]]})
    monkeypatch.setattr(api, "load_challenge", lambda challenge_id: challenge)
    fixture = load_fixture("product-catalogue", "reference")
    baseline = fixture.model_copy(update={"nodes": [node.model_copy(update={"instance_count": 2}) if node.id == "app" else node for node in fixture.nodes]})
    candidate = baseline.model_copy(update={"design_id": "design-renamed", "revision_id": "revision-renamed", "nodes": [node.model_copy(update={"id": "app-renamed"}) if node.id == "app" else node for node in baseline.nodes], "edges": [edge.model_copy(update={"source": "app-renamed" if edge.source == "app" else edge.source, "target": "app-renamed" if edge.target == "app" else edge.target}) for edge in baseline.edges]})
    missing_instance = baseline.model_copy(update={"design_id": "design-missing-instance", "revision_id": "revision-missing-instance", "nodes": [node.model_copy(update={"instance_count": 1}) if node.id == "app" else node for node in baseline.nodes]})
    case = generate_case(challenge, scenario.id, challenge.workload.assessment_seeds[0])
    assert fault_bindings(challenge, baseline, case) != fault_bindings(challenge, candidate, case)
    with pytest.raises(ValueError, match="fault instance missing"):
        fault_bindings(challenge, missing_instance, case)
    installed = load_challenge("product-catalogue")
    clear_scenario = next(s for s in installed.scenarios if any(f.type == "clear_cache" for f in s.faults))
    clear_case = generate_case(installed, clear_scenario.id, installed.workload.assessment_seeds[0])
    assert fault_bindings(installed, baseline, clear_case) == fault_bindings(installed, candidate, clear_case) == []
    store = Store(tmp_path)
    store.save_design(baseline)
    store.save_design(candidate)
    store.save_design(missing_instance)
    bundle_id, run_id, case_id = "bundle-test", "run-baseline", f"{case.scenario_id}-{case.seed}"
    workload_digest = bundle_hash([case])
    challenge_digest = digest(challenge.model_dump(mode="json"))
    store.write_gzip_jsonl(store.path("workloads", bundle_id, case_id).with_suffix(".jsonl.gz"), [case.model_dump(mode="json")])
    store.write_json(store.path("workloads", bundle_id, "manifest").with_suffix(".json"), {"trusted": True, "challenge_id": challenge.challenge_id, "challenge_version": challenge.version, "challenge_hash": challenge_digest, "generator_version": GENERATOR_VERSION, "workload_hash": workload_digest})
    manifest = RunManifest(run_id=run_id, mode="assessment", execution_status="completed", assessment_status="pass", design_id=baseline.design_id, revision_id=baseline.revision_id, challenge_id=challenge.challenge_id, challenge_version=challenge.version, challenge_hash=challenge_digest, engine_version=api.ENGINE_VERSION, assessment_version="0.1.0", profile_version="0.1.0", profile_hash=api.profile_hash(), workload_generator_version=GENERATOR_VERSION, design_hash=design_hash(baseline), workload_hash=workload_digest, run_config_hash="config", workload_bundle_id=bundle_id, case_ids=[case_id], created_at=datetime.now(timezone.utc))
    store.save_run_manifest(manifest.model_dump(mode="json"))
    store.write_json(store.path("runs", run_id, "assessment").with_suffix(".json"), AssessmentResult(status="pass", case_results=[], requirement_outcomes=[]).model_dump(mode="json"))
    http = client(tmp_path)
    response = http.post("/api/v1/comparisons", json={"baseline_run_id": run_id, "candidates": [{"design_id": candidate.design_id, "revision_id": candidate.revision_id}, {"design_id": missing_instance.design_id, "revision_id": missing_instance.revision_id}]})
    assert response.status_code == 202, response.text
    record = http.get(f"/api/v1/comparisons/{response.json()['comparison_id']}").json()
    assert record["status"] == "completed"
    assert not record["candidate_run_ids"]
    assert len(record["rejected_candidates"]) == 2
    assert "fault" in record["rejected_candidates"][0]["validation_error"]
    assert "fault instance missing" in record["rejected_candidates"][1]["validation_error"]
    store.save_run_manifest(manifest.model_copy(update={"engine_version": "0.1.0"}).model_dump(mode="json"))
    incompatible = http.post("/api/v1/comparisons", json={"baseline_run_id": run_id, "candidates": [{"design_id": candidate.design_id, "revision_id": candidate.revision_id}]})
    assert incompatible.status_code == 409 and "versions" in incompatible.json()["message"]


def create_design(http, fixture="reference"):
    design = load_fixture("product-catalogue", fixture)
    response = http.post("/api/v1/designs", json={"challenge_id": design.challenge_id, "challenge_version": design.challenge_version, "nodes": [n.model_dump(mode="json") for n in design.nodes], "edges": [e.model_dump(mode="json") for e in design.edges]})
    assert response.status_code == 201, response.text
    return response.json()


def test_catalogue_design_history_and_security(tmp_path):
    http = client(tmp_path)
    assert http.get("/api/v1/challenges").json()["items"][0]["concepts"]
    assert http.get("/api/v1/catalogue").json()["component_types"]
    created = create_design(http)
    design_id, revision_id = created["design_id"], created["revision_id"]
    revision = http.get(f"/api/v1/designs/{design_id}/revisions/{revision_id}").json()
    assert revision == created["revision"]
    revised = http.post(f"/api/v1/designs/{design_id}/revisions", json={"parent_revision_id": revision_id, "nodes": revision["nodes"], "edges": revision["edges"]})
    assert revised.status_code == 201, revised.text
    assert revised.json()["revision_id"] != revision_id
    assert http.post(f"/api/v1/designs/{design_id}/revisions", json={"parent_revision_id": revision_id, "nodes": revision["nodes"], "edges": revision["edges"]}).status_code == 409
    assert http.get("/api/v1/collection").json()["items"]
    assert http.get("/api/v1/health", headers={"Host": "evil.example"}).status_code == 403
    assert http.post("/api/v1/designs", headers={"Origin": "https://evil.example"}, json={"challenge_id": "product-catalogue"}).status_code == 403
    assert http.get("/api/v1/designs/../secret").status_code in {404, 422}


def test_preview_run_and_idempotency(tmp_path):
    http = client(tmp_path)
    created = create_design(http)
    body = {"design_id": created["design_id"], "revision_id": created["revision_id"], "challenge_id": "product-catalogue", "challenge_version": "0.1.0", "mode": "preview"}
    first = http.post("/api/v1/runs", json=body, headers={"Idempotency-Key": "preview-one"})
    assert first.status_code == 202, first.text
    run_id = first.json()["run_id"]
    assert http.post("/api/v1/runs", json=body, headers={"Idempotency-Key": "preview-one"}).json()["run_id"] == run_id
    assert http.post("/api/v1/runs", json={**body, "mode": "assessment"}, headers={"Idempotency-Key": "preview-one"}).status_code == 409
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        manifest = http.get(f"/api/v1/runs/{run_id}").json()
        if manifest["execution_status"] in {"completed", "failed", "canceled"}:
            break
        time.sleep(.1)
    assert manifest["execution_status"] == "completed", manifest
    assert manifest["assessment_status"] != "pass"
    results = http.get(f"/api/v1/runs/{run_id}/results").json()
    assert results["cases"]
    case_id = manifest["case_ids"][0]
    outcomes = http.get(f"/api/v1/runs/{run_id}/cases/{case_id}/outcomes").json()
    assert outcomes["requests"]
    snapshots = http.get(f"/api/v1/runs/{run_id}/cases/{case_id}/snapshots").json()["items"]
    assert snapshots
    saved = http.post(f"/api/v1/runs/{run_id}/snapshots", json={"title": "saved", "case_id": case_id, "time_us": snapshots[0]["time_us"]})
    assert saved.status_code == 201, saved.text
    assert http.get("/api/v1/snapshots").json()["items"][0]["snapshot_id"] == saved.json()["snapshot_id"]
    exported = http.post("/api/v1/exports", json={"run_ids": [run_id]})
    assert exported.status_code == 201, exported.text
    archive = http.get(exported.json()["download_url"]).content
    imported = http.post("/api/v1/imports", files={"file": ("evidence.zip", archive, "application/zip")})
    assert imported.status_code == 201, imported.text
    bundle_id = imported.json()["imported_workload_bundle_ids"][0]
    assert http.post("/api/v1/runs", json={**body, "mode": "assessment", "workload_bundle_id": bundle_id}).status_code == 409
    experiment = http.post("/api/v1/runs", json={**body, "mode": "experiment", "workload_bundle_id": bundle_id})
    assert experiment.status_code == 202, experiment.text
    experiment_id = experiment.json()["run_id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        experiment_run = http.get(f"/api/v1/runs/{experiment_id}").json()
        if experiment_run["execution_status"] in {"completed", "failed", "canceled"}:
            break
        time.sleep(.1)
    assert experiment_run["execution_status"] == "completed", experiment_run
    assert experiment_run["assessment_status"] != "pass" and experiment_run["trusted_workload"] is False


def test_export_import_rejects_unsafe_zip(tmp_path):
    http = client(tmp_path)
    created = create_design(http)
    exported = http.post("/api/v1/exports", json={"design_ids": [created["design_id"]]})
    assert exported.status_code == 201, exported.text
    archive = http.get(exported.json()["download_url"])
    assert archive.status_code == 200
    imported = http.post("/api/v1/imports", files={"file": ("evidence.zip", archive.content, "application/zip")})
    assert imported.status_code == 201, imported.text
    assert imported.json()["trusted"] is False
    assert imported.json()["imported_design_ids"]
    raw = io.BytesIO()
    with zipfile.ZipFile(raw, "w") as bad:
        bad.writestr("manifest.json", json.dumps({"schema_version": 1, "platform": "ai-system-design-simulator"}))
        bad.writestr("../.env", "AISD_AI_API_KEY=secret")
    assert http.post("/api/v1/imports", files={"file": ("bad.zip", raw.getvalue(), "application/zip")}).status_code == 422


def test_import_validates_all_entries_before_saving_design(tmp_path):
    from backend.storage import Store

    http = client(tmp_path)
    created = create_design(http)
    exported = http.post("/api/v1/exports", json={"design_ids": [created["design_id"]]})
    source = http.get(exported.json()["download_url"]).content
    raw = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(raw, "w") as bad:
        for name in original.namelist():
            bad.writestr(name, original.read(name))
        bad.writestr("workloads/bad-bundle/manifest.json", "{malformed")
    before = Store(tmp_path).ids("designs")
    response = http.post("/api/v1/imports", files={"file": ("bad.zip", raw.getvalue(), "application/zip")})
    assert response.status_code == 422, response.text
    assert Store(tmp_path).ids("designs") == before
    assert Store(tmp_path).ids("workloads") == []


def test_import_bounds_aggregate_expanded_workloads_before_committing(tmp_path, monkeypatch):
    import backend.api as api
    from backend.content import load_challenge
    from backend.storage import Store
    from backend.workloads import generate_case

    http = client(tmp_path)
    created = create_design(http)
    exported = http.post("/api/v1/exports", json={"design_ids": [created["design_id"]]})
    source = http.get(exported.json()["download_url"]).content
    challenge = load_challenge("product-catalogue")
    case = generate_case(challenge, challenge.scenarios[0].id, challenge.workload.assessment_seeds[0])
    content = json.dumps(case.model_dump(mode="json"), sort_keys=True, separators=(",", ":")).encode() + b"\n"
    monkeypatch.setattr(api, "MAX_EXPANDED_WORKLOAD_BYTES", len(content) + 16)
    raw = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source)) as original, zipfile.ZipFile(raw, "w") as archive:
        for name in original.namelist():
            archive.writestr(name, original.read(name))
        archive.writestr("workloads/bundle-test/manifest.json", json.dumps({"challenge_id": challenge.challenge_id, "challenge_version": challenge.version, "case_hashes": {"case-one": "a", "case-two": "b"}, "workload_hash": "irrelevant"}))
        compressed = gzip.compress(content)
        archive.writestr("workloads/bundle-test/case-one.jsonl.gz", compressed)
        archive.writestr("workloads/bundle-test/case-two.jsonl.gz", compressed)
    before = Store(tmp_path).ids("designs")
    response = http.post("/api/v1/imports", files={"file": ("too-large.zip", raw.getvalue(), "application/zip")})
    assert response.status_code == 422, response.text
    assert "expanded workload" in response.json()["message"].lower()
    assert Store(tmp_path).ids("designs") == before
    assert Store(tmp_path).ids("workloads") == []


def test_assessment_comparison_preserves_loser_and_progress(tmp_path, monkeypatch):
    # This verifies persisted API behavior; the separate benchmark owns the
    # simulation speed target. Allow for worker contention in the full suite.
    integration_timeout_s = 120
    http = client(tmp_path)
    baseline = create_design(http, "reference")
    body = {"design_id": baseline["design_id"], "revision_id": baseline["revision_id"], "challenge_id": "product-catalogue", "challenge_version": "0.1.0", "mode": "assessment"}
    response = http.post("/api/v1/runs", json=body)
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + integration_timeout_s
    while time.monotonic() < deadline:
        run = http.get(f"/api/v1/runs/{run_id}").json()
        if run["execution_status"] in {"completed", "failed", "canceled"}:
            break
        time.sleep(.1)
    assert run["execution_status"] == "completed", {"run": run, "timeout_s": integration_timeout_s}
    assert run["assessment_status"] == "pass", run
    assert next(item for item in http.get("/api/v1/challenges").json()["items"] if item["challenge_id"] == "product-catalogue")["progress"] == "passed"
    exported = http.post("/api/v1/exports", json={"run_ids": [run_id]})
    assert exported.status_code == 201, exported.text
    imported = http.post("/api/v1/imports", files={"file": ("assessment.zip", http.get(exported.json()["download_url"]).content, "application/zip")})
    assert imported.status_code == 201, imported.text
    imported_bundle_id = imported.json()["imported_workload_bundle_ids"][0]
    canonical_run = http.post("/api/v1/runs", json={**body, "workload_bundle_id": imported_bundle_id})
    assert canonical_run.status_code == 202, canonical_run.text
    assert http.get(f"/api/v1/runs/{canonical_run.json()['run_id']}").json()["trusted_workload"] is True
    http.post(f"/api/v1/runs/{canonical_run.json()['run_id']}/cancel")
    # Propose a supported experiment using ONLY the real outbound provider context.
    import httpx
    import backend.coach as coach
    from backend.content import load_challenge
    from backend.contracts import DesignRevision
    actual_client = httpx.AsyncClient
    captured = []
    def provider(request):
        body = json.loads(request.content)
        schema = body["response_format"]["json_schema"]
        assert schema["strict"] is True
        def check_objects(value):
            if isinstance(value, dict):
                if value.get("type") == "object":
                    assert value.get("additionalProperties") is False
                    assert set(value.get("required", [])) == set(value["properties"])
                assert "oneOf" not in value and "default" not in value
                for child in value.values(): check_objects(child)
            elif isinstance(value, list):
                for child in value: check_objects(child)
        check_objects(schema["schema"])
        context = json.loads(body["messages"][1]["content"])
        captured.append(context)
        node = next(node for node in context["design"]["nodes"] if node["settings"].get("invalidation") == "synchronous")
        choice = next(choice for choice in context["support_limits"]["component_settings"][node["type"]]["invalidation"]["choices"] if choice != "synchronous")
        assert "remove_edge" in context["patch_grammar"]["operations"]
        patch = {"base_revision_id": context["design"]["revision_id"], "operations": [
            *[{"op": "remove_edge", "edge_id": edge["id"]} for edge in context["design"]["edges"] if edge["source"] == node["id"] and edge["kind"] == "invalidate"],
            {"op": "set_node_setting", "node_id": node["id"], "key": "invalidation", "value": choice}]}
        payload = {"strengths": [], "findings": [], "limitations": [], "suggested_experiments": [{"purpose": "Test invalidation tradeoffs", "patch": patch, "expected_tradeoffs": "Less synchronous work may allow stale reads.", "evidence_refs": []}]}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(payload)}}]})
    monkeypatch.setattr(coach.httpx, "AsyncClient", lambda: actual_client(transport=httpx.MockTransport(provider)))
    monkeypatch.setenv("AISD_AI_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("AISD_AI_MODEL", "test")
    monkeypatch.setenv("AISD_AI_API_KEY", "secret")
    challenge, design = load_challenge("product-catalogue"), DesignRevision.model_validate(baseline["revision"])
    payload, raw, usage, latency = coach.request_review(challenge, design, [], {})
    validated = coach.validate_review(payload, [], design, challenge)
    assert captured[0]["design"]["revision_id"] == baseline["revision_id"]
    patch = validated.suggested_experiments[0].patch
    comparison = http.post("/api/v1/comparisons", json={"baseline_run_id": run_id, "candidates": [{"patch": patch}]})
    assert comparison.status_code == 202, comparison.text
    comparison_id = comparison.json()["comparison_id"]
    deadline = time.monotonic() + integration_timeout_s
    while time.monotonic() < deadline:
        record = http.get(f"/api/v1/comparisons/{comparison_id}").json()
        if record["status"] in {"completed", "failed"}:
            break
        time.sleep(.1)
    assert record["status"] == "completed", {"comparison": record, "timeout_s": integration_timeout_s}
    assert record["candidate_run_ids"] and record["differences"]
    assert record["winner_run_id"] == run_id
    rejected = http.post("/api/v1/comparisons", json={"baseline_run_id": run_id, "candidates": [{"patch": {"base_revision_id": baseline["revision_id"], "operations": [{"op": "set_node_setting", "node_id": "missing", "key": "ttl_seconds", "value": 10}]}}]})
    assert rejected.status_code == 202, rejected.text
    rejected_id = rejected.json()["comparison_id"]
    rejected_record = http.get(f"/api/v1/comparisons/{rejected_id}").json()
    assert rejected_record["status"] == "completed"
    assert rejected_record["rejected_candidates"][0]["status"] == "rejected"
    assert "missing node" in rejected_record["rejected_candidates"][0]["validation_error"]
    assert not rejected_record["candidate_run_ids"]
    assert http.delete(f"/api/v1/runs/{run_id}").status_code == 409
    assert http.delete(f"/api/v1/comparisons/{comparison_id}").status_code == 200
    assert http.delete(f"/api/v1/comparisons/{rejected_id}").status_code == 200
    assert http.delete(f"/api/v1/runs/{run_id}").status_code == 200
    assert next(item for item in http.get("/api/v1/challenges").json()["items"] if item["challenge_id"] == "product-catalogue")["progress"] != "passed"


def test_review_opt_in_and_rejected_model_output_is_saved(tmp_path, monkeypatch):
    import backend.api as api

    http = client(tmp_path)
    created = create_design(http)
    response = http.post("/api/v1/runs", json={"design_id": created["design_id"], "revision_id": created["revision_id"], "challenge_id": "product-catalogue", "challenge_version": "0.1.0", "mode": "preview"})
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        run = http.get(f"/api/v1/runs/{run_id}").json()
        if run["execution_status"] in {"completed", "failed"}:
            break
        time.sleep(.1)
    assert run["execution_status"] == "completed"
    calls = []
    def provider(*args):
        calls.append(1)
        payload = {"summary": "This was 50% faster.", "strengths": [], "findings": [], "suggested_experiments": [], "limitations": []}
        return payload, json.dumps(payload), None, 1
    monkeypatch.setattr(api, "request_review", provider)
    monkeypatch.setenv("AISD_AI_BASE_URL", "http://127.0.0.1:9999/v1")
    monkeypatch.setenv("AISD_AI_MODEL", "test")
    monkeypatch.setenv("AISD_AI_API_KEY", "test-secret")
    assert not calls
    accepted = http.post(f"/api/v1/runs/{run_id}/reviews", json={"consent": True})
    assert accepted.status_code == 202, accepted.text
    review_id = accepted.json()["review_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        review = http.get(f"/api/v1/runs/{run_id}/reviews/{review_id}").json()
        if review["status"] != "queued":
            break
        time.sleep(.05)
    assert calls == [1]
    assert review["status"] == "failed" and review["raw_response"]
    assert review["validation_errors"] and "test-secret" not in json.dumps(review)
    from backend.coach import ProviderOutputError
    def malformed(*args):
        raise ProviderOutputError("provider returned malformed JSON", "{bad-json", None, 2)
    monkeypatch.setattr(api, "request_review", malformed)
    accepted = http.post(f"/api/v1/runs/{run_id}/reviews", json={"consent": True})
    assert accepted.status_code == 202
    review_id = accepted.json()["review_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        review = http.get(f"/api/v1/runs/{run_id}/reviews/{review_id}").json()
        if review["status"] != "queued":
            break
        time.sleep(.05)
    assert review["status"] == "failed"
    assert review["raw_response"] == "{bad-json"
    assert review["validation_errors"]
    def malformed_with_bad_usage(*args):
        raise ProviderOutputError("provider returned malformed JSON", "{bad-json", [], 2)
    monkeypatch.setattr(api, "request_review", malformed_with_bad_usage)
    accepted = http.post(f"/api/v1/runs/{run_id}/reviews", json={"consent": True})
    assert accepted.status_code == 202
    review_id = accepted.json()["review_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        review = http.get(f"/api/v1/runs/{run_id}/reviews/{review_id}").json()
        if review["status"] != "queued":
            break
        time.sleep(.05)
    assert review["status"] == "failed"
    assert review["raw_response"] == "{bad-json"
    assert review["usage"] is None
    def valid(*args):
        payload = {"strengths": [], "findings": [], "suggested_experiments": [], "limitations": ["The cache may help repeated reads."]}
        return payload, json.dumps(payload), None, 2
    monkeypatch.setattr(api, "request_review", valid)
    accepted = http.post(f"/api/v1/runs/{run_id}/reviews", json={"consent": True})
    assert accepted.status_code == 202
    review_id = accepted.json()["review_id"]
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        review = http.get(f"/api/v1/runs/{run_id}/reviews/{review_id}").json()
        if review["status"] != "queued":
            break
        time.sleep(.05)
    assert review["status"] == "completed"
    assert review["assessment_status"] == run["assessment_status"]
    assert review["summary"] == {"pass": "Assessment passed.", "fail": "Assessment failed.", "incomplete": "Assessment evidence is incomplete.", "not_evaluated": "This run was not assessed."}[run["assessment_status"]]
    assert review["limitations"] == ["The cache may help repeated reads."]
