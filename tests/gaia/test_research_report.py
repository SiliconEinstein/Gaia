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
                    "evidence_refs": [{"kind": "item", "id": "item_0"}],
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
    assert "item:item_0" in markdown


def test_report_renders_assessment_markdown() -> None:
    markdown = render_research_artifact_markdown(
        {
            "schema_version": 1,
            "kind": "assessment",
            "focus": {"kind": "focus", "id": "elderly_net_benefit"},
            "evidence_packet": {
                "items": [{"item_id": "item_0", "kind": "variable", "id": "v1"}],
                "paper_leads": [{"paper_id": "P1", "title": "ASPREE trial"}],
            },
            "citations": [
                {
                    "id": "citation_1",
                    "source_kind": "paper",
                    "paper_id": "P1",
                    "title": "ASPREE trial",
                    "doi": "10.1056/aspree",
                    "item_ids": ["item_0"],
                    "variable_ids": ["v1"],
                }
            ],
            "relations": [
                {
                    "type": "opposes",
                    "claim": "ASPREE 不支持老年人常规使用阿司匹林一级预防。",
                    "rationale": "无心血管获益且大出血增加。",
                    "epistemic_status": "candidate",
                    "promotion_hint": "none",
                    "source_refs": [{"kind": "item", "id": "item_0"}],
                }
            ],
            "review": {
                "language": "zh",
                "depth": "review",
                "summary": "老年人净获益不足。",
                "sections": [{"title": "老年人证据", "body": "ASPREE 指向无获益。"}],
                "limitations": ["需要核对原始终点。"],
                "next_queries": ["ASPREE absolute risk difference"],
            },
            "candidate_obligations": [
                {
                    "kind": "needs_more_evidence",
                    "content": "补充绝对风险差。",
                    "source_refs": [{"kind": "item", "id": "item_0"}],
                }
            ],
        }
    )

    assert "# Research Assessment" in markdown
    assert "elderly_net_benefit" in markdown
    assert "opposes: 1" in markdown
    assert "老年人净获益不足。" in markdown
    assert "老年人证据" in markdown
    assert "## Citations" in markdown
    assert "citation_1" in markdown
    assert "ASPREE trial" in markdown
    assert "10.1056/aspree" in markdown
    assert "item_0" in markdown
    assert "补充绝对风险差。" in markdown
