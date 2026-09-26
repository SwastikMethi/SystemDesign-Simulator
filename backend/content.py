"""Load installed, versioned challenges and proposed design fixtures."""

import json
from pathlib import Path

from backend.contracts import AssessmentResult, CaseResult, Challenge, DesignRevision, JobOutcome, RequestOutcome

CONTENT = Path(__file__).resolve().parent.parent / "content"
CHALLENGE_IDS = ("team-notes", "url-shortener", "product-catalogue", "photo-delivery", "notifications", "first-design")


def load_challenge(challenge_id: str) -> Challenge:
    if challenge_id not in CHALLENGE_IDS:
        raise ValueError("unknown challenge")
    return Challenge.model_validate_json((CONTENT / "challenges" / f"{challenge_id}.json").read_text())


def list_challenges() -> list[Challenge]:
    return [load_challenge(challenge_id) for challenge_id in CHALLENGE_IDS]


def load_fixture(challenge_id: str, fixture_name: str) -> DesignRevision:
    if fixture_name not in {"initial", "reference", "failure", "budget"}:
        raise ValueError("unknown fixture")
    load_challenge(challenge_id)
    return DesignRevision.model_validate_json((CONTENT / "fixtures" / challenge_id / f"{fixture_name}.json").read_text())


def export_json_schemas(directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    for name, model in (("challenge", Challenge), ("design-revision", DesignRevision), ("request-outcome", RequestOutcome), ("job-outcome", JobOutcome), ("case-result", CaseResult), ("assessment-result", AssessmentResult)):
        (directory / f"{name}.schema.json").write_text(json.dumps(model.model_json_schema(), indent=2) + "\n")


if __name__ == "__main__":
    import sys

    export_json_schemas(Path(sys.argv[1] if len(sys.argv) > 1 else "content/schemas"))
