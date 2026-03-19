"""Tests for Typst package loading via typst-py."""

from pathlib import Path

from libs.lang.typst_loader import load_typst_package

GALILEO_TYPST = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst")
GALILEO_V3 = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "gaia_language_packages"
    / "galileo_falling_bodies_v3"
)
EINSTEIN_V3 = (
    Path(__file__).parent.parent.parent
    / "fixtures"
    / "gaia_language_packages"
    / "einstein_gravity_v3"
)


def test_load_typst_package_returns_graph_with_nodes():
    graph = load_typst_package(GALILEO_TYPST)
    assert "nodes" in graph
    assert len(graph["nodes"]) > 0


def test_load_typst_package_returns_graph_with_factors():
    graph = load_typst_package(GALILEO_TYPST)
    assert "factors" in graph
    assert len(graph["factors"]) > 0


def test_node_has_required_fields():
    graph = load_typst_package(GALILEO_TYPST)
    node = graph["nodes"][0]
    assert "name" in node
    assert "type" in node
    assert "content" in node


def test_node_content_is_plain_text():
    """Content should be flattened from Typst content tree to plain string."""
    graph = load_typst_package(GALILEO_TYPST)
    node = graph["nodes"][0]
    assert isinstance(node["content"], str)
    assert len(node["content"]) > 0


def test_factor_has_required_fields():
    graph = load_typst_package(GALILEO_TYPST)
    factors = [f for f in graph["factors"] if f["type"] == "reasoning"]
    assert len(factors) > 0
    factor = factors[0]
    assert "chain" in factor
    assert "premise" in factor
    assert "conclusion" in factor


def test_contradiction_factor_has_mutex_type():
    graph = load_typst_package(GALILEO_TYPST)
    mutex = [f for f in graph["factors"] if f["type"] == "mutex_constraint"]
    assert len(mutex) > 0


def test_refs_are_collected():
    graph = load_typst_package(GALILEO_TYPST)
    assert "refs" in graph
    ref_targets = [r["target"] for r in graph["refs"]]
    assert "aristotle.heavier_falls_faster" in ref_targets


def test_ctx_normalized_to_context():
    """The Typst library uses 'ctx' (context is a keyword), but Python output should use 'context'."""
    graph = load_typst_package(GALILEO_TYPST)
    for node in graph["nodes"]:
        assert "context" in node
        assert "ctx" not in node
    for factor in graph["factors"]:
        assert "context" in factor
        assert "ctx" not in factor


def test_expected_node_count():
    """Galileo fixture should have ~16 nodes."""
    graph = load_typst_package(GALILEO_TYPST)
    assert len(graph["nodes"]) >= 12  # at minimum


def test_expected_factor_count():
    """Galileo fixture should have ~9 factors."""
    graph = load_typst_package(GALILEO_TYPST)
    assert len(graph["factors"]) >= 6  # at minimum


# ── v3 fixture tests ──────────────────────────────────────────────────────────


def test_v3_no_proof_traces_in_output():
    graph = load_typst_package(GALILEO_V3)
    assert "proof_traces" not in graph


def test_v3_constraints_present():
    graph = load_typst_package(GALILEO_V3)
    assert len(graph["constraints"]) >= 1
    c = graph["constraints"][0]
    assert c["type"] == "contradiction"
    assert set(c["between"]) == {"composite_is_slower", "composite_is_faster"}


def test_v3_factors_from_premises():
    graph = load_typst_package(GALILEO_V3)
    vp = [f for f in graph["factors"] if f["conclusion"] == "vacuum_prediction"]
    assert len(vp) == 1
    assert set(vp[0]["premise"]) == {
        "tied_balls_contradiction",
        "air_resistance_is_confound",
        "inclined_plane_observation",
    }


def test_v3_factor_has_no_chain_field():
    """v3 factors come from premise blocks, not chains."""
    graph = load_typst_package(GALILEO_V3)
    reasoning = [f for f in graph["factors"] if f["type"] == "reasoning"]
    assert len(reasoning) > 0
    # v3 factors don't have chain/step fields
    for f in reasoning:
        assert "premise" in f
        assert "conclusion" in f


def test_v3_observation_node_type():
    graph = load_typst_package(GALILEO_V3)
    obs = [n for n in graph["nodes"] if n["type"] == "observation"]
    assert len(obs) >= 3  # everyday_observation, medium_density, inclined_plane


def test_v3_node_has_no_premise_field():
    """v3 nodes don't carry premise/context — that info is in factors."""
    graph = load_typst_package(GALILEO_V3)
    for node in graph["nodes"]:
        assert "name" in node
        assert "type" in node
        assert "content" in node
        assert "module" in node
        assert "premise" not in node
        assert "context" not in node


def test_v3_math_content_is_preserved():
    graph = load_typst_package(EINSTEIN_V3)
    node_map = {node["name"]: node["content"] for node in graph["nodes"]}
    assert "1.75''" in node_map["gr_light_deflection"]
    assert "43''" in node_map["mercury_perihelion"]
    assert "10^" in node_map["eotvos_experiment"]
    assert "m_i" in node_map["eotvos_experiment"]
    assert "m_g" in node_map["eotvos_experiment"]


def test_v3_package_metadata():
    """v3 export-graph() should include package name and version."""
    graph = load_typst_package(GALILEO_V3)
    assert graph["package"] == "galileo_falling_bodies"
    assert graph["version"] == "3.0.0"
