"""Unit tests for research stop-criteria artifacts."""

from __future__ import annotations

from gaia.engine.research.stop import evaluate_research_stop


def _focus_artifact(*, readiness: str = "ready_for_assess", gaps: int = 0) -> dict[str, object]:
    return {
        "kind": "focus_synthesis",
        "focuses": [
            {
                "id": "focus_1",
                "readiness": readiness,
                "question": "核心问题？",
                "evidence_refs": [{"kind": "snippet", "id": "snippet_0"}],
            }
        ],
        "coverage_gaps": [
            {"kind": "missing_method", "description": "缺少方法分层。"} for _ in range(gaps)
        ],
    }


def _assessment(
    *,
    relation_types: list[str],
    obligations: int = 0,
) -> dict[str, object]:
    return {
        "kind": "assessment",
        "relations": [
            {
                "type": relation_type,
                "claim": f"{relation_type} claim",
                "rationale": "Grounded rationale.",
                "epistemic_status": "candidate",
                "promotion_hint": "none",
                "source_refs": [{"kind": "snippet", "id": "snippet_0"}],
            }
            for relation_type in relation_types
        ],
        "candidate_obligations": [
            {"kind": "needs_more_evidence", "content": f"obligation {index}"}
            for index in range(obligations)
        ],
    }


def _landscape(*paper_ids: str) -> dict[str, object]:
    return {
        "kind": "research_landscape",
        "paper_leads": [{"paper_id": paper_id} for paper_id in paper_ids],
    }


def test_stop_recommends_ready_for_human_review_when_evidence_is_sufficient() -> None:
    artifact = evaluate_research_stop(
        focus_artifact=_focus_artifact(),
        assessment=_assessment(relation_types=["supports", "opposes", "qualifies"]),
        landscapes=[_landscape("P1", "P2")],
        previous_landscapes=[_landscape("P0")],
    )

    assert artifact["kind"] == "research_stop"
    assert artifact["recommendation"] == "ready_for_human_review"
    assert artifact["should_stop"] is True
    assert artifact["dimensions"]["coverage"]["status"] == "sufficient"
    assert artifact["dimensions"]["relation_mix"]["status"] == "sufficient"


def test_stop_recommends_expand_focus_for_coverage_gap() -> None:
    artifact = evaluate_research_stop(
        focus_artifact=_focus_artifact(readiness="needs_expand", gaps=1),
        assessment=None,
        landscapes=[_landscape("P1", "P2")],
        previous_landscapes=[_landscape("P0")],
    )

    assert artifact["recommendation"] == "expand_focus"
    assert artifact["should_stop"] is False
    assert artifact["dimensions"]["coverage"]["status"] == "weak"


def test_stop_recommends_ready_for_assess_without_assessment() -> None:
    artifact = evaluate_research_stop(
        focus_artifact=_focus_artifact(),
        assessment=None,
        landscapes=[_landscape("P1", "P2")],
        previous_landscapes=[_landscape("P0")],
    )

    assert artifact["recommendation"] == "ready_for_assess"
    assert artifact["should_stop"] is True
    assert artifact["dimensions"]["coverage"]["status"] == "sufficient"


def test_stop_flags_low_query_novelty() -> None:
    artifact = evaluate_research_stop(
        focus_artifact=_focus_artifact(),
        assessment=_assessment(relation_types=["supports"], obligations=3),
        landscapes=[_landscape("P1", "P2")],
        previous_landscapes=[_landscape("P1", "P2", "P3")],
    )

    assert artifact["recommendation"] == "ready_for_human_review"
    assert artifact["dimensions"]["query_novelty"]["status"] == "weak"
    assert artifact["dimensions"]["unresolved_obligations"]["status"] == "weak"
    assert artifact["metrics"]["new_paper_lead_ratio"] == 0.0
