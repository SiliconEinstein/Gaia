"""Tests for manifest.json generator."""

from __future__ import annotations

import json

from gaia.cli.commands._manifest import generate_manifest


def test_manifest_has_required_fields():
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "motivation",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    exported = {"github:test_pkg::a"}
    wiki_pages = ["Home.md", "Module-motivation.md"]
    result = generate_manifest(ir, exported, wiki_pages, assets=["fig1.png"])
    data = json.loads(result)
    assert data["package_name"] == "test_pkg"
    assert "Home.md" in data["wiki_pages"]
    assert "motivation.md" in data["pages_sections"]
    assert "fig1.png" in data["assets"]
    assert "a" in str(data["exported_conclusions"])


def test_manifest_counts():
    """total_claims counts only claim-type knowledge nodes."""
    ir = {
        "package_name": "test_pkg",
        "namespace": "github",
        "knowledges": [
            {
                "id": "github:test_pkg::a",
                "label": "a",
                "type": "claim",
                "content": "A.",
                "module": "m",
            },
            {
                "id": "github:test_pkg::b",
                "label": "b",
                "type": "setting",
                "content": "B.",
                "module": "m",
            },
            {
                "id": "github:test_pkg::c",
                "label": "c",
                "type": "claim",
                "content": "C.",
                "module": "m",
            },
        ],
        "strategies": [],
        "operators": [],
    }
    data = json.loads(generate_manifest(ir, set(), ["Home.md"]))
    assert data["total_claims"] == 2


def test_manifest_generated_at_present():
    """generated_at field exists and is a non-empty string."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
    }
    data = json.loads(generate_manifest(ir, set(), []))
    assert isinstance(data["generated_at"], str)
    assert len(data["generated_at"]) > 0


def test_manifest_sections_from_modules():
    """pages_sections lists one entry per unique module."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [
            {"id": "a", "label": "a", "type": "claim", "content": ".", "module": "intro"},
            {"id": "b", "label": "b", "type": "claim", "content": ".", "module": "analysis"},
            {"id": "c", "label": "c", "type": "claim", "content": ".", "module": "intro"},
        ],
        "strategies": [],
        "operators": [],
    }
    data = json.loads(generate_manifest(ir, set(), []))
    assert "intro.md" in data["pages_sections"]
    assert "analysis.md" in data["pages_sections"]
    assert len(data["pages_sections"]) == 2


def test_manifest_explicit_sections_override():
    """When sections= is explicitly provided, it overrides module-derived sections."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [
            {"id": "a", "label": "a", "type": "claim", "content": ".", "module": "m"},
        ],
        "strategies": [],
        "operators": [],
    }
    data = json.loads(generate_manifest(ir, set(), [], sections=["custom_a.md", "custom_b.md"]))
    assert data["pages_sections"] == ["custom_a.md", "custom_b.md"]


def test_manifest_readme_placeholders():
    """readme_placeholders is a list."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [],
        "strategies": [],
        "operators": [],
    }
    data = json.loads(generate_manifest(ir, set(), []))
    assert isinstance(data["readme_placeholders"], list)


def test_manifest_helper_nodes_excluded_from_beliefs():
    """Helper nodes (label starts with __) are not counted in total_beliefs."""
    ir = {
        "package_name": "pkg",
        "namespace": "github",
        "knowledges": [
            {"id": "a", "label": "a", "type": "claim", "content": ".", "module": "m"},
            {"id": "h", "label": "__h", "type": "claim", "content": ".", "module": "m"},
        ],
        "strategies": [],
        "operators": [],
    }
    data = json.loads(generate_manifest(ir, set(), []))
    # total_beliefs counts non-helper knowledge nodes
    assert data["total_beliefs"] == 1
