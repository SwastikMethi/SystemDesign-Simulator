import pytest

from backend.coach import render_review, validate_review
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
