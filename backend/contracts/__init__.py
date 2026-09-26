"""Versioned authored content and executable design contracts."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping
from datetime import datetime
from types import MappingProxyType
from typing import Annotated, Any, Literal, TypedDict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, with_config


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True, allow_inf_nan=False)


ComponentType = Literal["client", "load_balancer", "api_gateway", "app_service", "sql_database", "cache", "message_queue", "worker", "object_storage", "cdn"]
OperationKind = Literal["read_key", "write_key", "get_object", "put_object", "enqueue_job"]


class Operation(Strict):
    id: str
    kind: OperationKind
    weight: float = Field(gt=0, le=1)
    request_bytes: int = Field(ge=0)
    response_bytes: int = Field(ge=0)
    deadline_ms: int = Field(gt=0)
    retry_safe: bool
    freshness_allowance_ms: int | None = Field(default=None, ge=0)
    job_deadline_ms: int | None = Field(default=None, gt=0)


class InitialData(Strict):
    kind: Literal["versioned_keys", "immutable_objects", "empty_jobs"]
    namespace: str
    record_count: int = Field(ge=0)
    initial_version: int = Field(default=0, ge=0)
    object_bytes: int | None = Field(default=None, gt=0)


class KeyDistribution(Strict):
    type: Literal["uniform", "zipf"]
    key_count: int = Field(gt=0)
    exponent: float | None = Field(default=None, gt=0)


class WorkloadSettings(Strict):
    warmup_seconds: int = Field(gt=0)
    measurement_seconds: int = Field(gt=0)
    drain_seconds: int = Field(gt=0)
    assessment_seeds: list[int] = Field(min_length=1)
    key_distribution: KeyDistribution


class RateSegment(Strict):
    start_s: int = Field(ge=0)
    end_s: int = Field(gt=0)
    rps: float = Field(ge=0)


class Fault(Strict):
    type: Literal["clear_cache", "clear_cdn", "app_instance_unavailable", "service_multiplier"]
    at_s: int = Field(ge=0)
    end_s: int | None = None
    target_component_type: ComponentType | None = None
    target_node_id: str | None = None
    target_instance_id: str | None = None
    multiplier: float | None = Field(default=None, gt=0)


class Scenario(Strict):
    id: str
    required: bool
    warmup_rps: float = Field(ge=0)
    rate_segments: list[RateSegment]
    faults: list[Fault]
    demand_shift_at_s: int | None = None


class Requirement(Strict):
    id: str
    description: str
    metric: Literal["success_rate", "response_p95_ms", "response_p99_ms", "invalid_read_count", "freshness_violation_rate", "acknowledged_write_missing_count", "job_deadline_completion_rate", "duplicate_effect_count", "cost_credits_per_hour", "object_invalid_count", "object_capacity_violation_count"]
    operation_ids: list[str]
    scenario_ids: list[str]
    operator: Literal[">=", "<=", "=="]
    threshold: float
    unit: str
    min_samples: int = Field(ge=0)
    severity: Literal["hard"]


class Budget(Strict):
    max_credits_per_hour: int = Field(gt=0)
    profile_version: Literal["0.1.0"]


class Challenge(Strict):
    schema_version: Literal[1]
    challenge_id: str
    version: Literal["0.1.0"]
    title: str
    level: int = Field(ge=1, le=5)
    brief: str
    concepts: list[str]
    allowed_component_types: list[ComponentType]
    operations: list[Operation]
    initial_data: InitialData
    workload: WorkloadSettings
    scenarios: list[Scenario]
    requirements: list[Requirement]
    budget: Budget

    @model_validator(mode="after")
    def consistent(self) -> Challenge:
        if not math.isclose(sum(x.weight for x in self.operations), 1, abs_tol=1e-9):
            raise ValueError("operation weights must sum to one")
        ids = {x.id for x in self.operations}
        scenarios = {x.id for x in self.scenarios}
        if len(ids) != len(self.operations) or len(scenarios) != len(self.scenarios):
            raise ValueError("duplicate operation or scenario ID")
        for s in self.scenarios:
            pos = 0
            for segment in s.rate_segments:
                if segment.start_s != pos or segment.end_s <= pos:
                    raise ValueError(f"scenario {s.id} has a gap or overlap")
                pos = segment.end_s
            if pos != self.workload.measurement_seconds:
                raise ValueError(f"scenario {s.id} does not cover measurement")
            if any(f.at_s >= pos or (f.end_s is not None and not f.at_s < f.end_s <= pos) for f in s.faults):
                raise ValueError(f"scenario {s.id} fault is outside measurement")
        for r in self.requirements:
            if not set(r.operation_ids) <= ids or not set(r.scenario_ids) <= scenarios:
                raise ValueError(f"requirement {r.id} references unknown scope")
        if self.workload.key_distribution.key_count != self.initial_data.record_count and self.initial_data.kind != "empty_jobs":
            raise ValueError("key distribution and initial data disagree")
        return self


class Position(Strict):
    x: float
    y: float

    @field_validator("x", "y")
    @classmethod
    def finite(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("position must be finite")
        return value


SETTINGS: dict[str, dict[str, tuple[type, float, float] | tuple[str, ...]]] = {
    "client": {}, "sql_database": {}, "object_storage": {}, "cdn": {"ttl_seconds": (int, 1, 120)},
    "load_balancer": {},
    "api_gateway": {"rate_limit_rps": (int, 1, 100_000), "bucket_size": (int, 1, 100_000)},
    "app_service": {"dependency_timeout_ms": (int, 1, 10_000), "max_retries": (int, 0, 2), "invalidation": ("off", "synchronous")},
    "cache": {"ttl_seconds": (int, 1, 120)},
    "message_queue": {"lease_seconds": (int, 1, 10), "max_attempts": (int, 1, 3)},
    "worker": {"deduplicate": (bool, 0, 1)},
}


@with_config(ConfigDict(extra="forbid"))
class EmptySettings(TypedDict):
    pass


@with_config(ConfigDict(extra="forbid"))
class GatewaySettings(TypedDict, total=False):
    rate_limit_rps: Annotated[int, Field(ge=1, le=100_000, strict=True)]
    bucket_size: Annotated[int, Field(ge=1, le=100_000, strict=True)]


@with_config(ConfigDict(extra="forbid"))
class AppSettings(TypedDict, total=False):
    dependency_timeout_ms: Annotated[int, Field(ge=1, le=10_000, strict=True)]
    max_retries: Annotated[int, Field(ge=0, le=2, strict=True)]
    invalidation: Literal["off", "synchronous"]


@with_config(ConfigDict(extra="forbid"))
class CacheSettings(TypedDict, total=False):
    ttl_seconds: Annotated[int, Field(ge=1, le=120, strict=True)]


@with_config(ConfigDict(extra="forbid"))
class QueueSettings(TypedDict, total=False):
    lease_seconds: Annotated[int, Field(ge=1, le=10, strict=True)]
    max_attempts: Annotated[int, Field(ge=1, le=3, strict=True)]


@with_config(ConfigDict(extra="forbid"))
class WorkerSettings(TypedDict, total=False):
    deduplicate: bool


Settings = EmptySettings | GatewaySettings | AppSettings | CacheSettings | QueueSettings | WorkerSettings


class Node(Strict):
    id: str
    type: ComponentType
    label: str
    profile_id: str
    instance_count: int = Field(ge=1, le=32)
    settings: Settings
    position: Position

    @model_validator(mode="after")
    def check_settings(self) -> Node:
        allowed = SETTINGS[self.type]
        for key, value in self.settings.items():
            if key not in allowed:
                raise ValueError(f"unsupported setting {key}")
            rule = allowed[key]
            if len(rule) == 3 and isinstance(rule[0], type):
                typ, lo, hi = rule
                if type(value) is not typ or not lo <= value <= hi:
                    raise ValueError(f"invalid {key}")
            elif value not in rule:
                raise ValueError(f"invalid {key}")
        return self


class ClientNode(Node):
    type: Literal["client"]
    settings: EmptySettings


class LoadBalancerNode(Node):
    type: Literal["load_balancer"]
    settings: EmptySettings


class GatewayNode(Node):
    type: Literal["api_gateway"]
    settings: GatewaySettings


class AppNode(Node):
    type: Literal["app_service"]
    settings: AppSettings


class SqlNode(Node):
    type: Literal["sql_database"]
    settings: EmptySettings


class CacheNode(Node):
    type: Literal["cache"]
    settings: CacheSettings


class QueueNode(Node):
    type: Literal["message_queue"]
    settings: QueueSettings


class WorkerNode(Node):
    type: Literal["worker"]
    settings: WorkerSettings


class ObjectNode(Node):
    type: Literal["object_storage"]
    settings: EmptySettings


class CdnNode(Node):
    type: Literal["cdn"]
    settings: CacheSettings


DesignNode = Annotated[ClientNode | LoadBalancerNode | GatewayNode | AppNode | SqlNode | CacheNode | QueueNode | WorkerNode | ObjectNode | CdnNode, Field(discriminator="type")]


class Edge(Strict):
    id: str
    source: str
    target: str
    kind: Literal["request", "cache_miss", "invalidate", "consume"]
    operation_ids: list[str]


class DesignRevision(Strict):
    schema_version: Literal[1]
    design_id: str
    revision_id: str
    challenge_id: str
    challenge_version: Literal["0.1.0"]
    created_at: datetime
    parent_revision_id: str | None
    nodes: list[DesignNode] = Field(max_length=25)
    edges: list[Edge] = Field(max_length=60)


class Profile(Strict):
    model_config = ConfigDict(extra="forbid", frozen=True)
    id: str
    component_type: ComponentType
    slots: int
    queue_limit: int
    service_ms: float
    write_service_ms: float | None = None
    capacity: int | None = None
    credits_per_hour: int
    coefficient_of_variation: float = 0.25
    support_label: Literal["Simulated"] = "Simulated"


_SMALL = {
    "client": ("client", 0, 0, 0, None, None, 0),
    "lb": ("load_balancer", 64, 500, .5, None, None, 5),
    "gateway": ("api_gateway", 32, 200, 1, None, None, 5),
    "app": ("app_service", 4, 100, 2, None, None, 5),
    "sql": ("sql_database", 2, 100, 20, 30, 100_000, 20),
    "cache": ("cache", 16, 100, 1, None, 128, 8),
    "queue": ("message_queue", 16, 100, 1, None, 10_000, 5),
    "worker": ("worker", 2, 0, 50, None, None, 5),
    "object": ("object_storage", 16, 100, 5, None, 1 << 30, 10),
    "cdn": ("cdn", 32, 200, 1, None, 64 << 20, 8),
}
_profiles: dict[str, Profile] = {}
for prefix, row in _SMALL.items():
    component_type, slots, queue, service, write, capacity, cost = row
    for size, factor in (("small", 1), ("medium", 2), ("large", 4)) if prefix != "client" else (("", 1),):
        profile_id = "client.v1" if prefix == "client" else f"{prefix}.{size}.v1"
        _profiles[profile_id] = Profile(id=profile_id, component_type=component_type, slots=slots * factor, queue_limit=queue, service_ms=service, write_service_ms=write, capacity=capacity * factor if capacity and prefix in {"cache", "queue", "object", "cdn"} else capacity, credits_per_hour=cost * factor)
PROFILES: Mapping[str, Profile] = MappingProxyType(_profiles)


def profile_for(node: Node) -> Profile:
    profile = PROFILES.get(node.profile_id)
    if profile is None or profile.component_type != node.type:
        raise ValueError(f"unknown or mismatched profile {node.profile_id}")
    return profile


class ValidationFinding(Strict):
    code: str
    message: str
    node_ids: list[str] = []
    edge_ids: list[str] = []


class CompiledRoute(Strict):
    operation_id: str
    kind: OperationKind
    entry_node_id: str
    node_ids: list[str]
    request_edge_ids: list[str]
    miss_edge_ids: list[str]
    invalidation_edge_ids: list[str]
    consume_edge_ids: list[str]


class CompiledDesign(Strict):
    design: DesignRevision
    routes: dict[str, CompiledRoute]
    cost_credits_per_hour: int
    design_hash: str


def validate_draft(design: DesignRevision, challenge: Challenge) -> list[ValidationFinding]:
    findings: list[ValidationFinding] = []
    if (design.challenge_id, design.challenge_version) != (challenge.challenge_id, challenge.version):
        findings.append(ValidationFinding(code="challenge_mismatch", message="Unknown challenge version"))
    nodes = {n.id: n for n in design.nodes}
    edges = {e.id: e for e in design.edges}
    if len(nodes) != len(design.nodes) or len(edges) != len(design.edges):
        findings.append(ValidationFinding(code="duplicate_id", message="Node and edge IDs must be unique"))
    clients = [n for n in design.nodes if n.type == "client"]
    if len(clients) > 1 or (clients and clients[0].instance_count != 1):
        findings.append(ValidationFinding(code="client_count", message="At most one single-instance client is allowed in a draft"))
    for n in design.nodes:
        if n.type not in challenge.allowed_component_types:
            findings.append(ValidationFinding(code="component_forbidden", message="Component is not allowed", node_ids=[n.id]))
        try:
            profile_for(n)
        except ValueError as exc:
            findings.append(ValidationFinding(code="profile", message=str(exc), node_ids=[n.id]))
        if n.type in {"sql_database", "object_storage", "message_queue"} and n.instance_count != 1:
            findings.append(ValidationFinding(code="instance_count", message="Logical store or queue requires one instance", node_ids=[n.id]))
    op_ids = {o.id for o in challenge.operations}
    allowed_edges = {
        "request": {"client": {"load_balancer", "api_gateway", "app_service", "cdn", "object_storage"}, "load_balancer": {"api_gateway", "app_service"}, "api_gateway": {"app_service", "cdn", "object_storage"}, "app_service": {"sql_database", "cache", "message_queue", "object_storage"}},
        "cache_miss": {"cache": {"sql_database"}, "cdn": {"object_storage"}},
        "invalidate": {"app_service": {"cache"}},
        "consume": {"message_queue": {"worker"}},
    }
    for e in design.edges:
        if e.source not in nodes or e.target not in nodes:
            findings.append(ValidationFinding(code="edge_reference", message="Edge references missing node", edge_ids=[e.id]))
        elif nodes[e.target].type not in allowed_edges[e.kind].get(nodes[e.source].type, set()):
            findings.append(ValidationFinding(code="edge_kind", message="Unsupported edge relationship", edge_ids=[e.id]))
        if not e.operation_ids or len(set(e.operation_ids)) != len(e.operation_ids) or not set(e.operation_ids) <= op_ids:
            findings.append(ValidationFinding(code="edge_operation", message="Invalid edge operations", edge_ids=[e.id]))
    return findings


def compile_design(design: DesignRevision, challenge: Challenge, *, _branch: bool = False) -> CompiledDesign:
    findings = validate_draft(design, challenge)
    if findings:
        raise ValueError("; ".join(f.message for f in findings))
    if sum(n.type == "client" for n in design.nodes) != 1:
        raise ValueError("runnable route requires exactly one client")
    nodes = {n.id: n for n in design.nodes}
    routes: dict[str, CompiledRoute] = {}
    client = next(n for n in design.nodes if n.type == "client")
    for operation in challenge.operations:
        selected_nodes: list[str] = [client.id]
        request_edges: list[str] = []
        miss_edges: list[str] = []
        invalidations: list[str] = []
        consume_edges: list[str] = []
        seen: set[str] = set()
        current = client
        while True:
            if current.id in seen:
                raise ValueError(f"cycle in route for {operation.id}")
            seen.add(current.id)
            outgoing = [e for e in design.edges if e.source == current.id and operation.id in e.operation_ids]
            req = [e for e in outgoing if e.kind == "request"]
            miss = [e for e in outgoing if e.kind == "cache_miss"]
            consume = [e for e in outgoing if e.kind == "consume"]
            inv = [e for e in outgoing if e.kind == "invalidate"]
            if current.type in {"sql_database", "object_storage", "worker"}:
                expected = {"read_key": "sql_database", "write_key": "sql_database", "get_object": "object_storage", "put_object": "object_storage", "enqueue_job": "worker"}[operation.kind]
                if current.type != expected or outgoing:
                    raise ValueError(f"incompatible terminal route for {operation.id}")
                break
            if current.type == "message_queue":
                if operation.kind != "enqueue_job" or req or miss or inv or not consume:
                    raise ValueError(f"invalid queue route for {operation.id}")
                targets = [nodes[e.target] for e in consume]
                if any(n.type != "worker" for n in targets):
                    raise ValueError(f"invalid consume route for {operation.id}")
                consume_edges.extend(e.id for e in consume)
                selected_nodes.extend(n.id for n in targets)
                break
            if current.type == "app_service":
                if operation.kind == "write_key":
                    if any(nodes[e.target].type != "cache" for e in inv):
                        raise ValueError(f"invalid invalidate route for {operation.id}")
                    if inv and current.settings.get("invalidation", "off") != "synchronous":
                        raise ValueError(f"invalidation edge requires synchronous policy for {operation.id}")
                    invalidations.extend(e.id for e in inv)
                elif inv:
                    raise ValueError(f"invalid invalidate route for {operation.id}")
            elif inv:
                raise ValueError(f"invalid invalidate route for {operation.id}")
            if current.type in {"cache", "cdn"}:
                if (current.type == "cache" and operation.kind != "read_key") or (current.type == "cdn" and operation.kind != "get_object") or len(miss) != 1 or req or consume:
                    raise ValueError(f"invalid cache miss route for {operation.id}")
                edge = miss[0]
                target_type = "sql_database" if current.type == "cache" else "object_storage"
                if nodes[edge.target].type != target_type:
                    raise ValueError(f"invalid cache miss target for {operation.id}")
                miss_edges.append(edge.id)
            else:
                if miss or consume or not req or (len(req) != 1 and current.type != "load_balancer"):
                    raise ValueError(f"incomplete or ambiguous route for {operation.id}")
                edge = req[0]
                allowed = {"client": {"load_balancer", "api_gateway", "app_service", "cdn", "object_storage"}, "load_balancer": {"api_gateway", "app_service"}, "api_gateway": {"app_service", "cdn", "object_storage"}, "app_service": {"sql_database", "cache", "message_queue", "object_storage"}}.get(current.type, set())
                if any(nodes[e.target].type not in allowed for e in req):
                    raise ValueError(f"invalid request route for {operation.id}")
                request_edges.extend(e.id for e in req)
            current = nodes[edge.target]
            selected_nodes.append(current.id)
        routes[operation.id] = CompiledRoute(operation_id=operation.id, kind=operation.kind, entry_node_id=client.id, node_ids=selected_nodes, request_edge_ids=request_edges, miss_edge_ids=miss_edges, invalidation_edge_ids=invalidations, consume_edge_ids=consume_edges)
        # Every load-balancer target must implement the operation, not just its first target.
        for lb_id in (node_id for node_id in selected_nodes if nodes[node_id].type == "load_balancer"):
            choices = [e for e in design.edges if e.source == lb_id and e.kind == "request" and operation.id in e.operation_ids]
            for chosen in choices[1:]:
                branch_edges = [e.model_copy(update={"operation_ids": [operation.id]}) for e in design.edges if operation.id in e.operation_ids and (e.source != lb_id or e.id == chosen.id)]
                branch = compile_design(design.model_copy(update={"edges": branch_edges}), challenge.model_copy(update={"operations": [operation], "requirements": []}), _branch=True).routes[operation.id]
                for field in ("node_ids", "request_edge_ids", "miss_edge_ids", "invalidation_edge_ids", "consume_edge_ids"):
                    for item in getattr(branch, field):
                        if item not in getattr(routes[operation.id], field):
                            getattr(routes[operation.id], field).append(item)
    for store_type in ("sql_database", "object_storage"):
        stores = {node_id for route in routes.values() for node_id in route.node_ids if nodes[node_id].type == store_type}
        if len(stores) > 1:
            raise ValueError(f"route uses multiple independent {store_type} stores")
    if not _branch:
        for operation in challenge.operations:
            route = routes[operation.id]
            used = set(route.request_edge_ids + route.miss_edge_ids + route.invalidation_edge_ids + route.consume_edge_ids)
            if any(operation.id in edge.operation_ids and edge.id not in used for edge in design.edges):
                raise ValueError(f"unreachable route edge for {operation.id}")
    cost = sum(profile_for(n).credits_per_hour * n.instance_count for n in design.nodes)
    return CompiledDesign(design=design, routes=routes, cost_credits_per_hour=cost, design_hash=design_hash(design))


def design_hash(design: DesignRevision) -> str:
    data = {"challenge_id": design.challenge_id, "challenge_version": design.challenge_version,
            "nodes": sorted(({"id": n.id, "type": n.type, "profile_id": n.profile_id, "instance_count": n.instance_count, "settings": n.settings} for n in design.nodes), key=lambda n: n["id"]),
            "edges": sorted((e.model_dump(mode="json") for e in design.edges), key=lambda e: e["id"])}
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def apply_patch(design: DesignRevision, patch: dict[str, Any], challenge: Challenge) -> DesignRevision:
    if set(patch) != {"base_revision_id", "operations"} or patch["base_revision_id"] != design.revision_id or not isinstance(patch["operations"], list) or not 1 <= len(patch["operations"]) <= 20:
        raise ValueError("invalid or stale patch")
    data = design.model_dump(mode="json")
    for change in patch["operations"]:
        op = change.get("op")
        if op == "add_node" and set(change) == {"op", "node"}:
            data["nodes"].append(change["node"])
        elif op == "remove_node" and set(change) == {"op", "node_id"}:
            if not any(n["id"] == change["node_id"] for n in data["nodes"]):
                raise ValueError("missing node")
            if any(n["id"] == change["node_id"] and n["type"] == "client" for n in data["nodes"]):
                raise ValueError("cannot remove client")
            data["nodes"] = [n for n in data["nodes"] if n["id"] != change["node_id"]]
            data["edges"] = [e for e in data["edges"] if change["node_id"] not in (e["source"], e["target"])]
        elif op == "set_node_setting" and set(change) == {"op", "node_id", "key", "value"}:
            node = next((n for n in data["nodes"] if n["id"] == change["node_id"]), None)
            if node is None:
                raise ValueError("missing node")
            if change["key"] in {"profile_id", "instance_count"}:
                node[change["key"]] = change["value"]
            else:
                node["settings"][change["key"]] = change["value"]
        elif op == "add_edge" and set(change) == {"op", "edge"}:
            data["edges"].append(change["edge"])
        elif op == "remove_edge" and set(change) == {"op", "edge_id"}:
            if not any(e["id"] == change["edge_id"] for e in data["edges"]):
                raise ValueError("missing edge")
            data["edges"] = [e for e in data["edges"] if e["id"] != change["edge_id"]]
        else:
            raise ValueError("unsupported patch operation")
    data["parent_revision_id"] = design.revision_id
    data["revision_id"] = design.revision_id + "-candidate"
    candidate = DesignRevision.model_validate(data)
    compile_design(candidate, challenge)
    return candidate


class RequestOutcome(Strict):
    request_id: str
    operation_id: str
    key: str
    arrival_us: int
    deadline_us: int
    terminal_us: int
    status: Literal["success", "timeout", "rejected", "dependency_error", "invalid_result", "incomplete"]
    returned_payload_id: str | None = None
    returned_version: int | None = None
    correct: bool | None = None
    fresh: bool | None = None
    acknowledged_commit_us: int | None = None


class JobOutcome(Strict):
    job_id: str
    request_id: str
    attempts: int = Field(ge=0)
    acknowledged_us: int | None = None
    first_effect_us: int | None = None
    terminal_state: Literal["delivered", "failed", "expired", "pending"]
    duplicate_effect_count: int = Field(ge=0)


class MetricValue(Strict):
    value: float | None
    unit: str
    sample_count: int = Field(ge=0)
    unavailable_reason: str | None = None

    @field_validator("value")
    @classmethod
    def finite_value(cls, value: float | None) -> float | None:
        if value is not None and not math.isfinite(value):
            raise ValueError("metric value must be finite")
        return value


class RequirementOutcome(Strict):
    requirement_id: str
    scenario_id: str
    seed: int
    operation_id: str | None
    status: Literal["pass", "fail", "not_evaluated", "incomplete"]
    measured: MetricValue | None
    evidence_ids: list[str]


class EvidenceItem(Strict):
    evidence_id: str
    type: str
    unit: str
    value: float | str | None
    scope: str
    sample_count: int = Field(ge=0)
    artifact_ref: str | None


class CaseResult(Strict):
    case_id: str
    scenario_id: str
    seed: int
    execution_status: Literal["queued", "running", "completed", "canceled", "failed", "interrupted"]
    operation_metrics: dict[str, dict[str, MetricValue]]
    node_metrics: dict[str, dict[str, MetricValue]]
    requirement_outcomes: list[RequirementOutcome]
    evidence: list[EvidenceItem]
    trace_refs: list[str]


class AssessmentResult(Strict):
    status: Literal["pass", "fail", "not_evaluated", "incomplete"]
    case_results: list[CaseResult]
    requirement_outcomes: list[RequirementOutcome]
