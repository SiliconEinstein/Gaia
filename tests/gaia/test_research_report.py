"""Unit tests for research artifact Markdown reports."""

from __future__ import annotations

from gaia.engine.research.report import (
    render_final_research_report_markdown,
    render_markdown_with_research_citations,
    render_research_artifact_markdown,
)


def test_report_renders_focus_synthesis_markdown() -> None:
    markdown = render_research_artifact_markdown(
        {
            "schema_version": 1,
            "kind": "focus_synthesis",
            "language": "zh",
            "focuses": [
                {
                    "id": "elderly_net_benefit",
                    "question": "老年人一级预防净获益是否为正？",
                    "priority": "high",
                    "readiness": "ready_for_assess",
                    "status": "candidate",
                    "rationale": "ASPREE 同时涉及无心血管获益和出血增加。",
                    "coverage": {"items": 4, "paper_leads": 2},
                    "evidence_refs": [{"kind": "variable", "id": "v1"}],
                    "suggested_queries": ["aspirin elderly bleeding"],
                }
            ],
            "coverage_gaps": [
                {
                    "kind": "missing_subgroup",
                    "description": "缺少 CAC 分层证据。",
                    "evidence_refs": [{"kind": "paper", "paper_id": "P1"}],
                }
            ],
            "notes": ["由 agent/LLM 聚类生成。"],
        }
    )

    assert "# Research Focus Synthesis" in markdown
    assert "elderly_net_benefit" in markdown
    assert "老年人一级预防净获益是否为正？" in markdown
    assert "missing_subgroup" in markdown
    assert "aspirin elderly bleeding" in markdown
    assert "variable:v1" in markdown


def test_report_renders_assessment_artifact_with_final_report_renderer() -> None:
    markdown = render_research_artifact_markdown(
        {
            "schema_version": 1,
            "kind": "assessment",
            "focus": {"kind": "focus", "id": "elderly_net_benefit"},
            "evidence_packet": {
                "items": [{"item_id": "v1", "kind": "variable", "id": "v1"}],
                "paper_leads": [{"paper_id": "P1", "title": "ASPREE trial"}],
            },
            "citations": [
                {
                    "id": "citation_1",
                    "source_kind": "paper",
                    "paper_id": "P1",
                    "title": "ASPREE trial",
                    "doi": "10.1056/aspree",
                    "item_ids": ["v1"],
                    "variable_ids": ["v1"],
                },
                {
                    "id": "citation_2",
                    "source_kind": "paper",
                    "paper_id": "P2",
                    "title": "Does aspirin help?",
                    "item_ids": ["v2"],
                    "variable_ids": ["v2"],
                },
            ],
            "relations": [
                {
                    "type": "opposes",
                    "claim": "ASPREE 不支持老年人常规使用阿司匹林一级预防。",
                    "rationale": "无心血管获益且大出血增加。",
                    "epistemic_status": "candidate",
                    "promotion_hint": "none",
                    "source_refs": [{"kind": "variable", "id": "v1"}],
                }
            ],
            "review": {
                "language": "zh",
                "depth": "review",
                "title": "阿司匹林一级预防的净获益",
                "abstract": "阿司匹林一级预防需要在心血管获益与出血风险之间权衡。",
                "key_points": [
                    "老年人证据提示常规使用的净获益不足。[variable:v1]",
                    "后续需要按风险分层比较绝对获益与危害。",
                ],
                "summary": "老年人净获益不足。[variable:v1][paper:P1] 后续仍需风险分层。",
                "sections": [
                    {
                        "title": "老年人证据",
                        "body": "ASPREE 指向无获益。[variable:v1]",
                    },
                    {
                        "title": "证据合并",
                        "body": (
                            "联合证据应合并引用。[paper:P2][variable:v1] "
                            "系统误差来源，[variable:v1] 而不是统计噪声。"
                        ),
                    },
                ],
                "evidence_table": [
                    {
                        "证据簇": "ASPREE",
                        "方向": "反对常规使用",
                        "主要限制": "需要核对绝对风险差",
                    }
                ],
                "limitations": ["需要核对原始终点。"],
                "next_queries": ["ASPREE absolute risk difference"],
            },
            "candidate_obligations": [
                {
                    "kind": "needs_more_evidence",
                    "content": "补充绝对风险差。",
                    "source_refs": [{"kind": "variable", "id": "v1"}],
                }
            ],
        }
    )

    assert "# 阿司匹林一级预防的净获益" in markdown
    assert "## 摘要" in markdown
    assert "阿司匹林一级预防需要在心血管获益与出血风险之间权衡。" in markdown
    assert "## 关键结论" in markdown
    assert "老年人证据提示常规使用的净获益不足[1]。" in markdown
    assert "老年人净获益不足[1]。后续仍需风险分层。" in markdown
    assert "[1][1]" not in markdown
    assert "老年人证据" in markdown
    assert "ASPREE 指向无获益[1]。" in markdown
    assert "联合证据应合并引用[1-2]。" in markdown
    assert "系统误差来源[1]，而不是统计噪声。" in markdown
    assert "## 证据概览" in markdown
    assert "反对常规使用" in markdown
    assert "[variable:v1]" not in markdown
    assert "## 参考文献" in markdown
    assert "## Evidence Interpretation" not in markdown
    assert "| type | claim |" not in markdown
    assert "## Open Assessment Questions" not in markdown
    assert "| kind | content |" not in markdown
    assert "evidence packet" not in markdown
    assert "item(s)" not in markdown


def test_report_citation_rendering_strips_unresolved_internal_refs() -> None:
    markdown = render_markdown_with_research_citations(
        "Known claim [variable:v1]. Unknown claim [variable:gcn_missing].",
        citations=[
            {
                "id": "citation_1",
                "source_kind": "paper",
                "paper_id": "P1",
                "title": "Known paper",
                "variable_ids": ["v1"],
            }
        ],
        language="en",
    )

    assert "Known claim [1]." in markdown
    assert "Unknown claim." in markdown
    assert "[variable:gcn_missing]" not in markdown
    assert "[1] Known paper. DOI unavailable." in markdown


def test_report_citation_rendering_preserves_markdown_block_breaks() -> None:
    markdown = render_markdown_with_research_citations(
        "# Title\n\n## Evidence\n\nKnown claim [variable:v1].\n\n"
        "## Limits\n\nUnknown claim [variable:gcn_missing].",
        citations=[
            {
                "id": "citation_1",
                "source_kind": "paper",
                "paper_id": "P1",
                "title": "Known paper",
                "variable_ids": ["v1"],
            }
        ],
        language="en",
    )

    assert "# Title\n\n## Evidence\n\nKnown claim [1]." in markdown
    assert "\n\n## Limits\n\nUnknown claim." in markdown
    assert "[variable:gcn_missing]" not in markdown
    assert "Title ## Evidence" not in markdown


def test_final_report_renders_academic_evidence_review_without_run_summary() -> None:
    markdown = render_final_research_report_markdown(
        focus_artifacts=[
            {
                "kind": "focus_synthesis",
                "focuses": [
                    {
                        "id": "elderly_net_benefit",
                        "question": "老年人一级预防净获益是否为正？",
                    }
                ],
            }
        ],
        assessments=[
            {
                "kind": "assessment",
                "focus": {"kind": "focus", "id": "elderly_net_benefit"},
                "citations": [
                    {
                        "id": "citation_1",
                        "source_kind": "paper",
                        "paper_id": "P1",
                        "title": "ASPREE trial",
                        "doi": "10.1056/aspree",
                        "item_ids": ["v1"],
                        "variable_ids": ["v1"],
                    }
                ],
                "relations": [
                    {
                        "type": "opposes",
                        "claim": "ASPREE 不支持老年人常规使用阿司匹林一级预防。[variable:v1]",
                        "rationale": "无心血管获益且大出血增加。[variable:v1]",
                        "epistemic_status": "candidate",
                        "promotion_hint": "none",
                        "source_refs": [{"kind": "variable", "id": "v1"}],
                    }
                ],
                "review": {
                    "language": "zh",
                    "depth": "review",
                    "title": "阿司匹林一级预防的循证评估",
                    "abstract": "老年人阿司匹林一级预防的核心问题是低绝对获益能否抵消出血危害。",
                    "key_points": ["ASPREE 使常规使用的净获益判断转向保守。[variable:v1]"],
                    "summary": "现有证据提示老年人常规一级预防净获益不足。[variable:v1]",
                    "sections": [
                        {
                            "title": "老年人证据",
                            "body": "ASPREE 指向无心血管获益并增加出血风险。[variable:v1]",
                        }
                    ],
                    "limitations": ["仍需按基线风险和出血风险分层解释绝对效应。"],
                    "next_queries": ["aspirin elderly absolute risk bleeding subgroup"],
                },
                "limitations": ["需要补充女性和糖尿病亚组的绝对风险差。"],
                "next_queries": ["aspirin primary prevention diabetes female subgroup"],
            }
        ],
    )

    assert markdown.startswith("# 阿司匹林一级预防的循证评估")
    assert "## 摘要" in markdown
    assert "## 关键结论" in markdown
    assert "## 证据分层与争议点" in markdown
    assert "## 参考文献" in markdown
    assert "stop recommendation" not in markdown
    assert "total tokens" not in markdown
    assert "trace" not in markdown
    assert "artifact" not in markdown
    assert "paper lead(s)" not in markdown
    assert "item_ids" not in markdown
    assert "variable_ids" not in markdown
    assert "citation_1" not in markdown
    assert "P1" not in markdown
    assert "需要补充女性和糖尿病亚组的绝对风险差。" in markdown
    assert "aspirin primary prevention diabetes female subgroup" in markdown
    assert markdown.index("## 参考文献") > markdown.index("## 后续研究问题")
    assert "[1] ASPREE trial. DOI: 10.1056/aspree." in markdown
    assert "ASPREE trial" in markdown
    assert "10.1056/aspree" in markdown
