"""Tests for Graph IR → Storage model converter."""

from __future__ import annotations

from libs.graph_ir.models import (
    FactorNode,
    LocalCanonicalGraph,
    LocalCanonicalNode,
    LocalParameterization,
    Parameter,
    SourceRef,
)
from libs.graph_ir.storage_converter import (
    GraphIRIngestData,
    _infer_module_role,
    _map_factor_type,
    convert_graph_ir_to_storage,
)


def _make_lcg(
    nodes: list[LocalCanonicalNode] | None = None,
    factors: list[FactorNode] | None = None,
    package: str = "test-pkg",
    version: str = "0.1.0",
) -> LocalCanonicalGraph:
    return LocalCanonicalGraph(
        package=package,
        version=version,
        knowledge_nodes=nodes or [],
        factor_nodes=factors or [],
    )


def _make_node(
    lcn_id: str,
    content: str = "Some claim.",
    knowledge_type: str = "claim",
    kind: str | None = None,
    module: str = "main",
    knowledge_name: str | None = None,
    package: str = "test-pkg",
    version: str = "0.1.0",
    parameters: list[Parameter] | None = None,
) -> LocalCanonicalNode:
    k_name = knowledge_name or lcn_id
    return LocalCanonicalNode(
        local_canonical_id=lcn_id,
        package=package,
        knowledge_type=knowledge_type,
        kind=kind,
        representative_content=content,
        parameters=parameters or [],
        source_refs=[
            SourceRef(
                package=package,
                version=version,
                module=module,
                knowledge_name=k_name,
            )
        ],
    )


def _make_params(
    node_priors: dict[str, float] | None = None,
    graph_hash: str = "sha256:abc",
) -> LocalParameterization:
    return LocalParameterization(
        graph_hash=graph_hash,
        node_priors=node_priors or {},
    )


class TestBasicConversion:
    """test_basic_conversion: 2 nodes, 1 factor, beliefs → verify all fields."""

    def test_basic_conversion(self):
        n1 = _make_node("lcn_A", content="Water boils at 100C", knowledge_name="boiling_point")
        n2 = _make_node("lcn_B", content="Steam is produced", knowledge_name="steam_production")
        factor = FactorNode(
            factor_id="f_001",
            type="reasoning",
            premises=["lcn_A"],
            conclusion="lcn_B",
        )
        lcg = _make_lcg(nodes=[n1, n2], factors=[factor])
        params = _make_params(node_priors={"lcn_A": 0.9, "lcn_B": 0.6})
        beliefs = {"lcn_A": 0.85, "lcn_B": 0.55}

        result = convert_graph_ir_to_storage(lcg, params, beliefs=beliefs)

        assert isinstance(result, GraphIRIngestData)

        # Package
        assert result.package.package_id == "test-pkg"
        assert result.package.version == "0.1.0"
        assert result.package.status == "preparing"

        # Knowledge items
        assert len(result.knowledge_items) == 2
        k_map = {k.knowledge_id: k for k in result.knowledge_items}
        assert "test-pkg/boiling_point" in k_map
        assert "test-pkg/steam_production" in k_map
        k1 = k_map["test-pkg/boiling_point"]
        assert k1.content == "Water boils at 100C"
        assert k1.type == "claim"
        assert k1.prior == 0.9
        assert k1.version == 1

        # Factors
        assert len(result.factors) == 1
        f = result.factors[0]
        assert f.factor_id == "f_001"
        assert f.type == "infer"  # "reasoning" mapped to "infer"
        assert f.premises == ["test-pkg/boiling_point"]
        assert f.conclusion == "test-pkg/steam_production"
        assert f.package_id == "test-pkg"

        # Beliefs
        assert len(result.belief_snapshots) == 2
        b_map = {b.knowledge_id: b for b in result.belief_snapshots}
        assert b_map["test-pkg/boiling_point"].belief == 0.85
        assert b_map["test-pkg/steam_production"].belief == 0.55

        # Chains generated from reasoning factors
        assert len(result.chains) == 1
        chain = result.chains[0]
        assert chain.type == "deduction"
        assert len(chain.steps) == 1
        assert chain.steps[0].premises[0].knowledge_id == "test-pkg/boiling_point"
        assert chain.steps[0].conclusion.knowledge_id == "test-pkg/steam_production"
        assert result.probabilities == []

        # Modules
        assert len(result.modules) >= 1


class TestKnowledgePriors:
    """test_knowledge_priors_from_parameterization: priors come from LocalParameterization."""

    def test_priors_from_parameterization(self):
        n1 = _make_node("lcn_X", knowledge_name="x_node")
        n2 = _make_node("lcn_Y", knowledge_name="y_node")
        lcg = _make_lcg(nodes=[n1, n2])
        params = _make_params(node_priors={"lcn_X": 0.3, "lcn_Y": 0.95})

        result = convert_graph_ir_to_storage(lcg, params)

        k_map = {k.knowledge_id: k for k in result.knowledge_items}
        assert k_map["test-pkg/x_node"].prior == 0.3
        assert k_map["test-pkg/y_node"].prior == 0.95

    def test_default_prior_when_missing(self):
        n1 = _make_node("lcn_Z", knowledge_name="z_node")
        lcg = _make_lcg(nodes=[n1])
        params = _make_params(node_priors={})  # no prior for lcn_Z

        result = convert_graph_ir_to_storage(lcg, params)

        k = result.knowledge_items[0]
        assert k.prior == 0.5  # default

    def test_observation_maps_to_claim_with_observation_kind(self):
        obs = _make_node(
            "lcn_obs",
            content="The apparatus recorded a signal.",
            knowledge_type="observation",
            knowledge_name="signal_observation",
        )
        lcg = _make_lcg(nodes=[obs])
        params = _make_params(node_priors={"lcn_obs": 0.4})

        result = convert_graph_ir_to_storage(lcg, params)

        stored = result.knowledge_items[0]
        assert stored.type == "claim"
        assert stored.kind == "observation"
        assert stored.prior == 0.4


class TestFactorTypeMapping:
    """test_factor_type_mapping: reasoning→infer, mutex_constraint→contradiction, etc."""

    def test_all_mappings(self):
        expected = {
            "reasoning": "infer",
            "infer": "infer",
            "abstraction": "abstraction",
            "instantiation": "instantiation",
            "mutex_constraint": "contradiction",
            "equiv_constraint": "equivalence",
            "contradiction": "contradiction",
            "equivalence": "equivalence",
        }
        for ir_type, storage_type in expected.items():
            assert _map_factor_type(ir_type) == storage_type

    def test_unknown_factor_defaults_to_infer(self):
        assert _map_factor_type("unknown_type") == "infer"

    def test_factor_type_in_conversion(self):
        n1 = _make_node("lcn_A", knowledge_name="a")
        n2 = _make_node("lcn_B", knowledge_name="b")
        factor = FactorNode(
            factor_id="f_mutex",
            type="mutex_constraint",
            premises=["lcn_A", "lcn_B"],
        )
        lcg = _make_lcg(nodes=[n1, n2], factors=[factor])
        params = _make_params(node_priors={"lcn_A": 0.5, "lcn_B": 0.5})

        result = convert_graph_ir_to_storage(lcg, params)

        assert result.factors[0].type == "contradiction"
        assert result.factors[0].conclusion is None


class TestModuleDiscovery:
    """test_module_discovery: modules discovered from source_refs."""

    def test_modules_from_source_refs(self):
        n1 = _make_node("lcn_1", module="analysis", knowledge_name="k1")
        n2 = _make_node("lcn_2", module="discussion", knowledge_name="k2")
        n3 = _make_node("lcn_3", module="analysis", knowledge_name="k3")
        lcg = _make_lcg(nodes=[n1, n2, n3])
        params = _make_params(node_priors={"lcn_1": 0.5, "lcn_2": 0.5, "lcn_3": 0.5})

        result = convert_graph_ir_to_storage(lcg, params)

        module_names = {m.name for m in result.modules}
        assert module_names == {"analysis", "discussion"}
        assert len(result.modules) == 2

        # Each module has correct module_id
        mod_ids = {m.module_id for m in result.modules}
        assert "test-pkg.analysis" in mod_ids
        assert "test-pkg.discussion" in mod_ids


class TestModuleRoleInference:
    """test_module_role_inference: setting module gets role 'setting', etc."""

    def test_setting_role(self):
        assert _infer_module_role("setting") == "setting"
        assert _infer_module_role("problem_setting") == "setting"

    def test_motivation_role(self):
        assert _infer_module_role("motivation") == "motivation"
        assert _infer_module_role("research_motivation") == "motivation"

    def test_follow_up_role(self):
        assert _infer_module_role("follow_up") == "follow_up_question"
        assert _infer_module_role("follow_up_questions") == "follow_up_question"

    def test_default_reasoning_role(self):
        assert _infer_module_role("analysis") == "reasoning"
        assert _infer_module_role("main") == "reasoning"

    def test_role_in_conversion(self):
        n1 = _make_node("lcn_1", module="setting", knowledge_name="k1")
        n2 = _make_node("lcn_2", module="motivation", knowledge_name="k2")
        n3 = _make_node("lcn_3", module="analysis", knowledge_name="k3")
        lcg = _make_lcg(nodes=[n1, n2, n3])
        params = _make_params(node_priors={"lcn_1": 0.5, "lcn_2": 0.5, "lcn_3": 0.5})

        result = convert_graph_ir_to_storage(lcg, params)

        role_map = {m.name: m.role for m in result.modules}
        assert role_map["setting"] == "setting"
        assert role_map["motivation"] == "motivation"
        assert role_map["analysis"] == "reasoning"


class TestBeliefsMappedToKnowledgeIds:
    """test_beliefs_mapped_to_knowledge_ids: beliefs keyed by lcn_id mapped to knowledge_id."""

    def test_belief_id_mapping(self):
        n1 = _make_node("lcn_alpha", knowledge_name="alpha")
        n2 = _make_node("lcn_beta", knowledge_name="beta")
        lcg = _make_lcg(nodes=[n1, n2])
        params = _make_params(node_priors={"lcn_alpha": 0.5, "lcn_beta": 0.5})
        beliefs = {"lcn_alpha": 0.7, "lcn_beta": 0.3}

        result = convert_graph_ir_to_storage(lcg, params, beliefs=beliefs, bp_run_id="test_run")

        b_map = {b.knowledge_id: b for b in result.belief_snapshots}
        assert "test-pkg/alpha" in b_map
        assert "test-pkg/beta" in b_map
        assert b_map["test-pkg/alpha"].belief == 0.7
        assert b_map["test-pkg/beta"].bp_run_id == "test_run"

    def test_unknown_belief_id_skipped(self):
        n1 = _make_node("lcn_1", knowledge_name="k1")
        lcg = _make_lcg(nodes=[n1])
        params = _make_params(node_priors={"lcn_1": 0.5})
        beliefs = {"lcn_1": 0.8, "lcn_nonexistent": 0.5}

        result = convert_graph_ir_to_storage(lcg, params, beliefs=beliefs)

        assert len(result.belief_snapshots) == 1
        assert result.belief_snapshots[0].knowledge_id == "test-pkg/k1"


class TestEmptyBeliefs:
    """test_empty_beliefs: None beliefs → empty belief_snapshots."""

    def test_none_beliefs(self):
        n1 = _make_node("lcn_1", knowledge_name="k1")
        lcg = _make_lcg(nodes=[n1])
        params = _make_params(node_priors={"lcn_1": 0.5})

        result = convert_graph_ir_to_storage(lcg, params, beliefs=None)

        assert result.belief_snapshots == []

    def test_empty_dict_beliefs(self):
        n1 = _make_node("lcn_1", knowledge_name="k1")
        lcg = _make_lcg(nodes=[n1])
        params = _make_params(node_priors={"lcn_1": 0.5})

        result = convert_graph_ir_to_storage(lcg, params, beliefs={})

        assert result.belief_snapshots == []
