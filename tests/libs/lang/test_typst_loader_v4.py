"""Tests for v4 Typst package loader (label-based DSL)."""

from pathlib import Path

import pytest

from libs.lang.typst_loader import load_typst_package_v4

FIXTURE = Path(__file__).parents[2] / "fixtures" / "ir" / "dark_energy_v4"


@pytest.fixture(scope="module")
def v4_data():
    return load_typst_package_v4(FIXTURE)


def test_v4_loader_extracts_nodes(v4_data):
    """All 10 local nodes extracted."""
    nodes = v4_data["nodes"]
    local_nodes = [n for n in nodes if not n.get("external")]
    # 2 settings + 1 question + 5 claims (2 obs + main + qft_vacuum + cross_validation) + 1 action + 1 relation
    assert len(local_nodes) == 10


def test_v4_loader_node_types(v4_data):
    """Node types are correctly extracted from supplement."""
    by_name = {n["name"]: n for n in v4_data["nodes"]}
    assert by_name["flat_universe"]["type"] == "setting"
    assert by_name["main_question"]["type"] == "question"
    assert by_name["sn_observation"]["type"] == "claim"
    assert by_name["mcmc_fit"]["type"] == "action"
    assert by_name["vacuum_catastrophe"]["type"] == "relation"


def test_v4_loader_kind_field(v4_data):
    """kind parameter is extracted for claims and actions."""
    by_name = {n["name"]: n for n in v4_data["nodes"]}
    assert by_name["sn_observation"]["kind"] == "observation"
    assert by_name["mcmc_fit"]["kind"] == "python"
    assert by_name["flat_universe"].get("kind") is None


def test_v4_loader_node_content(v4_data):
    """Node content is flattened to plain text."""
    by_name = {n["name"]: n for n in v4_data["nodes"]}
    assert "spatially flat" in by_name["flat_universe"]["content"]
    assert "supernovae" in by_name["sn_observation"]["content"]


def test_v4_loader_from_edges(v4_data):
    """from: parameter creates reasoning factors."""
    factors = v4_data["factors"]
    main_factor = next(f for f in factors if f["conclusion"] == "dark_energy_fraction")
    assert set(main_factor["premises"]) == {
        "sn_observation",
        "cmb_data",
        "flat_universe",
        "gr_valid",
    }


def test_v4_loader_relation_between(v4_data):
    """relation between: parameter creates constraint."""
    constraints = v4_data["constraints"]
    vac = next(c for c in constraints if c["name"] == "vacuum_catastrophe")
    assert vac["type"] == "contradiction"
    assert "dark_energy_fraction" in vac["between"]


def test_v4_loader_external_refs(v4_data):
    """gaia-bibliography entries are marked as external."""
    ext_nodes = [n for n in v4_data["nodes"] if n.get("external")]
    assert len(ext_nodes) >= 1
    ext = next(n for n in ext_nodes if n["name"] == "prior_cmb_analysis")
    assert ext["ext_package"] == "cmb-analysis"
    assert "CMB" in ext["content"]


def test_v4_loader_package_metadata(v4_data):
    """Package name and version come from typst.toml."""
    assert v4_data["package"] == "dark_energy"
    assert v4_data["version"] == "1.0.0"
    assert v4_data["dsl_version"] == "v4"
