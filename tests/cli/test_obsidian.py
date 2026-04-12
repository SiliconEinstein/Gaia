"""Tests for Obsidian vault generation."""

from __future__ import annotations

from gaia.cli.commands._obsidian import generate_obsidian_vault


def _make_ir(knowledges=None, strategies=None, operators=None):
    return {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": knowledges or [],
        "strategies": strategies or [],
        "operators": operators or [],
    }


def _find_page(pages, prefix, substring):
    """Find a page path starting with prefix and containing substring."""
    for p in pages:
        if p.startswith(prefix) and substring in p:
            return p
    return None


# ---------------------------------------------------------------------------
# Page routing — all claims go to claims/
# ---------------------------------------------------------------------------


class TestPageRouting:
    def test_exported_claim_in_claims_dir(self):
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
        path = _find_page(pages, "claims/", "c1")
        assert path is not None

    def test_non_exported_claim_also_in_claims_dir(self):
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
        # Non-exported derived claim also gets its own page
        assert _find_page(pages, "claims/", "p1") is not None

    def test_setting_in_claims_dir(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::bg",
                    "label": "bg",
                    "type": "setting",
                    "content": "Background.",
                    "module": "m",
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        assert _find_page(pages, "claims/", "bg") is not None

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
        assert _find_page(pages, "claims/", "__helper") is None

    def test_no_conclusions_evidence_reasoning_dirs(self):
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
                    "type": "induction",
                    "premises": [
                        "github:test_pkg::p1",
                        "github:test_pkg::p1",
                        "github:test_pkg::p1",
                    ],
                    "conclusion": "github:test_pkg::c1",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        assert not any(p.startswith("conclusions/") for p in pages)
        assert not any(p.startswith("evidence/") for p in pages)
        assert not any(p.startswith("reasoning/") for p in pages)


# ---------------------------------------------------------------------------
# Numbering
# ---------------------------------------------------------------------------


class TestNumbering:
    def test_claims_numbered_by_topo_order(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::leaf",
                    "label": "leaf",
                    "type": "claim",
                    "content": "L.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::derived",
                    "label": "derived",
                    "type": "claim",
                    "content": "D.",
                    "module": "m",
                    "exported": True,
                },
            ],
            strategies=[
                {
                    "strategy_id": "lcs_s1",
                    "type": "noisy_and",
                    "premises": ["github:test_pkg::leaf"],
                    "conclusion": "github:test_pkg::derived",
                },
            ],
        )
        pages = generate_obsidian_vault(ir)
        leaf_path = _find_page(pages, "claims/", "leaf")
        derived_path = _find_page(pages, "claims/", "derived")
        # Leaf should have lower number than derived
        assert leaf_path < derived_path  # "01" < "02" lexicographically

    def test_claim_page_title_has_number(self):
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
        path = _find_page(pages, "claims/", "c1")
        page = pages[path]
        assert "# #01" in page

    def test_section_page_has_number(self):
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
        sec_pages = [p for p in pages if p.startswith("sections/")]
        assert len(sec_pages) > 0
        page = pages[sec_pages[0]]
        assert "# 01 -" in page


# ---------------------------------------------------------------------------
# Frontmatter
# ---------------------------------------------------------------------------


class TestFrontmatter:
    def test_frontmatter_has_aliases(self):
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
        path = _find_page(pages, "claims/", "c1")
        page = pages[path]
        assert "aliases: [c1]" in page

    def test_frontmatter_has_claim_number(self):
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
        path = _find_page(pages, "claims/", "c1")
        page = pages[path]
        assert "claim_number: 1" in page

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
        beliefs = {"beliefs": [{"knowledge_id": "github:test_pkg::c1", "belief": 0.85}]}
        params = {"priors": [{"knowledge_id": "github:test_pkg::c1", "value": 0.7}]}
        pages = generate_obsidian_vault(ir, beliefs_data=beliefs, param_data=params)
        path = _find_page(pages, "claims/", "c1")
        page = pages[path]
        assert "prior: 0.7" in page
        assert "belief: 0.85" in page

    def test_section_frontmatter(self):
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
        sec_pages = [p for p in pages if p.startswith("sections/")]
        assert len(sec_pages) > 0
        page = pages[sec_pages[0]]
        assert "type: section" in page


# ---------------------------------------------------------------------------
# Wikilinks
# ---------------------------------------------------------------------------


class TestWikilinks:
    def test_wikilinks_use_labels(self):
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
        path = _find_page(pages, "claims/", "c1")
        page = pages[path]
        assert "[[p1|" in page  # wikilink with numbered display

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
        path = _find_page(pages, "claims/", "c1")
        assert "[[results]]" in pages[path]

    def test_claim_ref_has_number(self):
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
        path = _find_page(pages, "claims/", "c1")
        page = pages[path]
        assert "[[p1|#01 p1]]" in page


# ---------------------------------------------------------------------------
# Index and overview
# ---------------------------------------------------------------------------


class TestIndexAndOverview:
    def test_index_has_claim_index_table(self):
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
        assert "## Claim Index" in index
        assert "[[c1]]" in index

    def test_index_has_sections_table(self):
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
        assert "## Sections" in pages["_index.md"]

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

    def test_no_beliefs_link_when_no_infer(self):
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
        assert "[[beliefs]]" not in pages["_index.md"]


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
        beliefs = {"beliefs": [{"knowledge_id": "github:test_pkg::c1", "belief": 0.85}]}
        params = {"priors": [{"knowledge_id": "github:test_pkg::c1", "value": 0.7}]}
        pages = generate_obsidian_vault(ir, beliefs_data=beliefs, param_data=params)
        assert "meta/beliefs.md" in pages
        assert "0.85" in pages["meta/beliefs.md"]

    def test_holes_page_lists_leaves(self):
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
        assert "[[hole]]" in pages["meta/holes.md"]


# ---------------------------------------------------------------------------
# Structural
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
            assert isinstance(content, str), f"{path} not string"
            assert len(content) > 0, f"{path} empty"

    def test_empty_ir_produces_minimal_vault(self):
        ir = _make_ir()
        pages = generate_obsidian_vault(ir)
        assert "_index.md" in pages
        assert "overview.md" in pages
        assert ".obsidian/graph.json" in pages

    def test_reason_from_metadata(self):
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
        path = _find_page(pages, "claims/", "c1")
        assert "Because X implies Y." in pages[path]

    def test_unlabeled_nodes_treated_as_helpers(self):
        ir = _make_ir(
            knowledges=[
                {
                    "id": "github:test_pkg::_anon_1",
                    "label": None,
                    "type": "claim",
                    "content": "H.",
                    "module": "m",
                },
                {
                    "id": "github:test_pkg::real",
                    "label": "real",
                    "type": "claim",
                    "content": "R.",
                    "module": "m",
                    "exported": True,
                },
            ]
        )
        pages = generate_obsidian_vault(ir)
        for path in pages:
            assert "_anon" not in path
