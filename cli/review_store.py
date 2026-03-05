"""Local storage for review results."""

from datetime import datetime, timezone
from pathlib import Path

import yaml


def save_review(pkg_dir: Path, claim_id: int, result: dict, model: str, skill: str) -> None:
    """Save a review result to .gaia/reviews/{claim_id}.yaml."""
    review_dir = pkg_dir / ".gaia" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "target": {"claim_id": claim_id},
        "result": result,
        "provenance": {
            "method": "local",
            "model": model,
            "skill": f"claim-review-{skill}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }
    path = review_dir / f"{claim_id}.yaml"
    path.write_text(yaml.dump(record, allow_unicode=True, default_flow_style=False))


def load_review_scores(pkg_dir: Path) -> dict[int, float]:
    """Load all review scores. Returns {claim_id: score}."""
    review_dir = pkg_dir / ".gaia" / "reviews"
    if not review_dir.exists():
        return {}
    scores = {}
    for f in review_dir.glob("*.yaml"):
        data = yaml.safe_load(f.read_text())
        cid = data["target"]["claim_id"]
        scores[cid] = data["result"]["score"]
    return scores
