"""Wire contracts for the local application."""

from datetime import datetime
from typing import Any, Literal

from pydantic import Field

from backend.contracts import AssessmentResult, CaseResult, Challenge, DesignNode, DesignRevision, Edge, JobOutcome, Profile, RequestOutcome, Strict, ValidationFinding
from backend.simulation import Snapshot, Trace


class Error(Strict):
    code: str
    message: str
    field_errors: dict[str, str] = {}
    node_ids: list[str] = []
    edge_ids: list[str] = []
    retryable: bool = False


class Health(Strict):
    status: Literal["ok"] = "ok"
    engine_version: str
    ai_configured: bool
    ai_model: str | None


class ComponentInfo(Strict):
    type: str
    label: str
    purpose: str
    profiles: list[str]
    settings: dict[str, Any]
    support_label: Literal["Simulated"] = "Simulated"


class Catalogue(Strict):
    component_types: list[ComponentInfo]
    profiles: list[Profile]


class ChallengeSummary(Strict):
    challenge_id: str
    version: str
    title: str
    level: int
    brief: str
    concepts: list[str]
    support_status: Literal["Simulated"] = "Simulated"
    progress: Literal["unstarted", "in_progress", "passed"]


class ChallengeList(Strict):
    items: list[ChallengeSummary]


class ReferenceAnswer(Strict):
    design: DesignRevision
    explanation: str = Field(min_length=1)


class DesignInput(Strict):
    challenge_id: str
    challenge_version: str = "0.1.0"
    nodes: list[DesignNode] = []
    edges: list[Edge] = []


class RevisionInput(Strict):
    parent_revision_id: str
    nodes: list[DesignNode]
    edges: list[Edge]


class DesignCreated(Strict):
    design_id: str
    revision_id: str
    revision: DesignRevision


class DesignMetadata(Strict):
    design_id: str
    challenge_id: str
    challenge_version: str
    latest_revision_id: str
    revision_ids: list[str]


class ValidationResult(Strict):
    valid_draft: bool
    runnable: bool
    findings: list[ValidationFinding]
    design_hash: str | None = None


class RunInput(Strict):
    design_id: str
    revision_id: str
    challenge_id: str
    challenge_version: str = "0.1.0"
    mode: Literal["preview", "assessment", "experiment"]
    workload_bundle_id: str | None = None
    experiment_scenario_id: str | None = None
    experiment_seed: int | None = None


class RunAccepted(Strict):
    run_id: str
    execution_status: Literal["queued"] = "queued"
    assessment_status: Literal["not_evaluated"] = "not_evaluated"


class RunManifest(Strict):
    run_id: str
    mode: Literal["preview", "assessment", "experiment"]
    execution_status: Literal["queued", "running", "completed", "canceled", "failed", "interrupted"]
    assessment_status: Literal["pass", "fail", "not_evaluated", "incomplete"]
    design_id: str
    revision_id: str
    challenge_id: str
    challenge_version: str
    challenge_hash: str
    engine_version: str
    assessment_version: str
    profile_version: str
    profile_hash: str
    workload_generator_version: str
    design_hash: str
    workload_hash: str
    run_config_hash: str
    workload_bundle_id: str
    case_ids: list[str]
    completed_case_ids: list[str] = []
    progress: float = 0
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    artifact_refs: dict[str, str] = {}
    trusted_workload: bool = True
    comparison_id: str | None = None


class RunResults(Strict):
    run_id: str
    assessment: AssessmentResult | None
    cases: list[CaseResult]


class SnapshotPage(Strict):
    case_id: str
    items: list[Snapshot]


class OutcomePage(Strict):
    case_id: str
    requests: list[RequestOutcome]
    jobs: list[JobOutcome]


class RunEvent(Strict):
    event_id: int
    run_id: str
    type: str
    case_id: str | None
    progress: float
    snapshot: Snapshot | None
    emitted_at: datetime


class ReviewAccepted(Strict):
    review_id: str
    status: Literal["queued"] = "queued"


class ReviewRequest(Strict):
    consent: Literal[True]
    comparison_id: str | None = None


class ReviewRecord(Strict):
    review_id: str
    run_id: str
    status: Literal["queued", "running", "completed", "failed"]
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    latency_ms: int | None = None
    usage: dict[str, Any] | None = None
    cost: float | None = None
    assessment_status: Literal["pass", "fail", "not_evaluated", "incomplete"] | None = None
    summary: str | None = None
    strengths: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    suggested_experiments: list[dict[str, Any]] = []
    limitations: list[str] = []
    validation_errors: list[str] = []
    error: str | None = None
    raw_response: str | None = None


class GuidanceRequest(Strict):
    revision_id: str
    mode: Literal["hint", "explain", "answer"]
    source_guidance_id: str | None = None
    focus: str | None = Field(default=None, max_length=160)
    evidence_step: bool = False
    consent: Literal[True]


class GuidanceAccepted(Strict):
    guidance_id: str
    status: Literal["queued"] = "queued"


class GuidanceRecord(Strict):
    guidance_id: str
    design_id: str
    revision_id: str
    mode: Literal["hint", "explain", "answer"]
    source_guidance_id: str | None = None
    focus: str | None = None
    evidence_step: bool = False
    status: Literal["queued", "completed", "failed"]
    question: str | None = None
    explanation: str | None = None
    authored_refs: list[str] = []
    provider: str | None = None
    model: str | None = None
    prompt_version: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
    latency_ms: int | None = None
    usage: dict[str, Any] | None = None
    cost: float | None = None
    error: str | None = None
    validation_errors: list[str] = []
    raw_response: str | None = None


class CandidateInput(Strict):
    revision_id: str | None = None
    design_id: str | None = None
    patch: dict[str, Any] | None = None


class ComparisonInput(Strict):
    baseline_run_id: str
    candidates: list[CandidateInput] = Field(min_length=1, max_length=2)


class ComparisonAccepted(Strict):
    comparison_id: str
    status: Literal["queued"] = "queued"


class ComparisonRecord(Strict):
    comparison_id: str
    baseline_run_id: str
    workload_bundle_id: str
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    candidate_revision_ids: list[str]
    candidate_run_ids: list[str] = []
    rejected_candidates: list[dict[str, Any]] = []
    objective: str = "minimum credits/hour among passing alternatives, including baseline"
    differences: list[dict[str, Any]] = []
    winner_run_id: str | None = None
    tied_run_ids: list[str] = []
    error: str | None = None


class ExportInput(Strict):
    design_ids: list[str] = []
    run_ids: list[str] = []
    comparison_ids: list[str] = []


class ExportToken(Strict):
    token: str
    download_url: str


class ImportResult(Strict):
    imported_design_ids: list[str]
    imported_workload_bundle_ids: list[str]
    imported_run_ids: list[str]
    trusted: Literal[False] = False


class DeleteResult(Strict):
    deleted: bool
    id: str


class CollectionItem(Strict):
    id: str
    kind: Literal["design", "run", "comparison"]
    title: str
    challenge_id: str
    created_at: datetime
    status: str | None = None


class Collection(Strict):
    items: list[CollectionItem]


class SavedSnapshot(Strict):
    snapshot_id: str
    title: str
    run_id: str
    case_id: str
    time_us: int
    created_at: datetime
    snapshot: Snapshot


class SaveSnapshotInput(Strict):
    title: str = Field(min_length=1, max_length=120)
    case_id: str
    time_us: int = Field(ge=0)


class SnapshotList(Strict):
    items: list[SavedSnapshot]
