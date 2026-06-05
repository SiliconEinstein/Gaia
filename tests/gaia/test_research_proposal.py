"""Unit tests for research proposal artifacts."""

from __future__ import annotations

import pytest

from gaia.engine.research.proposal import (
    ProposalSchemaError,
    build_proposal_from_assessment,
    validate_proposal_artifact,
)


def _assessment() -> dict[str, object]:
    return {
        "kind": "assessment",
        "schema_version": 1,
        "focus": {"kind": "focus", "id": "h0_tension"},
        "relations": [],
        "candidate_obligations": [
            {
                "kind": "needs_more_evidence",
                "content": "Check whether TRGB and SH0ES share calibration systematics.",
                "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
            }
        ],
        "review": {
            "language": "zh",
            "depth": "review",
            "summary": "H0 张力仍需要区分系统误差和新物理。",
            "sections": [],
            "limitations": [],
            "next_queries": [
                "TRGB Cepheid calibration systematics H0 tension",
                "early dark energy BAO CMB H0 tension constraints",
            ],
        },
    }


def test_proposal_from_assessment_uses_review_next_queries_and_obligations() -> None:
    artifact = build_proposal_from_assessment(assessment=_assessment())

    assert artifact["kind"] == "research_proposal"
    assert artifact["source_assessment"]["focus_id"] == "h0_tension"
    assert [proposal["question"] for proposal in artifact["proposals"]] == [
        "TRGB Cepheid calibration systematics H0 tension",
        "early dark energy BAO CMB H0 tension constraints",
    ]
    assert artifact["candidate_obligations"][0]["content"] == (
        "Check whether TRGB and SH0ES share calibration systematics."
    )
    assert validate_proposal_artifact(artifact) is artifact


def test_proposal_rejects_stable_claim_payloads() -> None:
    artifact = build_proposal_from_assessment(
        assessment=_assessment(),
        analysis={
            "proposals": [
                {
                    "id": "bad_claim",
                    "kind": "claim",
                    "status": "accepted",
                    "question": "H0 tension is caused by early dark energy.",
                    "rationale": "This is a truth claim, not an open proposal.",
                    "priority": "high",
                    "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                }
            ],
            "hypotheses": [],
            "candidate_obligations": [],
            "notes": [],
        },
    )

    with pytest.raises(ProposalSchemaError, match="stable truth claims"):
        validate_proposal_artifact(artifact)
