import pytest

from backend.assessment import assess_suite
from backend.content import list_challenges, load_challenge, load_fixture
from backend.simulation import run_case
from backend.workloads import generate_case


@pytest.mark.parametrize("fixture,mode,verdict,outcomes", [
    ("initial", "assessment", "fail", ["fail", "fail", "pass"]),
    ("failure", "assessment", "fail", ["fail", "fail", "pass"]),
    ("reference", "assessment", "pass", ["pass", "pass", "pass"]),
    ("budget", "assessment", "fail", ["pass", "pass", "fail"]),
    ("initial", "preview", "incomplete", ["fail", "fail", "pass"]),
    ("reference", "preview", "incomplete", ["pass", "pass", "pass"]),
])
def test_walkthrough_teaches_capacity_without_skipping_budget(fixture, mode, verdict, outcomes):
    assert "first-design" in [c.challenge_id for c in list_challenges()]
    challenge = load_challenge("first-design")
    design = load_fixture(challenge.challenge_id, fixture)
    result = run_case(challenge, design, generate_case(challenge, "steady", 101, mode)).result

    assert result.execution_status == "completed"
    assert [r.status for r in result.requirement_outcomes] == outcomes
    assert assess_suite(challenge, [result], mode=mode).status == verdict
