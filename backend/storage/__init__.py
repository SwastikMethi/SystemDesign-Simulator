"""Atomic local evidence storage. All path segments are generated or validated IDs."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import re
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend.contracts import DesignRevision

SAFE_ID = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,119}$")


def valid_id(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError("invalid identifier")
    return value


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex}"


def digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()).hexdigest()


class Store:
    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, *parts: str) -> Path:
        for part in parts:
            valid_id(part)
        path = self.root.joinpath(*parts)
        if not path.resolve().is_relative_to(self.root):
            raise ValueError("path escapes data directory")
        return path

    def write_bytes(self, path: Path, blob: bytes, *, immutable: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if immutable and path.exists():
            raise FileExistsError(path.name)
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            if immutable:
                os.link(name, path)
            else:
                os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def write_json(self, path: Path, data: Any, *, immutable: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if immutable and path.exists():
            raise FileExistsError(path.name)
        blob = json.dumps(data, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(blob)
                handle.flush()
                os.fsync(handle.fileno())
            if immutable:
                os.link(name, path)
                os.unlink(name)
            else:
                os.replace(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def read_json(self, path: Path) -> Any:
        return json.loads(path.read_text())

    def write_gzip_jsonl(self, path: Path, records: list[Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(path.name)
        fd, name = tempfile.mkstemp(dir=path.parent, prefix=".tmp-")
        try:
            with os.fdopen(fd, "wb") as raw:
                with gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as handle:
                    for record in records:
                        handle.write(json.dumps(record, sort_keys=True, separators=(",", ":"), allow_nan=False).encode() + b"\n")
                raw.flush()
                os.fsync(raw.fileno())
            os.link(name, path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def read_gzip_jsonl(self, path: Path) -> list[Any]:
        with gzip.open(path, "rt") as handle:
            return [json.loads(line) for line in handle]

    def save_design(self, revision: DesignRevision) -> None:
        path = self.path("designs", revision.design_id, revision.revision_id) .with_suffix(".json")
        self.write_json(path, revision.model_dump(mode="json"), immutable=True)

    def get_design(self, design_id: str, revision_id: str) -> DesignRevision:
        path = self.path("designs", design_id, revision_id).with_suffix(".json")
        return DesignRevision.model_validate(self.read_json(path))

    def revisions(self, design_id: str) -> list[DesignRevision]:
        folder = self.path("designs", design_id)
        return [DesignRevision.model_validate(self.read_json(path)) for path in sorted(folder.glob("*.json"))] if folder.exists() else []

    def manifest_path(self, run_id: str) -> Path:
        return self.path("runs", run_id, "manifest").with_suffix(".json")

    def run_manifest(self, run_id: str) -> dict[str, Any]:
        return self.read_json(self.manifest_path(run_id))

    def save_run_manifest(self, manifest: dict[str, Any]) -> None:
        self.write_json(self.manifest_path(manifest["run_id"]), manifest)

    def case_path(self, run_id: str, case_id: str, name: str) -> Path:
        if name not in {"outcomes.jsonl.gz", "snapshots.jsonl.gz", "traces.jsonl.gz", "result.json"}:
            raise ValueError("invalid case artifact")
        return self.path("runs", run_id, "cases", case_id) / name

    def ids(self, category: str) -> list[str]:
        if category not in {"runs", "designs", "workloads", "snapshots"}:
            raise ValueError("invalid category")
        base = self.path(category)
        return sorted(p.name for p in base.iterdir() if p.is_dir() and SAFE_ID.fullmatch(p.name)) if base.exists() else []

    def interrupt_unfinished(self) -> None:
        for run_id in self.ids("runs"):
            try:
                manifest = self.run_manifest(run_id)
            except (OSError, ValueError):
                manifest = None
            if isinstance(manifest, dict) and manifest.get("execution_status") in {"queued", "running"}:
                manifest["execution_status"] = "interrupted"
                manifest["assessment_status"] = "incomplete"
                manifest["error"] = "Backend restarted; run again to resume."
                self.save_run_manifest(manifest)
            reviews = self.path("runs", run_id, "reviews")
            if reviews.exists():
                for path in reviews.glob("*.json"):
                    if path.is_symlink() or not SAFE_ID.fullmatch(path.stem):
                        continue
                    try:
                        review = self.read_json(path)
                    except (OSError, ValueError):
                        continue
                    if isinstance(review, dict) and review.get("status") in {"queued", "running"}:
                        review.update(status="failed", error="Backend restarted; review interrupted. Request a new review.", finished_at=datetime.now(timezone.utc).isoformat())
                        self.write_json(path, review)
        for design_id in self.ids("designs"):
            guidance_dir = self.path("designs", design_id, "guidance")
            if not guidance_dir.exists():
                continue
            for path in guidance_dir.glob("*.json"):
                if path.is_symlink() or not SAFE_ID.fullmatch(path.stem):
                    continue
                try:
                    guidance = self.read_json(path)
                except (OSError, ValueError):
                    continue
                if isinstance(guidance, dict) and guidance.get("status") in {"queued", "running"}:
                    guidance.update(status="failed", error="Backend restarted; guidance interrupted. Request new guidance.", finished_at=datetime.now(timezone.utc).isoformat())
                    self.write_json(path, guidance)
        comparisons = self.path("comparisons")
        if comparisons.exists():
            for path in comparisons.glob("*.json"):
                if path.is_symlink() or not SAFE_ID.fullmatch(path.stem):
                    continue
                try:
                    comparison = self.read_json(path)
                except (OSError, ValueError):
                    continue
                if isinstance(comparison, dict) and comparison.get("status") in {"queued", "running"}:
                    comparison.update(status="failed", error="Backend restarted; comparison interrupted. Start a new comparison.")
                    self.write_json(path, comparison)
