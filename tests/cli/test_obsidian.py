"""Tests for Obsidian vault generation."""

from __future__ import annotations

from gaia.cli.commands._obsidian import generate_obsidian_vault


def _make_ir(knowledges=None, strategies=None, operators=None):
    """Build minimal IR dict for testing."""
    return {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": knowledges or [],
        "strategies": strategies or [],
        "operators": operators or [],
    }


# ---------------------------------------------------------------------------
# Page routing
# ---------------------------------------------------------------------------


class TestPageRouting:
    def test_exported_claim_gets_conclusion_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::main_claim",
                    "label": "main_claim",
                    "type": "claim",
                    "content": "Main finding.",
                    "module": "results",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "conclusions/main_claim.md" in pages

    def test_question_gets_conclusion_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::q1",
                    "label": "q1",
                    "type": "question",
                    "content": "Is X true?",
                    "module": "intro",
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "conclusions/q1.md" in pages

    def test_leaf_premise_gets_evidence_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::evidence_a",
                    "label": "evidence_a",
                    "type": "claim",
                    "content": "Observed data.",
                    "module": "results",
                },
                {
                    "id": "github:test_pkg::derived",
                    "label": "derived",
                    "type": "claim",
                    "content": "Conclusion.",
                    "module": "results",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::evidence_a"],
                    "conclusion": "github:test_pkg::derived",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert "evidence/evidence_a.md" in pages

    def test_non_exported_derived_claim_inlined_in_module(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::premise_a",
                    "label": "premise_a",
                    "type": "claim",
                    "content": "P.",
                    "module": "analysis",
                },
                {
                    "id": "github:test_pkg::intermediate",
                    "label": "intermediate",
                    "type": "claim",
                    "content": "I.",
                    "module": "analysis",
                    "exported": False,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::premise_a"],
                    "conclusion": "github:test_pkg::intermediate",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert "conclusions/intermediate.md" not in pages
        assert "modules/analysis.md" in pages
        assert "intermediate" in pages["modules/analysis.md"]

    def test_setting_inlined_in_module(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::bg",
                    "label": "bg",
                    "type": "setting",
                    "content": "Background.",
                    "module": "intro",
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "conclusions/bg.md" not in pages
        assert "evidence/bg.md" not in pages
        assert "modules/intro.md" in pages

    def test_helper_nodes_excluded(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::__helper",
                    "label": "__helper",
                    "type": "claim",
                    "content": "H.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::visible",
                    "label": "visible",
                    "type": "claim",
                    "content": "V.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        for path in pages:
            assert "__helper" not in path
        assert "__helper" not in pages.get("modules/m.md", "")


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestFrontmatter:
    def test_frontmatter_has_yaml_delimiters(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        page = pages["conclusions/c1.md"]
        assert page.startswith("---\n")
        assert "\n---\n" in page[4:]

    def test_beliefs_in_frontmatter(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        beliefs = {
            "beliefs": [{"knowledge_id": "github:test_pkg::c1", "belief": 0.85, "label": "c1"}]
        }
        params = {"priors": [{"knowledge_id": "github:test_pkg::c1", "value": 0.7}]}
        pages = generate_obsidian_vault(ir, beliefs_data=beliefs, param_data=params)
        page = pages["conclusions/c1.md"]
        assert "prior: 0.7" in page
        assert "belief: 0.85" in page

    def test_null_beliefs_without_inference(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        page = pages["conclusions/c1.md"]
        assert "prior: null" in page
        assert "belief: null" in page

    def test_module_frontmatter(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "results",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        mod_page = pages["modules/results.md"]
        assert "type: module" in mod_page
        assert "label: results" in mod_page


# ---------------------------------------------------------------------------
# Wikilinks
# ---------------------------------------------------------------------------


class TestWikilinks:
    def test_wikilinks_in_derivation(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::p1",
                    "label": "p1",
                    "type": "claim",
                    "content": "P.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::p1"],
                    "conclusion": "github:test_pkg::c1",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        page = pages["conclusions/c1.md"]
        assert "[[p1]]" in page

    def test_module_link_in_claim_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "results",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "[[results]]" in pages["conclusions/c1.md"]


# ---------------------------------------------------------------------------
# Strategy pages
# ---------------------------------------------------------------------------


class TestStrategyPages:
    def test_complex_strategy_gets_own_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::p1",
                    "label": "p1",
                    "type": "claim",
                    "content": "P1.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::p2",
                    "label": "p2",
                    "type": "claim",
                    "content": "P2.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::p3",
                    "label": "p3",
                    "type": "claim",
                    "content": "P3.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_induction_s1",
                    "type": "induction",
                    "premises": [
                        "github:test_pkg::p1",
                        "github:test_pkg::p2",
                        "github:test_pkg::p3",
                    ],
                    "conclusion": "github:test_pkg::c1",
                    "reason": "Three independent observations...",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert any(p.startswith("reasoning/") for p in pages)
        # Strategy page should have conclusion wikilink
        strategy_page = [v for k, v in pages.items() if k.startswith("reasoning/")][0]
        assert "[[c1]]" in strategy_page

    def test_simple_strategy_no_own_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::p1",
                    "label": "p1",
                    "type": "claim",
                    "content": "P.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::p1"],
                    "conclusion": "github:test_pkg::c1",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert not any(p.startswith("reasoning/") for p in pages)


# ---------------------------------------------------------------------------
# Meta pages
# ---------------------------------------------------------------------------


class TestMetaPages:
    def test_beliefs_page_with_data(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        beliefs = {
            "beliefs": [{"knowledge_id": "github:test_pkg::c1", "belief": 0.85, "label": "c1"}]
        }
        params = {"priors": [{"knowledge_id": "github:test_pkg::c1", "value": 0.7}]}
        pages = generate_obsidian_vault(ir, beliefs_data=beliefs, param_data=params)
        assert "meta/beliefs.md" in pages
        assert "0.85" in pages["meta/beliefs.md"]
        assert "[[c1]]" in pages["meta/beliefs.md"]

    def test_no_beliefs_page_without_data(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "meta/beliefs.md" not in pages

    def test_holes_page(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::hole",
                    "label": "hole",
                    "type": "claim",
                    "content": "Evidence.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::hole"],
                    "conclusion": "github:test_pkg::c1",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert "meta/holes.md" in pages
        assert "[[hole]]" in pages["meta/holes.md"]


# ---------------------------------------------------------------------------
# Index and overview
# ---------------------------------------------------------------------------


class TestIndexAndOverview:
    def test_index_has_statistics(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
                {
                    "id": "github:test_pkg::s1",
                    "label": "s1",
                    "type": "setting",
                    "content": "S.",
                    "module": "m",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        index = pages["_index.md"]
        assert "## Statistics" in index
        assert "1 claims" in index
        assert "1 settings" in index

    def test_index_has_exported_conclusions(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "[[c1]]" in pages["_index.md"]

    def test_index_has_reading_path(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::a",
                    "label": "a",
                    "type": "claim",
                    "content": "A.",
                    "module": "intro",
                    "exported": True,
                },
                {
                    "id": "github:test_pkg::b",
                    "label": "b",
                    "type": "claim",
                    "content": "B.",
                    "module": "results",
                    "exported": True,
                },
            ]
        )
        ir["module_order"] = ["intro", "results"]
        pages = generate_obsidian_vault(ir)
        index = pages["_index.md"]
        assert "## Reading Path" in index
        assert "[[intro]] → [[results]]" in index

    def test_strategy_page_has_readable_name(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::p1",
                    "label": "p1",
                    "type": "claim",
                    "content": "P1.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::p2",
                    "label": "p2",
                    "type": "claim",
                    "content": "P2.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::p3",
                    "label": "p3",
                    "type": "claim",
                    "content": "P3.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_abc123",
                    "type": "induction",
                    "premises": [
                        "github:test_pkg::p1",
                        "github:test_pkg::p2",
                        "github:test_pkg::p3",
                    ],
                    "conclusion": "github:test_pkg::c1",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert "reasoning/induction_c1.md" in pages
        assert "reasoning/abc123.md" not in pages

    def test_overview_has_mermaid(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert "overview.md" in pages
        assert "```mermaid" in pages["overview.md"]

    def test_obsidian_config(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert ".obsidian/graph.json" in pages
        config = pages[".obsidian/graph.json"]
        assert "colorGroups" in config


# ---------------------------------------------------------------------------
# Structural guarantees
# ---------------------------------------------------------------------------


class TestStructural:
    def test_all_pages_are_strings(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::p1",
                    "label": "p1",
                    "type": "claim",
                    "content": "P.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::p1"],
                    "conclusion": "github:test_pkg::c1",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        for path, content in pages.items():
            assert isinstance(path, str), f"Path {path} is not a string"
            assert isinstance(content, str), f"Content for {path} is not a string"
            assert len(content) > 0, f"Page {path} is empty"

    def test_empty_ir_produces_minimal_vault(self):
        ir = _make_ir()
        pages = generate_obsidian_vault(ir)
        assert "_index.md" in pages
        assert "overview.md" in pages
        assert ".obsidian/graph.json" in pages


# ---------------------------------------------------------------------------
# Regression tests (Codex review findings)
# ---------------------------------------------------------------------------


class TestCodexRegressions:
    def test_overview_no_double_mermaid_fence(self):
        """P2: render_mermaid already returns fenced block — don't wrap again."""
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        overview = pages["overview.md"]
        # Should have exactly one opening fence
        assert overview.count("```mermaid") == 1

    def test_unlabeled_nodes_treated_as_helpers(self):
        """P2: Nodes with None/empty label should not create pages."""
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::_anon_op_1",
                    "label": None,
                    "type": "claim",
                    "content": "Helper.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::_anon_op_2",
                    "type": "claim",
                    "content": "Another helper.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::real",
                    "label": "real",
                    "type": "claim",
                    "content": "Real.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        # No page with empty path segment
        for path in pages:
            assert "/." not in path
            assert path != "evidence/.md"
            assert path != "conclusions/.md"

    def test_reason_from_metadata(self):
        """P2: Strategy reason lives in metadata.reason, not top-level reason."""
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::p1",
                    "label": "p1",
                    "type": "claim",
                    "content": "P.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::p1"],
                    "conclusion": "github:test_pkg::c1",
                    "metadata": {"reason": "Because X implies Y."},
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        page = pages["conclusions/c1.md"]
        assert "Because X implies Y." in page

    def test_root_module_count_correct(self):
        """P3: Nodes without module field should count under Root."""
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        index = pages["_index.md"]
        assert "| [[Root]] | 1 |" in index

    def test_no_beliefs_link_when_no_infer(self):
        """P3: _index.md should not link to meta/beliefs when beliefs are absent."""
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::c1",
                    "label": "c1",
                    "type": "claim",
                    "content": "C.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        index = pages["_index.md"]
        assert "[[meta/beliefs]]" not in index
