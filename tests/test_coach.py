import json

import pytest

from backend.coach import render_review, request_review, validate_review
from backend.content import load_challenge, load_fixture
from backend.contracts import EvidenceItem


def test_coach_requires_real_evidence_for_numbers_and_references():
    challenge = load_challenge("product-catalogue")
    design = load_fixture("product-catalogue", "reference")
    evidence = [EvidenceItem(evidence_id="metric:latency", type="metric", unit="ms", value=42.0, scope="case", sample_count=10, artifact_ref="cases/x/result.json")]
    review = {"strengths": [], "findings": [], "suggested_experiments": [], "limitations": ["Latency is {{evidence:metric:latency}}."]}
    assert validate_review(review, evidence, design, challenge).limitations == review["limitations"]
    with pytest.raises(ValueError):
        validate_review({**review, "limitations": ["Latency is 42 ms."]}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**review, "limitations": ["Latency is {{evidence:fake}}."]}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**review, "findings": [{"id": "bad", "title": "Unknown", "severity": "high", "requirement_id": None, "node_ids": [], "explanation": "Unsupported", "evidence_refs": ["fake"], "classification": "observed"}]}, evidence, design, challenge)


def test_declared_calculation_and_worded_number_are_checked():
    challenge = load_challenge("product-catalogue")
    design = load_fixture("product-catalogue", "reference")
    evidence = [EvidenceItem(evidence_id="baseline:p95", type="metric", unit="ms", value=42.0, scope="baseline", sample_count=10, artifact_ref="cases/x/result.json"), EvidenceItem(evidence_id="candidate:p95", type="metric", unit="ms", value=30.0, scope="candidate", sample_count=10, artifact_ref="cases/y/result.json")]
    base = {"strengths": [], "findings": [], "suggested_experiments": [], "limitations": ["Difference is {{calc:subtract|baseline:p95|candidate:p95}}."]}
    parsed = validate_review(base, evidence, design, challenge)
    assert "12.0 ms" in render_review(parsed, evidence)["limitations"][0]
    with pytest.raises(ValueError):
        validate_review({**base, "limitations": ["It is twice as fast."]}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**base, "limitations": ["It saved one million milliseconds."]}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**base, "limitations": ["Difference is {{calc:subtract|baseline:p95|candidate:p99}}."]}, [evidence[0], evidence[1].model_copy(update={"evidence_id": "candidate:p99"})], design, challenge)


def test_coach_cannot_assert_overall_verdict_but_can_explain_requirement():
    challenge = load_challenge("product-catalogue")
    design = load_fixture("product-catalogue", "reference")
    requirement_id = challenge.requirements[0].id
    evidence = [EvidenceItem(evidence_id=f"requirement:{requirement_id}", type="requirement", unit="fraction", value=0.8, scope="case", sample_count=10, artifact_ref="assessment.json")]
    base = {"strengths": [], "findings": [], "suggested_experiments": [], "limitations": []}
    for claim in ("The assessment passed all requirements.", "The run failed overall.", "All requirements were met.", "The assessment was successful."):
        with pytest.raises(ValueError):
            validate_review({**base, "summary": claim}, evidence, design, challenge)
    finding = {"id": "observation", "title": "Read quality", "severity": "high", "requirement_id": requirement_id, "node_ids": [], "explanation": f"Requirement {requirement_id} failed during the burst.", "evidence_refs": [f"requirement:{requirement_id}"], "classification": "observed"}
    assert validate_review({**base, "findings": [finding]}, evidence, design, challenge).findings[0].classification == "observed"


@pytest.mark.parametrize("usage", [[], "bad usage"])
def test_malformed_provider_content_keeps_raw_body(monkeypatch, usage):
    import httpx
    import backend.coach as coach

    real_client = httpx.AsyncClient
    def handler(request):
        sent = json.loads(request.content)
        context = json.loads(sent["messages"][1]["content"])
        assert next(node for node in context["design"]["nodes"] if node["id"] == "app")["instance_count"] == 1
        assert any(profile["id"] == "app.small.v1" and profile["credits_per_hour"] == 5 and profile["slots"] == 4 for profile in context["profiles"])
        assert "app_service" in context["support_limits"]["allowed_component_types"]
        assert context["support_limits"]["component_settings"]["app_service"]["max_retries"] == {"min": 0, "max": 2}
        assert context["support_limits"]["model_scope"]
        return httpx.Response(200, json={"choices": [{"message": {"content": "{bad-json"}}], "usage": usage})
    monkeypatch.setattr(coach.httpx, "AsyncClient", lambda: real_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setenv("AISD_AI_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("AISD_AI_MODEL", "test")
    monkeypatch.setenv("AISD_AI_API_KEY", "secret")
    with pytest.raises(coach.ProviderOutputError) as failure:
        request_review(load_challenge("product-catalogue"), load_fixture("product-catalogue", "reference"), [], {})
    assert failure.value.raw_response == "{bad-json"
    assert failure.value.usage is None


@pytest.mark.parametrize("phase", ["connect", "body", "retry_body"])
def test_total_deadline_cancels_transport_and_closes_partial_body(monkeypatch, phase):
    import asyncio
    import time
    import httpx
    import backend.coach as coach

    actual_client = httpx.AsyncClient
    budget = 1.1 if phase == "retry_body" else .15
    calls, closed = [], []
    class Trickle(httpx.AsyncByteStream):
        async def __aiter__(self):
            yield b'{"partial":'
            while True:
                await asyncio.sleep(.03)
                yield b' '
        async def aclose(self):
            closed.append(True)
    async def handler(request):
        calls.append(request)
        if phase == "connect":
            try:
                await asyncio.sleep(5)
            finally:
                closed.append(True)
        if phase == "retry_body" and len(calls) == 1:
            return httpx.Response(503, text="retry diagnostic")
        return httpx.Response(200, stream=Trickle())
    monkeypatch.setattr(coach, "PROVIDER_BUDGET_SECONDS", budget)
    monkeypatch.setattr(coach.httpx, "AsyncClient", lambda: actual_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setenv("AISD_AI_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("AISD_AI_MODEL", "test")
    monkeypatch.setenv("AISD_AI_API_KEY", "secret")
    started = time.monotonic()
    with pytest.raises(coach.ProviderOutputError, match="total deadline") as failure:
        request_review(load_challenge("product-catalogue"), load_fixture("product-catalogue", "reference"), [], {})
    assert budget <= time.monotonic() - started < budget + .5
    assert budget * 1000 <= failure.value.latency_ms < (budget + .5) * 1000
    assert len(calls) == (2 if phase == "retry_body" else 1)
    assert closed == [True]
    assert failure.value.raw_response.startswith('{"partial":') if phase != "connect" else failure.value.raw_response == ""


def test_provider_patch_converts_added_node_settings_and_keeps_bounds():
    from backend.coach import ProviderPatch
    challenge = load_challenge("team-notes")
    design = load_fixture(challenge.challenge_id, "initial")
    node = next(n for n in design.nodes if n.type == "app_service").model_dump(mode="json")
    node.update(id="extra", settings=[{"key": "max_retries", "value": 1}])
    patch = {"base_revision_id": design.revision_id, "operations": [{"op": "add_node", "node": node}]}
    proposal = ProviderPatch.model_validate(patch).to_patch()
    assert proposal["operations"][0]["node"]["settings"] == {"max_retries": 1}
    assert validate_review({"strengths": [], "findings": [], "limitations": [], "suggested_experiments": [{"purpose": "Explore capacity", "patch": proposal, "evidence_refs": [], "expected_tradeoffs": "More cost"}]}, [], design, challenge)
    with pytest.raises(ValueError):
        ProviderPatch.model_validate({**patch, "operations": patch["operations"] * 21})
    node["settings"].append({"key": "max_retries", "value": 2})
    with pytest.raises(ValueError, match="duplicate"):
        ProviderPatch.model_validate(patch).to_patch()
