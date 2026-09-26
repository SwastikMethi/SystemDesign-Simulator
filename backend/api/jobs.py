"""One simulation child at a time; the API process stays responsive."""

from __future__ import annotations

import multiprocessing as mp
import queue
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.api.models import RunEvent, RunManifest
from backend.contracts import AssessmentResult, CaseResult, Challenge, DesignRevision
from backend.storage import Store
from backend.workloads import WorkloadCase

ENGINE_VERSION = "0.1.0"
ASSESSMENT_VERSION = "0.1.0"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def run_child(root: str, run_id: str, challenge_data: dict, design_data: dict, cases_data: list[dict], messages: Any, cancel: Any) -> None:
    from backend.assessment import assess_suite
    from backend.simulation import run_case

    store = Store(Path(root))
    challenge = Challenge.model_validate(challenge_data)
    design = DesignRevision.model_validate(design_data)
    results: list[CaseResult] = []
    try:
        for raw in cases_data:
            if cancel.is_set():
                messages.put({"kind": "canceled"})
                return
            case = WorkloadCase.model_validate(raw)
            case_id = f"{case.scenario_id}-{case.seed}"
            messages.put({"kind": "case_started", "case_id": case_id})
            def progress(value: dict) -> None:
                messages.put({"kind": "progress", "case_id": case_id, "value": value})
            artifacts = run_case(challenge, design, case, on_progress=progress, should_cancel=cancel.is_set)
            store.write_gzip_jsonl(store.case_path(run_id, case_id, "outcomes.jsonl.gz"), [{"kind": "request", **o.model_dump(mode="json")} for o in artifacts.outcomes] + [{"kind": "job", **o.model_dump(mode="json")} for o in artifacts.jobs])
            store.write_gzip_jsonl(store.case_path(run_id, case_id, "snapshots.jsonl.gz"), [s.model_dump(mode="json") for s in artifacts.snapshots])
            store.write_gzip_jsonl(store.case_path(run_id, case_id, "traces.jsonl.gz"), [t.model_dump(mode="json") for t in artifacts.traces])
            store.write_json(store.case_path(run_id, case_id, "result.json"), artifacts.result.model_dump(mode="json"), immutable=True)
            results.append(artifacts.result)
            messages.put({"kind": "case_completed", "case_id": case_id})
            if cancel.is_set() or artifacts.result.execution_status != "completed":
                messages.put({"kind": "canceled" if cancel.is_set() else "incomplete"})
                return
        assessment = assess_suite(challenge, results, mode=store.run_manifest(run_id)["mode"])
        store.write_json(store.path("runs", run_id, "assessment").with_suffix(".json"), assessment.model_dump(mode="json"), immutable=True)
        messages.put({"kind": "completed", "assessment_status": assessment.status})
    except BaseException as exc:
        messages.put({"kind": "failed", "error": str(exc)[:500]})


class Jobs:
    def __init__(self, store: Store, capacity: int = 8):
        self.store = store
        self.capacity = capacity
        self.pending: queue.Queue[tuple[str, dict, dict, list[dict]]] = queue.Queue(maxsize=capacity)
        self.events: dict[str, deque[dict]] = defaultdict(lambda: deque(maxlen=256))
        self.cancellations: set[str] = set()
        self.lock = threading.RLock()
        self.active_id: str | None = None
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()

    def enqueue(self, run_id: str, challenge: Challenge, design: DesignRevision, cases: list[WorkloadCase]) -> bool:
        try:
            self.pending.put_nowait((run_id, challenge.model_dump(mode="json"), design.model_dump(mode="json"), [case.model_dump(mode="json") for case in cases]))
        except queue.Full:
            return False
        self.emit(run_id, "queued", progress=0)
        return True

    def emit(self, run_id: str, kind: str, **values: Any) -> dict:
        with self.lock:
            events = self.events[run_id]
            event_id = events[-1]["event_id"] + 1 if events else 1
            event = RunEvent(event_id=event_id, run_id=run_id, type=kind, case_id=values.pop("case_id", None), progress=values.pop("progress", 0), snapshot=values.pop("snapshot", None), emitted_at=now()).model_dump(mode="json")
            events.append(event)
            return event

    def cancel(self, run_id: str) -> None:
        with self.lock:
            self.cancellations.add(run_id)

    def _loop(self) -> None:
        while True:
            run_id, challenge, design, cases = self.pending.get()
            with self.lock:
                if run_id in self.cancellations:
                    self._finish(run_id, "canceled", "incomplete")
                    continue
                self.active_id = run_id
            manifest = self.store.run_manifest(run_id)
            manifest["execution_status"] = "running"
            manifest["started_at"] = now()
            self.store.save_run_manifest(manifest)
            self.emit(run_id, "running")
            ctx = mp.get_context("spawn")
            messages, cancel = ctx.Queue(maxsize=100), ctx.Event()
            child = ctx.Process(target=run_child, args=(str(self.store.root), run_id, challenge, design, cases, messages, cancel))
            child.start()
            terminal = None
            last_progress = 0.0
            while child.is_alive() or not messages.empty():
                if run_id in self.cancellations:
                    cancel.set()
                try:
                    item = messages.get(timeout=.1)
                except queue.Empty:
                    continue
                kind = item["kind"]
                if kind == "progress":
                    if time.monotonic() - last_progress >= .1:
                        self.emit(run_id, "progress", case_id=item["case_id"], snapshot=item["value"].get("snapshot"), progress=manifest["progress"])
                        last_progress = time.monotonic()
                elif kind == "case_completed":
                    manifest["completed_case_ids"].append(item["case_id"])
                    manifest["progress"] = len(manifest["completed_case_ids"]) / len(manifest["case_ids"])
                    self.store.save_run_manifest(manifest)
                    self.emit(run_id, "case_completed", case_id=item["case_id"], progress=manifest["progress"])
                elif kind in {"completed", "failed", "canceled", "incomplete"}:
                    terminal = item
            child.join(timeout=1)
            if terminal is None:
                terminal = {"kind": "failed", "error": f"Simulation process exited {child.exitcode}"}
            kind = terminal["kind"]
            status = "completed" if kind == "completed" else "canceled" if kind == "canceled" else "failed"
            assessment_status = terminal.get("assessment_status", "incomplete")
            self._finish(run_id, status, assessment_status, terminal.get("error"))
            with self.lock:
                self.active_id = None

    def _finish(self, run_id: str, status: str, assessment_status: str, error: str | None = None) -> None:
        manifest = self.store.run_manifest(run_id)
        manifest.update(execution_status=status, assessment_status=assessment_status, finished_at=now(), error=error)
        self.store.save_run_manifest(manifest)
        if status == "completed" and assessment_status == "pass" and manifest["mode"] == "assessment" and manifest.get("trusted_workload", False) and not manifest.get("comparison_id"):
            progress_path = self.store.path("progress").with_suffix(".json")
            progress = self.store.read_json(progress_path) if progress_path.exists() else {}
            progress[manifest["challenge_id"]] = {"run_id": run_id, "challenge_version": manifest["challenge_version"], "design_hash": manifest["design_hash"], "completed_at": manifest["finished_at"]}
            self.store.write_json(progress_path, progress)
        self.emit(run_id, status, progress=manifest["progress"])
