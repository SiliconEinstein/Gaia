"""Review skill input/output formatting and parsing."""

import re
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).parent.parent / "review-skills"


def load_skill_prompt(version: str = "v1.0") -> str:
    """Load the review skill prompt by version."""
    path = SKILL_DIR / f"claim-review-{version}.md"
    return path.read_text()


def format_review_input(claim: dict, all_claims: dict[int, dict]) -> str:
    """Format a claim into the standardized review input YAML."""
    premise_expanded = []
    for pid in claim.get("premise", []):
        p = all_claims.get(pid, {})
        premise_expanded.append({"id": pid, "content": p.get("content", "")})

    context_expanded = []
    for cid in claim.get("context", []):
        c = all_claims.get(cid, {})
        context_expanded.append({"id": cid, "content": c.get("content", "")})

    input_data = {
        "claim": {
            "id": claim["id"],
            "content": claim["content"],
            "type": claim.get("type", "deduction"),
            "why": claim.get("why", ""),
            "premise": premise_expanded,
            "context": context_expanded,
        }
    }
    return yaml.dump(input_data, allow_unicode=True, default_flow_style=False)


def parse_review_output(raw: str) -> dict:
    """Parse LLM review output YAML, stripping code fences if present."""
    cleaned = re.sub(r"^```(?:yaml)?\n?", "", raw.strip())
    cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    return yaml.safe_load(cleaned)
