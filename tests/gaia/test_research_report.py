"""Unit tests for research artifact Markdown reports."""

from __future__ import annotations

from gaia.engine.research.report import render_research_artifact_markdown


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


def test_report_renders_assessment_markdown() -> None:
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
                "figure_specs": [
                    {
                        "title": "阿司匹林一级预防的获益-风险矩阵",
                        "purpose": "展示不同风险人群中获益与出血风险的相对位置",
                        "visual_structure": "二维矩阵",
                        "data_needed": "心血管事件、主要出血、年龄和基线风险",
                        "takeaway": "高出血风险人群不宜常规使用",
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
    assert "## 要点" in markdown
    assert "老年人证据提示常规使用的净获益不足[1]。" in markdown
    assert "## 综述正文" in markdown
    assert "老年人净获益不足[1]。后续仍需风险分层。" in markdown
    assert "[1][1]" not in markdown
    assert "老年人证据" in markdown
    assert "ASPREE 指向无获益[1]。" in markdown
    assert "联合证据应合并引用[1-2]。" in markdown
    assert "系统误差来源[1]，而不是统计噪声。" in markdown
    assert "## 证据概览" in markdown
    assert "反对常规使用" in markdown
    assert "## 图表建议" in markdown
    assert "阿司匹林一级预防的获益-风险矩阵" in markdown
    assert "[variable:v1]" not in markdown
    assert "## 参考文献" in markdown
    assert "## Evidence Interpretation" not in markdown
    assert "| type | claim |" not in markdown
    assert "## Open Assessment Questions" not in markdown
    assert "| kind | content |" not in markdown
    assert "evidence packet" not in markdown
    assert "item(s)" not in markdown
    assert "paper lead(s)" not in markdown
    assert "item_ids" not in markdown
    assert "variable_ids" not in markdown
    assert "citation_1" not in markdown
    assert "P1" not in markdown
    assert markdown.index("## 参考文献") > markdown.index("## 后续研究问题")
    assert "[1] ASPREE trial. DOI: 10.1056/aspree." in markdown
    assert "[2] Does aspirin help? DOI 未提供。" in markdown
    assert "ASPREE trial" in markdown
    assert "10.1056/aspree" in markdown
