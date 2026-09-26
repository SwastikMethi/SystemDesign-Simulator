import pytest

from backend.coach import render_review, request_review, validate_review
from backend.content import load_challenge, load_fixture
from backend.contracts import EvidenceItem


def test_coach_requires_real_evidence_for_numbers_and_references():
    challenge = load_challenge("product-catalogue")
    design = load_fixture("product-catalogue", "reference")
    evidence = [EvidenceItem(evidence_id="metric:latency", type="metric", unit="ms", value=42.0, scope="case", sample_count=10, artifact_ref="cases/x/result.json")]
    review = {"summary": "Latency is {{evidence:metric:latency}}.", "strengths": [], "findings": [], "suggested_experiments": [], "limitations": []}
    assert validate_review(review, evidence, design, challenge).summary == review["summary"]
    with pytest.raises(ValueError):
        validate_review({**review, "summary": "Latency is 42 ms."}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**review, "summary": "Latency is {{evidence:fake}}."}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**review, "findings": [{"id": "bad", "title": "Unknown", "severity": "high", "requirement_id": None, "node_ids": [], "explanation": "Unsupported", "evidence_refs": ["fake"], "classification": "observed"}]}, evidence, design, challenge)


def test_declared_calculation_and_worded_number_are_checked():
    challenge = load_challenge("product-catalogue")
    design = load_fixture("product-catalogue", "reference")
    evidence = [EvidenceItem(evidence_id="baseline:p95", type="metric", unit="ms", value=42.0, scope="baseline", sample_count=10, artifact_ref="cases/x/result.json"), EvidenceItem(evidence_id="candidate:p95", type="metric", unit="ms", value=30.0, scope="candidate", sample_count=10, artifact_ref="cases/y/result.json")]
    base = {"summary": "Difference is {{calc:subtract|baseline:p95|candidate:p95}}.", "strengths": [], "findings": [], "suggested_experiments": [], "limitations": []}
    parsed = validate_review(base, evidence, design, challenge)
    assert "12.0 ms" in render_review(parsed, evidence)["summary"]
    with pytest.raises(ValueError):
        validate_review({**base, "summary": "It is twice as fast."}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**base, "summary": "It saved one million milliseconds."}, evidence, design, challenge)
    with pytest.raises(ValueError):
        validate_review({**base, "summary": "Difference is {{calc:subtract|baseline:p95|candidate:p99}}."}, [evidence[0], evidence[1].model_copy(update={"evidence_id": "candidate:p99"})], design, challenge)


def test_coach_cannot_assert_overall_verdict_but_can_explain_requirement():
    challenge = load_challenge("product-catalogue")
    design = load_fixture("product-catalogue", "reference")
    requirement_id = challenge.requirements[0].id
    evidence = [EvidenceItem(evidence_id=f"requirement:{requirement_id}", type="requirement", unit="fraction", value=0.8, scope="case", sample_count=10, artifact_ref="assessment.json")]
    base = {"summary": "The cache helped repeated reads.", "strengths": [], "findings": [], "suggested_experiments": [], "limitations": []}
    for claim in ("The assessment passed all requirements.", "The run failed overall.", "All requirements were met."):
        with pytest.raises(ValueError):
            validate_review({**base, "summary": claim}, evidence, design, challenge)
    finding = {"id": "observation", "title": "Read quality", "severity": "high", "requirement_id": requirement_id, "node_ids": [], "explanation": f"Requirement {requirement_id} failed during the burst.", "evidence_refs": [f"requirement:{requirement_id}"], "classification": "observed"}
    assert validate_review({**base, "findings": [finding]}, evidence, design, challenge).findings[0].classification == "observed"


def test_malformed_provider_content_keeps_raw_body(monkeypatch):
    import httpx
    import backend.coach as coach

    real_client = httpx.Client
    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "{bad-json"}}]})
    monkeypatch.setattr(coach.httpx, "Client", lambda: real_client(transport=httpx.MockTransport(handler)))
    monkeypatch.setenv("AISD_AI_BASE_URL", "http://127.0.0.1:9999")
    monkeypatch.setenv("AISD_AI_MODEL", "test")
    monkeypatch.setenv("AISD_AI_API_KEY", "secret")
    with pytest.raises(coach.ProviderOutputError) as failure:
        request_review(load_challenge("product-catalogue"), load_fixture("product-catalogue", "reference"), [], {})
    assert failure.value.raw_response == "{bad-json"
