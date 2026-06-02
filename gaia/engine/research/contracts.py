"""Agent-facing JSON contracts for package-native research actions."""

from __future__ import annotations

from typing import Any

from gaia.engine.research.assessment import (
    RELATION_PROMOTION_HINTS,
    VALID_RELATIONS,
)
from gaia.engine.research.focus import (
    VALID_FOCUS_PRIORITIES,
    VALID_FOCUS_READINESS,
    VALID_FOCUS_STATUSES,
)


class ResearchContractError(ValueError):
    """Raised when an unknown research contract is requested."""


def focus_contract(*, language: str = "zh") -> dict[str, Any]:
    """Return the JSON contract for LLM focus synthesis output."""
    return {
        "contract": "gaia.research.focus_synthesis",
        "schema_version": 1,
        "language": language,
        "purpose": (
            "Transform breadth-first landscape artifacts into assessment-ready research "
            "focuses without writing Gaia source."
        ),
        "input": {
            "landscapes": "One or more .gaia/research/landscapes/*.json artifacts.",
            "grounding": (
                "Use items, paper_leads, query_provenance, and coverage_map. "
                "Every focus must cite evidence_refs from these inputs."
            ),
        },
        "output_required_fields": {
            "focuses": "list[Focus]",
            "coverage_gaps": "list[CoverageGap]",
            "notes": "list[str]",
        },
        "focus_fields": {
            "id": "stable snake/kebab identifier local to the focus artifact",
            "kind": "use 'research_focus'",
            "status": sorted(VALID_FOCUS_STATUSES),
            "question": "user-facing question; write Chinese when language is zh",
            "rationale": "why this is an important assessment focus",
            "priority": sorted(VALID_FOCUS_PRIORITIES),
            "readiness": sorted(VALID_FOCUS_READINESS),
            "scope": "object describing population, endpoint, method, or theory dimensions",
            "coverage": "object summarizing available evidence and missing dimensions",
            "evidence_refs": (
                "non-empty list of refs; each ref has kind plus id, paper_id, or query_index"
            ),
            "suggested_queries": (
                "list[str] for targeted expand queries; Chinese or English accepted"
            ),
        },
        "coverage_gap_fields": {
            "kind": "short gap type, e.g. missing_population, missing_endpoint",
            "description": "Chinese/user-facing description of what is missing",
            "evidence_refs": "optional grounding refs showing why the gap was detected",
        },
        "analysis_guidance": [
            (
                "Start broad: cluster by query family, paper overlap, population, "
                "endpoint, and method."
            ),
            "Prefer 3-8 high-signal focuses over one focus per query.",
            "A good focus is assessable: it can receive support/opposition/qualification evidence.",
            "Do not select a focus only because one paper has high retrieval rank.",
            "Mark readiness as needs_expand when a focus is promising but coverage is thin.",
        ],
        "example": {
            "focuses": [
                {
                    "id": "elderly_net_benefit",
                    "kind": "research_focus",
                    "status": "candidate",
                    "question": (
                        "70岁及以上人群中, 阿司匹林一级预防的心血管获益是否被大出血风险抵消?"
                    ),
                    "rationale": (
                        "ASPREE/JPPP 相关证据同时涉及无心血管获益和出血增加, "
                        "是一级预防净获益的核心分层问题。"
                    ),
                    "priority": "high",
                    "readiness": "ready_for_assess",
                    "scope": {"population": "older adults", "endpoint": "net clinical benefit"},
                    "coverage": {"items": 8, "paper_leads": 3, "missing": []},
                    "evidence_refs": [{"kind": "item", "id": "item_12"}],
                    "suggested_queries": [],
                }
            ],
            "coverage_gaps": [],
            "notes": ["Focuses are candidates until accepted through Gaia inquiry."],
        },
    }


def assess_contract(*, language: str = "zh") -> dict[str, Any]:
    """Return the JSON contract for LLM assessment analysis output."""
    return {
        "contract": "gaia.research.assessment_analysis",
        "schema_version": 1,
        "language": language,
        "purpose": (
            "Classify grounded evidence relations for one focus and write a review-grade "
            "assessment without writing stable Gaia source."
        ),
        "input": {
            "focus": "A focus id, question, or obligation selected by the agent/user.",
            "evidence_packet": (
                "The combined items and paper leads from one or more landscape artifacts. "
                "Use item ids exactly as presented by the evidence packet. Items are "
                "artifact-local references to LKM variables, factors, papers, packages, "
                "or chains; they are not new knowledge entities."
            ),
        },
        "output_required_fields": {
            "relations": "list[Relation]",
            "review": "object containing Chinese/user-facing synthesis",
            "candidate_obligations": "list[CandidateObligation]",
        },
        "relation_fields": {
            "type": sorted(VALID_RELATIONS),
            "claim": (
                "atomic user-readable statement about how the source bears on the focus; "
                "write Chinese when language is zh"
            ),
            "rationale": (
                "user-readable explanation of why this source supports/opposes/qualifies/"
                "undercuts the focus"
            ),
            "epistemic_status": "candidate, provisional, or accepted",
            "promotion_hint": {
                relation_type: sorted(hints)
                for relation_type, hints in RELATION_PROMOTION_HINTS.items()
            },
            "source_refs": "non-empty refs grounded in items, variables, factors, or papers",
        },
        "review_fields": {
            "language": language,
            "depth": "review",
            "summary": "concise bottom-line answer",
            "sections": (
                "ordered list with title and body fields; body text may cite evidence "
                "with inline [item:item_N] refs that the report renderer maps to citations"
            ),
            "evidence_table": (
                "optional list summarizing trial/paper, population, endpoint, direction"
            ),
            "limitations": "list[str]",
            "next_queries": "list[str]",
        },
        "analysis_guidance": [
            "Separate benefit endpoints from harm endpoints.",
            "Distinguish support, opposition, qualification, and methodological undercutting.",
            "Discuss population, endpoint, trial-era, and background-therapy heterogeneity.",
            "Use absolute effects, NNT, and NNH when available.",
            "Write enough detail for a domain review, not a terse search summary.",
            (
                "In review.summary and review.sections[].body, cite important evidence "
                "with inline [item:item_N] markers; do not write paper citations manually."
            ),
            (
                "Relations and candidate_obligations remain structured artifacts, but "
                "Markdown reports rephrase them into readable sections; write claim, "
                "rationale, and content as complete review-quality sentences."
            ),
            "When evidence is insufficient, emit obligations instead of overclaiming.",
        ],
        "example": {
            "relations": [
                {
                    "type": "opposes",
                    "claim": (
                        "ASPREE does not support routine aspirin primary prevention "
                        "in healthy adults aged 70 or older."
                    ),
                    "rationale": (
                        "The referenced item reports no cardiovascular disease reduction "
                        "and increased major hemorrhage."
                    ),
                    "epistemic_status": "candidate",
                    "promotion_hint": "none",
                    "source_refs": [{"kind": "item", "id": "item_20"}],
                }
            ],
            "review": {
                "language": language,
                "depth": "review",
                "summary": "总体净获益有限, 老年人和中等风险人群尤其应谨慎。",
                "sections": [
                    {
                        "title": "老年人证据",
                        "body": "ASPREE 相关证据提示心血管获益不足以抵消大出血风险。[item:item_20]",
                    }
                ],
                "evidence_table": [],
                "limitations": ["需要逐篇核对原始试验终点定义。"],
                "next_queries": ["aspirin primary prevention CAC net benefit"],
            },
            "candidate_obligations": [
                {
                    "kind": "needs_more_evidence",
                    "content": "补充 CAC 分层下 NNT/NNH 的证据。",
                    "source_refs": [{"kind": "item", "id": "item_33"}],
                }
            ],
        },
    }


def research_contract(kind: str, *, language: str = "zh") -> dict[str, Any]:
    """Return one named research contract."""
    normalized = kind.strip().lower()
    if normalized in {"focus", "focuses", "focus_synthesis"}:
        return focus_contract(language=language)
    if normalized in {"assess", "assessment", "assessment_analysis"}:
        return assess_contract(language=language)
    raise ResearchContractError("supported contracts are: focus, assess")


__all__ = [
    "ResearchContractError",
    "assess_contract",
    "focus_contract",
    "research_contract",
]
