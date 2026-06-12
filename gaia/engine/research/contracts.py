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
from gaia.engine.research.proposal import (
    VALID_PROPOSAL_KINDS,
    VALID_PROPOSAL_PRIORITIES,
    VALID_PROPOSAL_STATUSES,
)


class ResearchContractError(ValueError):
    """Raised when an unknown research contract is requested."""


def field_map_contract(*, language: str = "zh") -> dict[str, Any]:
    """Return the JSON contract for autonomous review field-map induction."""
    return {
        "contract": "gaia.research.field_map",
        "schema_version": 1,
        "language": language,
        "purpose": (
            "Induce a review-oriented field map from primary search evidence before "
            "choosing narrow assessment focuses. Do not assume existing review papers "
            "are present in the corpus."
        ),
        "input": {
            "topic": "The user's original review or evidence-assessment topic.",
            "landscapes": "Breadth-first landscape artifacts built from live primary search.",
            "grounding": (
                "Use retrieved item ids, paper leads, query provenance, methods, "
                "models, observables, and controversy signals visible in the landscapes."
            ),
        },
        "output_required_fields": {
            "domain_thesis": "one-paragraph map of what the field is about",
            "buckets": "list[ReviewBucket]",
            "controversy_axes": "list[str]",
            "coverage_gaps": "list[CoverageGap]",
            "recommended_expansions": "list[str]",
            "synthesis_notes": "list[str]",
        },
        "bucket_fields": {
            "id": "stable snake/kebab identifier",
            "title": "reader-facing bucket title",
            "role": (
                "why this bucket matters for a review, e.g. historical backbone, "
                "numerical evidence, theory constraint, experiment, controversy"
            ),
            "required_for_review": "bool",
            "coverage_status": "covered, partial, thin, missing, or out_of_scope",
            "evidence_refs": "refs grounded in retrieved variables, papers, or queries",
            "recommended_queries": "list[str] to fill this bucket if coverage is thin",
        },
        "coverage_gap_fields": {
            "kind": "missing_bucket, thin_bucket, missing_method, missing_experiment, etc.",
            "description": "why the gap matters for a self-contained review",
            "recommended_queries": "list[str] that can be searched now",
        },
        "analysis_guidance": [
            (
                "Think like a review author: infer the field taxonomy before selecting "
                "narrow debates. The map should explain where later focuses fit."
            ),
            (
                "Do not rely on review articles being present. Use primary evidence "
                "signals to infer model families, methods, diagnostics, and disputes."
            ),
            (
                "Separate review-coverage gaps from scientific unknowns. A missing "
                "experimental bucket can drive more search; a need for new simulation "
                "belongs in later assessment limitations."
            ),
            (
                "Include buckets for historical/foundational theory, canonical models, "
                "numerical diagnostics, theoretical constraints, experimental systems, "
                "and recent controversies when the topic calls for them."
            ),
            "Keep recommended_expansions to the highest-value 2-5 live-search queries.",
        ],
        "example": {
            "domain_thesis": (
                "DQCP evidence spans canonical lattice simulations, emergent symmetry "
                "diagnostics, field-theory constraints, and experimental proximate systems."
            ),
            "buckets": [
                {
                    "id": "canonical_lattice_models",
                    "title": "Canonical lattice models",
                    "role": "historical and numerical backbone",
                    "required_for_review": True,
                    "coverage_status": "partial",
                    "evidence_refs": [{"kind": "query", "query_index": 0}],
                    "recommended_queries": ["square lattice J-Q scaling violations"],
                }
            ],
            "controversy_axes": ["continuous DQCP versus weak first-order transition"],
            "coverage_gaps": [
                {
                    "kind": "missing_experiment",
                    "description": "Experimental proximate DQCP systems are absent.",
                    "recommended_queries": ["SrCu2(BO3)2 proximate deconfined critical point"],
                }
            ],
            "recommended_expansions": ["SrCu2(BO3)2 proximate deconfined critical point"],
            "synthesis_notes": ["Assess focuses only after the coverage buckets are visible."],
        },
    }


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
                    "evidence_refs": [{"kind": "variable", "id": "aspree_result"}],
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
            "Classify grounded evidence relations for one focus and identify scientific "
            "limitations or next-search directions without writing stable Gaia source or "
            "final review prose."
        ),
        "forbidden_prose_terms": [
            "Gaia",
            "LKM",
            "item",
            "artifact",
            "evidence packet",
            "agent",
            "CLI",
            "trace",
            "run",
            "round",
            "workflow",
            "targeted expand",
            "source promotion",
            "assessment JSON",
        ],
        "input": {
            "focus": "A focus id, question, or obligation selected by the agent/user.",
            "evidence_packet": (
                "The combined items and paper leads from one or more landscape artifacts. "
                "Items are references to LKM variables, factors, papers, packages, or "
                "chains; they are not new knowledge entities and are not a ref namespace. "
                "Use stable refs whenever possible, especially source_refs like "
                "{kind: 'variable', id: items[*].id}. When an item includes package_ref, "
                "package_ref.ref is the Gaia package QID for the shallow source "
                "claim/question/note generated during Explore, and package_ref.value_type "
                "tells whether it can be used as a claim."
            ),
        },
        "output_required_fields": {
            "relations": "list[Relation]",
            "candidate_obligations": "list[CandidateObligation]",
        },
        "output_optional_fields": {
            "limitations": "list[str] scientific limitations that affect this focus",
            "next_queries": "list[str] targeted live-search queries for unresolved evidence gaps",
            "review": (
                "legacy optional object; do not produce it in the fixed workflow unless "
                "a caller explicitly asks for a standalone assessment artifact"
            ),
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
            "source_refs": (
                "non-empty refs grounded in variables, factors, chains, packages, "
                "package_ref values, papers, or the current focus"
            ),
            "claim_refs": (
                "optional list of concrete package claim refs used only when this relation "
                "should be scaffolded as candidate_relation(...). Use local bindings or "
                "foreign Gaia QIDs such as items[*].package_ref.ref; omit when the "
                "relation is only a prose assessment. Only use package_ref.ref when "
                "package_ref.value_type is 'claim'."
            ),
        },
        "limitation_fields": {
            "limitations": (
                "Scientific limitations only: method dependence, finite-size effects, "
                "shared datasets, incompatible observables, missing covariance, "
                "definition mismatch, or incomplete source coverage."
            ),
            "next_queries": (
                "Concrete query strings that would close material evidence gaps. Keep "
                "them focused on missing methods, systems, observables, or constraints."
            ),
        },
        "candidate_obligation_fields": {
            "kind": "needs_more_evidence, needs_method_check, needs_replication, or other",
            "content": "specific missing check that affects this focus",
            "source_refs": "optional grounding refs",
            "actionable": (
                "optional bool; set true only for a near-term blocking task that should "
                "be written as an open inquiry obligation. Omit or false means the item "
                "is retained as a deferred assessment gap."
            ),
        },
        "analysis_guidance": [
            "Separate benefit endpoints from harm endpoints.",
            "Distinguish support, opposition, qualification, and methodological undercutting.",
            "Discuss population, endpoint, trial-era, and background-therapy heterogeneity.",
            "Use absolute effects, NNT, and NNH when available.",
            "Write compact contract-shaped JSON; do not emit Markdown or prose outside "
            "the JSON object.",
            (
                "Do not write the final report, mini-review, abstract, introduction, "
                "or section prose. Later report phases write the article from these "
                "structured judgments."
            ),
            (
                "When a relation genuinely compares or links concrete package claims, "
                "set claim_refs to those package refs. Do not invent refs; use only "
                "local package bindings or package_ref.ref values visible in "
                "the evidence packet whose package_ref.value_type is 'claim'."
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
                    "source_refs": [{"kind": "variable", "id": "aspree_result"}],
                }
            ],
            "limitations": ["需要逐篇核对原始试验终点定义。"],
            "next_queries": ["aspirin primary prevention CAC net benefit"],
            "candidate_obligations": [
                {
                    "kind": "needs_more_evidence",
                    "content": "补充 CAC 分层下 NNT/NNH 的证据。",
                    "source_refs": [{"kind": "paper", "id": "P_ASPREE"}],
                    "actionable": False,
                }
            ],
        },
    }


def propose_contract(*, language: str = "zh") -> dict[str, Any]:
    """Return the JSON contract for LLM proposal synthesis output."""
    return {
        "contract": "gaia.research.proposal_analysis",
        "schema_version": 1,
        "language": language,
        "purpose": (
            "Transform an assessment artifact into open-ended next research proposals, "
            "hypotheses, and obligations. Proposals are not stable Gaia claims."
        ),
        "input": {
            "assessment": (
                "One .gaia/research/assessments/*.json artifact, including next_queries, "
                "candidate_obligations, relations, and any cited source refs."
            ),
            "grounding": (
                "Every proposal, hypothesis, and obligation should cite assessment, item, "
                "paper, variable, factor, or package refs visible in the assessment."
            ),
        },
        "output_required_fields": {
            "proposals": "list[Proposal]",
            "hypotheses": "list[Hypothesis]",
            "candidate_obligations": "list[CandidateObligation]",
            "notes": "list[str]",
        },
        "proposal_fields": {
            "id": "stable snake/kebab identifier local to the proposal artifact",
            "kind": sorted(VALID_PROPOSAL_KINDS),
            "status": sorted(VALID_PROPOSAL_STATUSES),
            "question": "open-ended question or action phrased for researchers",
            "rationale": "why this proposal follows from the assessment",
            "priority": sorted(VALID_PROPOSAL_PRIORITIES),
            "source_refs": "non-empty refs grounding the proposal in assessment evidence",
        },
        "hypothesis_fields": {
            "content": "tentative possibility to track in inquiry, not a stable claim",
            "source_refs": "optional grounding refs",
        },
        "candidate_obligation_fields": {
            "kind": "needs_more_evidence, needs_method_check, needs_replication, or other",
            "content": "what must be checked before the proposal can be assessed or promoted",
            "source_refs": "optional grounding refs",
        },
        "forbidden_outputs": [
            "Do not emit stable truth claims, claim(...), stable_claim, or fields named claims.",
            "Do not decide the answer to the research question; propose the next inquiry target.",
            "Do not invent source refs not present in the assessment.",
        ],
        "analysis_guidance": [
            "Prefer a small number of high-value open-ended questions over many narrow queries.",
            "Separate research questions from tentative hypotheses and audit obligations.",
            (
                "Use --accept only when the selected proposals are worth tracking "
                "as package questions."
            ),
            "Write Chinese user-facing prose when language is zh.",
        ],
        "example": {
            "proposals": [
                {
                    "id": "rq_calibration_systematics",
                    "kind": "research_question",
                    "status": "accepted",
                    "question": "TRGB 与 Cepheid 定标是否共享导致高 H0 的系统误差?",
                    "rationale": "assessment 将距离阶梯系统误差识别为核心未决方向。",
                    "priority": "high",
                    "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                }
            ],
            "hypotheses": [
                {
                    "content": "TRGB 与 SH0ES 可能共享部分定标系统误差。",
                    "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                }
            ],
            "candidate_obligations": [
                {
                    "kind": "needs_more_evidence",
                    "content": "核查 Cepheid/TRGB/SNIa 绝对星等传递的不确定度协方差。",
                    "source_refs": [{"kind": "assessment", "id": "h0_tension"}],
                }
            ],
            "notes": ["Accepted proposals should still be reviewed by a human before promotion."],
        },
    }


def research_contract(kind: str, *, language: str = "zh") -> dict[str, Any]:
    """Return one named research contract."""
    normalized = kind.strip().lower()
    if normalized in {"field_map", "field-map", "map", "review_map"}:
        return field_map_contract(language=language)
    if normalized in {"focus", "focuses", "focus_synthesis"}:
        return focus_contract(language=language)
    if normalized in {"assess", "assessment", "assessment_analysis"}:
        return assess_contract(language=language)
    if normalized in {"propose", "proposal", "proposal_analysis"}:
        return propose_contract(language=language)
    raise ResearchContractError("supported contracts are: field_map, focus, assess, propose")


__all__ = [
    "ResearchContractError",
    "assess_contract",
    "field_map_contract",
    "focus_contract",
    "propose_contract",
    "research_contract",
]
