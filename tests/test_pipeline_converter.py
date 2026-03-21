"""Tests for _convert_local_graph_to_storage() and _render_markdown_from_graph_data()."""

from pathlib import Path

import pytest

from libs.pipeline import (
    _convert_local_graph_to_storage,
    _render_markdown_from_graph_data,
    pipeline_build,
    pipeline_infer,
    pipeline_review,
)

GALILEO_V3 = (
    Path(__file__).parent / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies_v3"
)


# ── Shared fixture to avoid rebuilding the pipeline 9 times ──


@pytest.fixture(scope="module")
async def converter_data():
    """Build → review → infer → convert, returning V2IngestData + build for reuse."""
    build = await pipeline_build(GALILEO_V3)
    review = await pipeline_review(build, mock=True)
    infer = await pipeline_infer(build, review)
    data = _convert_local_graph_to_storage(build, review, infer.beliefs, infer.bp_run_id)
    return data, build


# ── 1. _convert_local_graph_to_storage tests ──


async def test_converter_knowledge_type_mapping(converter_data):
    data, _build = converter_data
    types = {k.type for k in data.knowledge_items}
    # observation → setting, claim stays claim
    assert "setting" in types
    assert "claim" in types


async def test_converter_knowledge_id_format(converter_data):
    data, _build = converter_data
    for k in data.knowledge_items:
        assert k.knowledge_id.startswith("galileo_falling_bodies/")
        assert "/" in k.knowledge_id


async def test_converter_knowledge_id_uses_package_name(converter_data):
    data, build = converter_data
    pkg = build.local_graph.package
    for k in data.knowledge_items:
        assert k.knowledge_id.startswith(f"{pkg}/"), f"Expected {pkg}/ prefix, got {k.knowledge_id}"


async def test_converter_no_duplicate_knowledge_ids(converter_data):
    data, _build = converter_data
    kids = [k.knowledge_id for k in data.knowledge_items]
    assert len(kids) == len(set(kids))


async def test_converter_chains_have_steps(converter_data):
    data, _build = converter_data
    assert len(data.chains) > 0
    for chain in data.chains:
        assert len(chain.steps) > 0
        assert chain.steps[0].conclusion is not None


async def test_converter_modules_have_chain_ids(converter_data):
    data, _build = converter_data
    total_chains = sum(len(m.chain_ids) for m in data.modules)
    assert total_chains > 0, "At least some modules should have chain_ids"


async def test_converter_priors_clamped(converter_data):
    data, _build = converter_data
    for k in data.knowledge_items:
        assert 0 < k.prior <= 1.0


async def test_converter_belief_snapshots_match_knowledge(converter_data):
    data, _build = converter_data
    kid_set = {k.knowledge_id for k in data.knowledge_items}
    for snap in data.belief_snapshots:
        assert snap.knowledge_id in kid_set


async def test_converter_probability_records(converter_data):
    data, _build = converter_data
    assert len(data.probabilities) > 0
    for p in data.probabilities:
        assert 0 < p.value <= 1.0


# ── 2. _render_markdown_from_graph_data tests ──


def test_render_markdown_has_package_header():
    graph_data = {
        "package": "test_pkg",
        "nodes": [{"name": "n1", "type": "claim", "content": "hello"}],
        "factors": [],
    }
    md = _render_markdown_from_graph_data(graph_data)
    assert "# Package: test_pkg" in md
    assert "### n1 [claim]" in md
    assert "> hello" in md


def test_render_markdown_includes_reasoning_factors():
    graph_data = {
        "package": "test_pkg",
        "nodes": [
            {"name": "a", "type": "setting", "content": "A"},
            {"name": "b", "type": "claim", "content": "B"},
        ],
        "factors": [
            {"type": "reasoning", "premise": ["a"], "conclusion": "b"},
        ],
    }
    md = _render_markdown_from_graph_data(graph_data)
    assert "### b [proof]" in md
    assert "**Premises:** a" in md


def test_render_markdown_skips_non_reasoning_factors():
    graph_data = {
        "package": "test_pkg",
        "nodes": [{"name": "x", "type": "claim", "content": "X"}],
        "factors": [
            {"type": "constraint", "between": ["x", "y"]},
        ],
    }
    md = _render_markdown_from_graph_data(graph_data)
    assert "[proof]" not in md
