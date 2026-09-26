import json
import queue
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.api import create_app
from backend.api.jobs import Jobs
from backend.api.models import RunManifest
from backend.content import load_fixture
from backend.storage import Store


def manifest(run_id: str, status: str = "queued") -> RunManifest:
    return RunManifest(run_id=run_id, mode="preview", execution_status=status, assessment_status="not_evaluated", design_id="design-test", revision_id="revision-test", challenge_id="product-catalogue", challenge_version="0.1.0", challenge_hash="hash", engine_version="0.1.0", assessment_version="0.1.0", profile_version="0.1.0", profile_hash="hash", workload_generator_version="1", design_hash="hash", workload_hash="hash", run_config_hash="hash", workload_bundle_id="bundle-test", case_ids=["case-test"], created_at=datetime.now(timezone.utc))


def idle_jobs(store: Store) -> Jobs:
    jobs = object.__new__(Jobs)
    jobs.store = store
    jobs.capacity = 8
    jobs.pending = queue.Queue(maxsize=8)
    jobs.events = defaultdict(lambda: deque(maxlen=256))
    jobs.cancellations = set()
    jobs.lock = threading.RLock()
    jobs.active_id = None
    return jobs


def test_atomic_replace_failure_preserves_previous_manifest(tmp_path, monkeypatch):
    import backend.storage as storage

    store = Store(tmp_path)
    path = store.manifest_path("run-existing")
    store.write_json(path, {"version": "previous"})
    previous = path.read_bytes()
    replace = storage.os.replace
    def fail_replace(source, target):
        if Path(target) == path:
            raise OSError("injected replacement failure")
        return replace(source, target)
    monkeypatch.setattr(storage.os, "replace", fail_replace)
    with pytest.raises(OSError, match="injected replacement failure"):
        store.write_json(path, {"version": "new"})
    assert path.read_bytes() == previous
    assert not list(path.parent.glob(".tmp-*"))


def test_run_create_write_failure_does_not_enqueue_or_leave_partial_evidence(tmp_path, monkeypatch):
    import backend.storage as storage

    store = Store(tmp_path)
    design = load_fixture("product-catalogue", "reference")
    store.save_design(design)
    design_path = store.path("designs", design.design_id, design.revision_id).with_suffix(".json")
    prior_design = design_path.read_bytes()
    app = create_app(tmp_path)
    http = TestClient(app, raise_server_exceptions=False)
    link = storage.os.link
    def fail_idempotency_link(source, target):
        if Path(target).parent.name == "idempotency":
            raise OSError("injected idempotency write failure")
        return link(source, target)
    monkeypatch.setattr(storage.os, "link", fail_idempotency_link)
    response = http.post("/api/v1/runs", headers={"Idempotency-Key": "failure-check"}, json={"design_id": design.design_id, "revision_id": design.revision_id, "challenge_id": design.challenge_id, "challenge_version": design.challenge_version, "mode": "preview"})
    assert response.status_code == 500
    assert design_path.read_bytes() == prior_design
    assert store.ids("runs") == []
    assert store.ids("workloads") == []
    assert app.state.jobs is None or (app.state.jobs.pending.empty() and not app.state.jobs.events)


def test_queue_full_rolls_back_prepared_run_and_idempotency_key(tmp_path):
    store = Store(tmp_path)
    design = load_fixture("product-catalogue", "reference")
    store.save_design(design)
    app = create_app(tmp_path)
    app.state.store = store
    jobs = idle_jobs(store)
    jobs.capacity = 1
    jobs.pending = queue.Queue(maxsize=1)
    jobs.pending.put(("already-queued", {}, {}, []))
    app.state.jobs = jobs
    http = TestClient(app)
    response = http.post("/api/v1/runs", headers={"Idempotency-Key": "queue-full"}, json={"design_id": design.design_id, "revision_id": design.revision_id, "challenge_id": design.challenge_id, "challenge_version": design.challenge_version, "mode": "preview"})
    assert response.status_code == 503
    assert store.ids("runs") == []
    assert store.ids("workloads") == []
    assert not list(store.path("idempotency").glob("*.json"))


def test_restart_interrupts_queued_and_running_runs_without_erasing_artifacts(tmp_path):
    store = Store(tmp_path)
    store.save_run_manifest(manifest("run-queued").model_dump(mode="json"))
    running = manifest("run-running", "running").model_copy(update={"completed_case_ids": ["case-test"], "progress": 1.0})
    store.save_run_manifest(running.model_dump(mode="json"))
    artifact = store.case_path("run-running", "case-test", "result.json")
    store.write_json(artifact, {"saved": "immutable evidence"}, immutable=True)
    http = TestClient(create_app(tmp_path))
    for run_id in ("run-queued", "run-running"):
        recovered = http.get(f"/api/v1/runs/{run_id}").json()
        assert recovered["execution_status"] == "interrupted"
        assert recovered["assessment_status"] == "incomplete"
        assert "restart" in recovered["error"].lower()
    assert store.read_json(artifact) == {"saved": "immutable evidence"}
    assert http.get("/api/v1/runs/run-running").json()["completed_case_ids"] == ["case-test"]


def test_queued_cancel_reaches_terminal_state_through_api_and_manager(tmp_path):
    store = Store(tmp_path)
    store.save_run_manifest(manifest("run-cancel").model_dump(mode="json"))
    app = create_app(tmp_path)
    app.state.store = store
    jobs = idle_jobs(store)
    app.state.jobs = jobs
    jobs.pending.put(("run-cancel", {}, {}, []))
    jobs.emit("run-cancel", "queued")
    http = TestClient(app)
    assert http.post("/api/v1/runs/run-cancel/cancel").status_code == 200
    threading.Thread(target=jobs._loop, daemon=True).start()
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline and store.run_manifest("run-cancel")["execution_status"] != "canceled":
        time.sleep(.01)
    canceled = http.get("/api/v1/runs/run-cancel").json()
    assert canceled["execution_status"] == "canceled"
    assert canceled["assessment_status"] == "incomplete"
    assert canceled["finished_at"]
    assert jobs.events["run-cancel"][-1]["type"] == "canceled"


def test_sse_replays_cursor_and_resyncs_after_bounded_buffer_loss(tmp_path):
    store = Store(tmp_path)
    store.save_run_manifest(manifest("run-events", "completed").model_dump(mode="json"))
    app = create_app(tmp_path)
    app.state.store = store
    jobs = idle_jobs(store)
    app.state.jobs = jobs
    jobs.emit("run-events", "queued")
    jobs.emit("run-events", "progress", progress=.5)
    jobs.emit("run-events", "completed", progress=1)
    http = TestClient(app)
    def events(response):
        return [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
    replayed = events(http.get("/api/v1/runs/run-events/events", headers={"Last-Event-ID": "1"}))
    assert [(event["event_id"], event["type"]) for event in replayed] == [(2, "progress"), (3, "completed")]
    for _ in range(257):
        jobs.emit("run-events", "progress")
    assert len(jobs.events["run-events"]) == 256
    resynced = events(http.get("/api/v1/runs/run-events/events", headers={"Last-Event-ID": "1"}))
    assert len(resynced) == 1
    assert resynced[0]["type"] == "resync"
    assert resynced[0]["event_id"] > jobs.events["run-events"][0]["event_id"]
