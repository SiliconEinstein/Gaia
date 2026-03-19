"""Tests targeting coverage gaps in graph_ir modules.

Covers: serialize.py (round-trip save/load), adapter.py edge cases,
build.py missing branches, models.py uncovered lines.
"""

from pathlib import Path

import pytest

from libs.graph_ir import (
    build_raw_graph,
    build_singleton_local_graph,
    derive_local_parameterization,
)
from libs.graph_ir.adapter import (
    _display_label,
    _resolve_prefix,
    adapt_local_graph_to_factor_graph,
)
from libs.graph_ir.models import (
    CanonicalizationLogEntry,
    FactorNode,
    FactorParams,
    LocalCanonicalGraph,
    LocalCanonicalNode,
    LocalParameterization,
    RawGraph,
    RawKnowledgeNode,
    SourceRef,
)
from libs.graph_ir.serialize import (
    load_local_canonical_graph,
    load_local_parameterization,
    load_raw_graph,
    save_canonicalization_log,
    save_local_canonical_graph,
    save_local_parameterization,
    save_raw_graph,
)
from libs.lang.models import (
    Claim,
    Contradiction,
    Module,
    Package,
    RetractAction,
    Setting,
)
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"


# ═══════════════════════════════════════════════════════════════════════
# serialize.py — round-trip save/load tests
# ═══════════════════════════════════════════════════════════════════════


class TestSerialize:
    def test_save_and_load_raw_graph(self, tmp_path):
        raw = RawGraph(
            package="test_pkg",
            version="0.1.0",
            knowledge_nodes=[
                RawKnowledgeNode(
                    raw_node_id="raw_1",
                    knowledge_type="claim",
                    content="Test claim",
                    source_refs=[],
                )
            ],
            factor_nodes=[],
        )
        out_path = save_raw_graph(raw, tmp_path)
        assert out_path.exists()

        loaded = load_raw_graph(out_path)
        assert loaded.package == "test_pkg"
        assert len(loaded.knowledge_nodes) == 1
        assert loaded.knowledge_nodes[0].raw_node_id == "raw_1"

    def test_save_and_load_local_canonical_graph(self, tmp_path):
        lcg = LocalCanonicalGraph(
            package="test_pkg",
            version="0.1.0",
            knowledge_nodes=[
                LocalCanonicalNode(
                    local_canonical_id="lcn_abc",
                    package="test_pkg",
                    knowledge_type="claim",
                    representative_content="A claim",
                    member_raw_node_ids=["raw_1"],
                    source_refs=[],
                )
            ],
            factor_nodes=[],
        )
        out_path = save_local_canonical_graph(lcg, tmp_path)
        assert out_path.exists()

        loaded = load_local_canonical_graph(out_path)
        assert loaded.package == "test_pkg"
        assert loaded.knowledge_nodes[0].local_canonical_id == "lcn_abc"

    def test_save_and_load_local_parameterization(self, tmp_path):
        params = LocalParameterization(
            graph_hash="sha256:abc",
            node_priors={"lcn_abc": 0.8},
            factor_parameters={"f_1": FactorParams(conditional_probability=0.9)},
        )
        out_path = save_local_parameterization(params, tmp_path)
        assert out_path.exists()

        loaded = load_local_parameterization(out_path)
        assert loaded.graph_hash == "sha256:abc"
        assert loaded.node_priors["lcn_abc"] == 0.8

    def test_save_canonicalization_log(self, tmp_path):
        entries = [
            CanonicalizationLogEntry(
                local_canonical_id="lcn_abc",
                reason="singleton",
                members=["raw_1", "raw_2"],
            )
        ]
        out_path = save_canonicalization_log(entries, tmp_path)
        assert out_path.exists()
        assert out_path.name == "canonicalization_log.json"

        import json

        data = json.loads(out_path.read_text())
        assert len(data["canonicalization_log"]) == 1

    def test_save_creates_directories(self, tmp_path):
        nested = tmp_path / "deep" / "nested" / "dir"
        raw = RawGraph(package="pkg", version="0.1.0", knowledge_nodes=[], factor_nodes=[])
        out_path = save_raw_graph(raw, nested)
        assert out_path.exists()


# ═══════════════════════════════════════════════════════════════════════
# adapter.py — edge cases
# ═══════════════════════════════════════════════════════════════════════


def _make_lcg(*nodes_data):
    """Helper to build LocalCanonicalGraph with correct required fields."""
    nodes = []
    for lcn_id, content in nodes_data:
        nodes.append(
            LocalCanonicalNode(
                local_canonical_id=lcn_id,
                package="pkg",
                knowledge_type="claim",
                representative_content=content,
                member_raw_node_ids=[f"raw_{lcn_id}"],
                source_refs=[],
            )
        )
    return nodes


class TestAdapterEdgeCases:
    def test_display_label_empty_refs(self):
        assert _display_label([]) == "unknown"

    def test_display_label_with_ref(self):
        ref = SourceRef(package="pkg", version="0.1.0", module="mod", knowledge_name="claim_a")
        assert _display_label([ref]) == "mod.claim_a"

    def test_resolve_prefix_exact_match(self):
        assert _resolve_prefix("lcn_abc", ["lcn_abc", "lcn_def"], "test") == "lcn_abc"

    def test_resolve_prefix_ambiguous(self):
        with pytest.raises(ValueError, match="ambiguous"):
            _resolve_prefix("lcn_", ["lcn_abc", "lcn_def"], "test")

    def test_resolve_prefix_not_found(self):
        with pytest.raises(ValueError, match="unknown"):
            _resolve_prefix("xxx", ["lcn_abc"], "test")

    def test_adapter_hash_mismatch_raises(self):
        nodes = _make_lcg(("lcn_a", "A"))
        lcg = LocalCanonicalGraph(
            package="pkg", version="0.1.0", knowledge_nodes=nodes, factor_nodes=[]
        )
        params = LocalParameterization(
            graph_hash="wrong_hash",
            node_priors={"lcn_a": 0.8},
            factor_parameters={},
        )
        with pytest.raises(ValueError, match="graph_hash"):
            adapt_local_graph_to_factor_graph(lcg, params)

    def test_adapter_missing_node_prior_raises(self):
        nodes = _make_lcg(("lcn_a", "A"))
        lcg = LocalCanonicalGraph(
            package="pkg", version="0.1.0", knowledge_nodes=nodes, factor_nodes=[]
        )
        params = LocalParameterization(
            graph_hash=lcg.graph_hash(),
            node_priors={},
            factor_parameters={},
        )
        with pytest.raises(ValueError, match="Missing node prior"):
            adapt_local_graph_to_factor_graph(lcg, params)

    def test_adapter_missing_factor_params_raises(self):
        nodes = _make_lcg(("lcn_a", "A"), ("lcn_b", "B"))
        lcg = LocalCanonicalGraph(
            package="pkg",
            version="0.1.0",
            knowledge_nodes=nodes,
            factor_nodes=[
                FactorNode(
                    factor_id="f_1",
                    type="infer",
                    premises=["lcn_a"],
                    contexts=[],
                    conclusion="lcn_b",
                )
            ],
        )
        params = LocalParameterization(
            graph_hash=lcg.graph_hash(),
            node_priors={"lcn_a": 0.8, "lcn_b": 0.5},
            factor_parameters={},
        )
        with pytest.raises(ValueError, match="Missing factor parameters"):
            adapt_local_graph_to_factor_graph(lcg, params)

    def test_adapter_skips_ext_factors(self):
        nodes = _make_lcg(("lcn_a", "A"))
        lcg = LocalCanonicalGraph(
            package="pkg",
            version="0.1.0",
            knowledge_nodes=nodes,
            factor_nodes=[
                FactorNode(
                    factor_id="f_ext",
                    type="infer",
                    premises=["ext:other_pkg.claim"],
                    contexts=[],
                    conclusion="lcn_a",
                )
            ],
        )
        params = LocalParameterization(
            graph_hash=lcg.graph_hash(),
            node_priors={"lcn_a": 0.8},
            factor_parameters={},
        )
        adapted = adapt_local_graph_to_factor_graph(lcg, params)
        assert len(adapted.factor_graph.factors) == 0

    def test_adapter_handles_constraint_factors(self):
        """Contradiction/equivalence factors should produce no-conclusion factors."""
        nodes = _make_lcg(("lcn_a", "A"), ("lcn_b", "B"), ("lcn_gate", "gate"))
        lcg = LocalCanonicalGraph(
            package="pkg",
            version="0.1.0",
            knowledge_nodes=nodes,
            factor_nodes=[
                FactorNode(
                    factor_id="f_contra",
                    type="contradiction",
                    premises=["lcn_gate", "lcn_a", "lcn_b"],
                    contexts=[],
                    conclusion=None,
                )
            ],
        )
        params = LocalParameterization(
            graph_hash=lcg.graph_hash(),
            node_priors={"lcn_a": 0.8, "lcn_b": 0.8, "lcn_gate": 0.9},
            factor_parameters={},
        )
        adapted = adapt_local_graph_to_factor_graph(lcg, params)
        assert len(adapted.factor_graph.factors) == 1
        factor = adapted.factor_graph.factors[0]
        assert factor["edge_type"] == "contradiction"
        assert factor["conclusions"] == []


# ═══════════════════════════════════════════════════════════════════════
# build.py — missing branches
# ═══════════════════════════════════════════════════════════════════════


class TestBuildEdgeCases:
    def test_build_with_setting_type(self):
        pkg = Package(
            name="setting_pkg",
            version="0.1.0",
            loaded_modules=[
                Module(
                    type="setting_module",
                    name="env",
                    knowledge=[
                        Setting(name="vacuum", content="In a vacuum environment"),
                    ],
                    export=["vacuum"],
                )
            ],
        )
        pkg = resolve_refs(pkg)
        raw = build_raw_graph(pkg)
        setting_nodes = [n for n in raw.knowledge_nodes if n.knowledge_type == "setting"]
        assert len(setting_nodes) == 1
        assert setting_nodes[0].content == "In a vacuum environment"

    def test_build_with_contradiction(self):
        pkg = Package(
            name="contra_pkg",
            version="0.1.0",
            loaded_modules=[
                Module(
                    type="reasoning_module",
                    name="core",
                    knowledge=[
                        Claim(name="a", content="A is true", prior=0.8),
                        Claim(name="b", content="B is true", prior=0.8),
                        Contradiction(
                            name="a_vs_b",
                            between=["a", "b"],
                            content="A and B cannot both be true",
                        ),
                    ],
                    export=["a", "b", "a_vs_b"],
                )
            ],
        )
        pkg = resolve_refs(pkg)
        raw = build_raw_graph(pkg)
        mutex_factors = [f for f in raw.factor_nodes if f.type == "contradiction"]
        assert len(mutex_factors) == 1

    def test_build_with_retraction(self):
        """RetractAction is recorded as metadata annotation, not as a factor."""
        pkg = Package(
            name="retract_pkg",
            version="0.1.0",
            loaded_modules=[
                Module(
                    type="reasoning_module",
                    name="core",
                    knowledge=[
                        Claim(name="old_claim", content="Old claim", prior=0.8),
                        Claim(name="new_evidence", content="New evidence", prior=0.9),
                        RetractAction(
                            name="retract_old",
                            target="old_claim",
                            reason="new_evidence",
                            content="Retract old claim based on new evidence",
                        ),
                    ],
                    export=["old_claim", "new_evidence", "retract_old"],
                )
            ],
        )
        pkg = resolve_refs(pkg)
        raw = build_raw_graph(pkg)
        # RetractAction is an author intent annotation, not a BP factor
        # It should appear in raw_graph metadata
        assert raw.metadata is not None
        retraction_intents = raw.metadata.get("retraction_intents", [])
        assert len(retraction_intents) == 1
        assert retraction_intents[0]["target"] == "old_claim"
        assert retraction_intents[0]["reason"] == "new_evidence"

    def test_default_node_prior_contradiction_type(self):
        from libs.graph_ir.build import _default_node_prior

        assert _default_node_prior(None, "contradiction") == 0.5
        assert _default_node_prior(None, "equivalence") == 0.5
        assert _default_node_prior(None, "claim") == 1.0

    def test_chain_probability_no_steps(self):
        from libs.graph_ir.build import _chain_probability

        assert _chain_probability(None) == 1.0

    def test_dedupe_preserving_order(self):
        from libs.graph_ir.build import _dedupe_preserving_order

        assert _dedupe_preserving_order(["a", "b", "a", "c", "b"]) == ["a", "b", "c"]
        assert _dedupe_preserving_order([]) == []

    def test_galileo_full_pipeline(self):
        """Galileo fixture builds raw → local → params → adapter successfully."""
        from libs.lang.loader import load_package

        pkg = load_package(GALILEO_DIR)
        pkg = resolve_refs(pkg)
        raw = build_raw_graph(pkg)
        canon = build_singleton_local_graph(raw)
        params = derive_local_parameterization(pkg, canon.local_graph)
        adapted = adapt_local_graph_to_factor_graph(canon.local_graph, params)
        assert len(adapted.factor_graph.variables) > 0
        assert len(adapted.factor_graph.factors) > 0


# ═══════════════════════════════════════════════════════════════════════
# models.py — uncovered lines (canonical_json, graph_hash on RawGraph)
# ═══════════════════════════════════════════════════════════════════════


class TestModelsEdgeCases:
    def test_raw_graph_canonical_json(self):
        raw = RawGraph(package="pkg", version="0.1.0", knowledge_nodes=[], factor_nodes=[])
        json_str = raw.canonical_json()
        assert '"package": "pkg"' in json_str

    def test_raw_graph_hash(self):
        raw = RawGraph(package="pkg", version="0.1.0", knowledge_nodes=[], factor_nodes=[])
        h = raw.graph_hash()
        assert h.startswith("sha256:")

    def test_raw_graph_hash_deterministic(self):
        raw1 = RawGraph(package="pkg", version="0.1.0", knowledge_nodes=[], factor_nodes=[])
        raw2 = RawGraph(package="pkg", version="0.1.0", knowledge_nodes=[], factor_nodes=[])
        assert raw1.graph_hash() == raw2.graph_hash()
