"""Precompute immutable original arrivals, payload identities, and fault times."""

from __future__ import annotations

import bisect
import hashlib
import json
import random
from typing import Literal

from pydantic import Field

from backend.contracts import Challenge, Fault, Strict

GENERATOR_VERSION = "1"
MAX_ARRIVALS = 100_000


class Arrival(Strict):
    request_id: str
    operation_id: str
    key: str
    payload_id: str
    time_us: int = Field(ge=0)
    deadline_us: int = Field(gt=0)
    request_bytes: int
    response_bytes: int
    segment_id: str


class ScheduledFault(Strict):
    time_us: int
    fault: Fault


class WorkloadCase(Strict):
    challenge_id: str
    challenge_version: str
    scenario_id: str
    seed: int
    mode: Literal["assessment", "preview", "experiment"]
    warmup_end_us: int
    measurement_end_us: int
    drain_end_us: int
    initial_data_hash: str
    arrivals: list[Arrival]
    faults: list[ScheduledFault]
    generator_version: str = GENERATOR_VERSION


def _hash(data: object) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def workload_hash(case: WorkloadCase) -> str:
    return _hash(case.model_dump(mode="json"))


def bundle_hash(cases: list[WorkloadCase]) -> str:
    return _hash(sorted(workload_hash(case) for case in cases))


def generate_case(challenge: Challenge, scenario_id: str, seed: int, mode: Literal["assessment", "preview", "experiment"] = "assessment") -> WorkloadCase:
    scenario = next((s for s in challenge.scenarios if s.id == scenario_id), None)
    if scenario is None:
        raise ValueError("unknown scenario")
    if mode == "assessment" and (seed not in challenge.workload.assessment_seeds or not scenario.required):
        raise ValueError("not an assessment case")
    warmup = 10 if mode == "preview" else challenge.workload.warmup_seconds
    measurement = 60 if mode == "preview" else challenge.workload.measurement_seconds
    drain = 30 if mode == "preview" else challenge.workload.drain_seconds
    if mode == "preview" and (seed != 101 or scenario_id != next(s.id for s in challenge.scenarios if s.required)):
        raise ValueError("preview is first required scenario, seed 101")
    rng = random.Random(seed)
    operations = challenge.operations
    cumulative: list[float] = []
    total = 0.0
    for operation in operations:
        total += operation.weight
        cumulative.append(total)
    distribution = challenge.workload.key_distribution
    if distribution.type == "zipf":
        weights = [1 / (i + 1) ** distribution.exponent for i in range(distribution.key_count)]
        weight_sum = sum(weights)
        zipf_cdf = []
        acc = 0.0
        for weight in weights:
            acc += weight / weight_sum
            zipf_cdf.append(acc)
    else:
        zipf_cdf = []
    segments = [(0, warmup, scenario.warmup_rps, "warmup")]
    if mode == "preview":
        segments.append((warmup, warmup + measurement, scenario.rate_segments[0].rps, "0-60"))
    else:
        segments.extend((warmup + s.start_s, warmup + s.end_s, s.rps, f"{s.start_s}-{s.end_s}") for s in scenario.rate_segments)
    arrivals: list[Arrival] = []
    create_index = 0
    for start, end, rps, segment_id in segments:
        if rps == 0:
            continue
        now_us = start * 1_000_000
        end_us = end * 1_000_000
        while True:
            delta_us = max(1, round(rng.expovariate(rps) * 1_000_000))
            now_us += delta_us
            if now_us >= end_us:
                break  # next segment starts its own Poisson process
            if len(arrivals) >= MAX_ARRIVALS:
                raise ValueError("original arrival cap exceeded")
            op = operations[min(bisect.bisect_left(cumulative, rng.random()), len(operations) - 1)]
            ordinal = len(arrivals)
            unique = op.kind in {"put_object"} or (challenge.challenge_id == "url-shortener" and op.kind == "write_key")
            if unique:
                key = f"{challenge.initial_data.namespace}:new:{create_index}"
                create_index += 1
            else:
                index = rng.randrange(distribution.key_count) if not zipf_cdf else bisect.bisect_left(zipf_cdf, rng.random())
                if scenario.demand_shift_at_s is not None and now_us >= (warmup + scenario.demand_shift_at_s) * 1_000_000:
                    index = (index + distribution.key_count // 2) % distribution.key_count
                key = f"{challenge.initial_data.namespace}:{index}"
            arrivals.append(Arrival(request_id=f"{scenario_id}-{seed}-{ordinal}", operation_id=op.id, key=key, payload_id=f"payload:{scenario_id}:{seed}:{ordinal}", time_us=now_us, deadline_us=now_us + op.deadline_ms * 1_000, request_bytes=op.request_bytes, response_bytes=op.response_bytes, segment_id=segment_id))
    faults = [] if mode == "preview" else [ScheduledFault(time_us=(warmup + f.at_s) * 1_000_000, fault=f) for f in scenario.faults]
    return WorkloadCase(challenge_id=challenge.challenge_id, challenge_version=challenge.version, scenario_id=scenario_id, seed=seed, mode=mode, warmup_end_us=warmup * 1_000_000, measurement_end_us=(warmup + measurement) * 1_000_000, drain_end_us=(warmup + measurement + drain) * 1_000_000, initial_data_hash=_hash(challenge.initial_data.model_dump(mode="json")), arrivals=arrivals, faults=faults)
