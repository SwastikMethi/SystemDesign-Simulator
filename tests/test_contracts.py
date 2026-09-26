import copy
from pathlib import Path

import pytest
from pydantic import ValidationError

from backend.content import list_challenges, load_challenge, load_fixture
from backend.contracts import PROFILES, Challenge, DesignRevision, apply_patch, compile_design, design_hash, validate_draft


def test_all_content_compiles_and_costs():
    assert len(list_challenges()) == 5
    for challenge in list_challenges():
        for name in ("initial", "reference", "failure", "budget"):
            design = load_fixture(challenge.challenge_id, name)
            compiled = compile_design(design, challenge)
            assert len(compiled.routes) == len(challenge.operations)
            assert compiled.cost_credits_per_hour >= 0


def test_draft_safe_but_runnable_strict():
    challenge = load_challenge("product-catalogue")
    design = load_fixture(challenge.challenge_id, "initial")
    broken = design.model_copy(update={"edges": []})
    assert validate_draft(broken, challenge) == []
    with pytest.raises(ValueError, match="route"):
        compile_design(broken, challenge)
    empty = design.model_copy(update={"nodes": [], "edges": []})
    assert validate_draft(empty, challenge) == []
    with pytest.raises(ValueError, match="client"):
        compile_design(empty, challenge)


def test_hash_excludes_labels_positions_and_revision_metadata():
    challenge = load_challenge("product-catalogue")
    design = load_fixture(challenge.challenge_id, "initial")
    data = design.model_dump(mode="json")
    data["nodes"][0]["label"] = "renamed"
    data["nodes"][0]["position"] = {"x": 999, "y": -900}
    data["revision_id"] = "other"
    assert design_hash(design) == design_hash(DesignRevision.model_validate(data))


def test_invalid_patch_rejected_and_input_untouched():
    challenge = load_challenge("team-notes")
    design = load_fixture(challenge.challenge_id, "initial")
    before = design.model_dump(mode="json")
    with pytest.raises(ValueError):
        apply_patch(design, {"base_revision_id": design.revision_id, "operations": [{"op": "set_node_setting", "node_id": "app", "key": "free_capacity", "value": 999}]}, challenge)
    with pytest.raises(ValueError, match="stale"):
        apply_patch(design, {"base_revision_id": "older", "operations": [{"op": "remove_node", "node_id": "client"}]}, challenge)
    with pytest.raises(ValueError, match="client"):
        apply_patch(design, {"base_revision_id": design.revision_id, "operations": [{"op": "remove_node", "node_id": "client"}]}, challenge)
    assert design.model_dump(mode="json") == before


def test_profile_costs_and_cardinality():
    assert PROFILES["sql.small.v1"].credits_per_hour == 20
    assert PROFILES["sql.medium.v1"].slots == 4
    assert PROFILES["cache.large.v1"].capacity == 512
    challenge = load_challenge("product-catalogue")
    reference = compile_design(load_fixture(challenge.challenge_id, "reference"), challenge)
    assert reference.cost_credits_per_hour <= challenge.budget.max_credits_per_hour
    assert compile_design(load_fixture(challenge.challenge_id, "budget"), challenge).cost_credits_per_hour > challenge.budget.max_credits_per_hour


def test_invalid_route_kind_rejected():
    challenge = load_challenge("team-notes")
    data = load_fixture(challenge.challenge_id, "initial").model_dump(mode="json")
    data["edges"][1]["kind"] = "cache_miss"
    with pytest.raises(ValueError, match="relationship"):
        compile_design(DesignRevision.model_validate(data), challenge)


def test_extra_fields_and_nonfinite_rejected():
    design = load_fixture("team-notes", "initial").model_dump(mode="json")
    design["nodes"][0]["settings"]["surprise"] = 1
    with pytest.raises(ValidationError):
        DesignRevision.model_validate(design)
    design["nodes"][0]["settings"] = {}
    design["nodes"][0]["position"]["x"] = float("nan")
    with pytest.raises(ValidationError):
        DesignRevision.model_validate(design)


def test_published_examples_remain_valid():
    Challenge.model_validate_json(Path("docs/examples/catalogue-challenge.json").read_text())
    DesignRevision.model_validate_json(Path("docs/examples/catalogue-starter-design.json").read_text())


def test_load_balancer_checks_all_targets():
    challenge = load_challenge("team-notes")
    data = load_fixture("team-notes", "initial").model_dump(mode="json")
    app2 = copy.deepcopy(data["nodes"][1])
    app2["id"] = "app2"
    data["nodes"].append(app2)
    data["nodes"].append({"id": "lb", "type": "load_balancer", "label": "LB", "profile_id": "lb.small.v1", "instance_count": 1, "settings": {}, "position": {"x": 1, "y": 1}})
    data["edges"] = [
        {"id": "client-lb", "source": "client", "target": "lb", "kind": "request", "operation_ids": ["read_note", "write_note"]},
        {"id": "lb-app", "source": "lb", "target": "app", "kind": "request", "operation_ids": ["read_note", "write_note"]},
        {"id": "lb-app2", "source": "lb", "target": "app2", "kind": "request", "operation_ids": ["read_note", "write_note"]},
        {"id": "app-sql", "source": "app", "target": "sql", "kind": "request", "operation_ids": ["read_note", "write_note"]},
        {"id": "app2-sql", "source": "app2", "target": "sql", "kind": "request", "operation_ids": ["read_note", "write_note"]},
    ]
    compiled = compile_design(DesignRevision.model_validate(data), challenge)
    assert {"lb-app", "lb-app2"} <= set(compiled.routes["read_note"].request_edge_ids)
    data["edges"][-1]["target"] = "client"
    with pytest.raises(ValueError):
        compile_design(DesignRevision.model_validate(data), challenge)
