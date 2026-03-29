"""Tests for Graph IR models — KnowledgeNode, FactorNode, graph containers."""

import pytest
from pydantic import ValidationError

from gaia.models.graph_ir import (
    FactorCategory,
    FactorNode,
    FactorStage,
    GlobalCanonicalGraph,
    KnowledgeNode,
    KnowledgeType,
    LocalCanonicalGraph,
    LocalCanonicalRef,
    PackageRef,
    Parameter,
    ReasoningType,
    SourceRef,
    Step,
)


# ---------------------------------------------------------------------------
# KnowledgeNode tests
# ---------------------------------------------------------------------------


class TestKnowledgeNodeLocal:
    """Local knowledge node (lcn_ prefix, content-addressed)."""

    def test_claim_node_has_lcn_prefix(self):
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="Water boils at 100C",
            source_refs=[],
        )
        assert node.id.startswith("lcn_")

    def test_setting_node_creation(self):
        node = KnowledgeNode(
            type=KnowledgeType.SETTING,
            content="Background on superconductors",
            source_refs=[],
        )
        assert node.id.startswith("lcn_")
        assert node.type == KnowledgeType.SETTING

    def test_question_node_creation(self):
        node = KnowledgeNode(
            type=KnowledgeType.QUESTION,
            content="What causes high-Tc superconductivity?",
            source_refs=[],
        )
        assert node.id.startswith("lcn_")
        assert node.type == KnowledgeType.QUESTION

    def test_template_node_creation(self):
        node = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="falls_at_rate({x}, {medium})",
            parameters=[
                Parameter(name="x", type="str"),
                Parameter(name="medium", type="str"),
            ],
            source_refs=[],
        )
        assert node.id.startswith("lcn_")
        assert node.type == KnowledgeType.TEMPLATE
        assert len(node.parameters) == 2

    def test_id_determinism_same_content(self):
        """Same type + content + parameters -> same ID."""
        a = KnowledgeNode(type=KnowledgeType.CLAIM, content="X", source_refs=[])
        b = KnowledgeNode(type=KnowledgeType.CLAIM, content="X", source_refs=[])
        assert a.id == b.id

    def test_different_content_different_id(self):
        a = KnowledgeNode(type=KnowledgeType.CLAIM, content="X", source_refs=[])
        b = KnowledgeNode(type=KnowledgeType.CLAIM, content="Y", source_refs=[])
        assert a.id != b.id

    def test_different_type_different_id(self):
        a = KnowledgeNode(type=KnowledgeType.CLAIM, content="X", source_refs=[])
        b = KnowledgeNode(type=KnowledgeType.SETTING, content="X", source_refs=[])
        assert a.id != b.id

    def test_parameters_sorted_for_id(self):
        """Parameter order should not affect ID."""
        a = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="f({x},{y})",
            parameters=[Parameter(name="x", type="str"), Parameter(name="y", type="int")],
            source_refs=[],
        )
        b = KnowledgeNode(
            type=KnowledgeType.TEMPLATE,
            content="f({x},{y})",
            parameters=[Parameter(name="y", type="int"), Parameter(name="x", type="str")],
            source_refs=[],
        )
        assert a.id == b.id


class TestKnowledgeNodeGlobal:
    """Global knowledge node (gcn_ prefix, registry-allocated)."""

    def test_global_id_preserved(self):
        node = KnowledgeNode(
            id="gcn_abc123",
            type=KnowledgeType.CLAIM,
            content=None,
            source_refs=[],
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_xyz",
                package_id="pkg1",
                version="1.0",
            ),
            member_local_nodes=[
                LocalCanonicalRef(
                    local_canonical_id="lcn_xyz",
                    package_id="pkg1",
                    version="1.0",
                ),
            ],
        )
        assert node.id == "gcn_abc123"
        assert node.content is None
        assert node.representative_lcn is not None
        assert len(node.member_local_nodes) == 1


class TestKnowledgeNodeSerialization:
    def test_roundtrip(self):
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="Test claim",
            source_refs=[
                SourceRef(package="pkg1", version="1.0", module="mod1", knowledge_name="k1")
            ],
            metadata={"schema": "observation"},
            provenance=[PackageRef(package_id="pkg1", version="1.0")],
        )
        data = node.model_dump()
        restored = KnowledgeNode.model_validate(data)
        assert restored.id == node.id
        assert restored.content == node.content
        assert restored.type == node.type
        assert restored.metadata == node.metadata

    def test_json_roundtrip(self):
        node = KnowledgeNode(
            type=KnowledgeType.CLAIM,
            content="Test claim",
            source_refs=[],
        )
        json_str = node.model_dump_json()
        restored = KnowledgeNode.model_validate_json(json_str)
        assert restored.id == node.id


# ---------------------------------------------------------------------------
# FactorNode tests
# ---------------------------------------------------------------------------


class TestFactorNodeLocal:
    def test_local_factor_has_lcf_prefix(self):
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
        )
        assert factor.factor_id.startswith("lcf_")

    def test_local_factor_with_steps(self):
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="A implies B")],
            weak_points=["Assumes linearity"],
        )
        assert len(factor.steps) == 1
        assert len(factor.weak_points) == 1


class TestFactorNodeGlobal:
    def test_global_factor_has_gcf_prefix(self):
        factor = FactorNode(
            scope="global",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["gcn_a", "gcn_b"],
            conclusion="gcn_c",
        )
        assert factor.factor_id.startswith("gcf_")


class TestFactorNodeValidation:
    def test_candidate_infer_requires_reasoning_type(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=None,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_permanent_infer_requires_reasoning_type(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.PERMANENT,
                reasoning_type=None,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_candidate_infer_with_reasoning_type_ok(self):
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["lcn_a"],
            conclusion="lcn_b",
        )
        assert factor.reasoning_type == ReasoningType.ENTAILMENT

    def test_equivalent_requires_no_conclusion(self):
        """equivalent must have conclusion=None."""
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.EQUIVALENT,
            premises=["lcn_a", "lcn_b"],
            conclusion=None,
        )
        assert factor.conclusion is None

    def test_equivalent_requires_at_least_2_premises(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=ReasoningType.EQUIVALENT,
                premises=["lcn_a"],
                conclusion=None,
            )

    def test_contradict_requires_no_conclusion(self):
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.CANDIDATE,
            reasoning_type=ReasoningType.CONTRADICT,
            premises=["lcn_a", "lcn_b"],
            conclusion=None,
        )
        assert factor.conclusion is None

    def test_contradict_requires_at_least_2_premises(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=ReasoningType.CONTRADICT,
                premises=["lcn_a"],
                conclusion=None,
            )

    def test_bilateral_with_conclusion_rejected(self):
        """equivalent/contradict must not have a conclusion."""
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=ReasoningType.EQUIVALENT,
                premises=["lcn_a", "lcn_b"],
                conclusion="lcn_c",
            )


class TestToolcallProofConstraints:
    """toolcall/proof categories: reasoning_type=None, no candidate/permanent stage."""

    def test_toolcall_rejects_reasoning_type(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.TOOLCALL,
                stage=FactorStage.INITIAL,
                reasoning_type=ReasoningType.ENTAILMENT,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_proof_rejects_reasoning_type(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.PROOF,
                stage=FactorStage.INITIAL,
                reasoning_type=ReasoningType.ENTAILMENT,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_toolcall_rejects_candidate_stage(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.TOOLCALL,
                stage=FactorStage.CANDIDATE,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_proof_rejects_candidate_stage(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.PROOF,
                stage=FactorStage.CANDIDATE,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_toolcall_rejects_permanent_stage(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.TOOLCALL,
                stage=FactorStage.PERMANENT,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )

    def test_proof_rejects_permanent_stage(self):
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.PROOF,
                stage=FactorStage.PERMANENT,
                premises=["lcn_a"],
                conclusion="lcn_b",
            )


class TestSubgraphStageConstraint:
    """subgraph only allowed for permanent stage."""

    def test_subgraph_rejected_for_non_permanent(self):
        inner = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_x"],
            conclusion="lcn_y",
        )
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.INITIAL,
                premises=["lcn_a"],
                conclusion="lcn_b",
                subgraph=[inner],
            )

    def test_subgraph_rejected_for_candidate(self):
        inner = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_x"],
            conclusion="lcn_y",
        )
        with pytest.raises(ValidationError):
            FactorNode(
                scope="local",
                category=FactorCategory.INFER,
                stage=FactorStage.CANDIDATE,
                reasoning_type=ReasoningType.ENTAILMENT,
                premises=["lcn_a"],
                conclusion="lcn_b",
                subgraph=[inner],
            )

    def test_subgraph_allowed_for_permanent(self):
        inner = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_x"],
            conclusion="lcn_y",
        )
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["lcn_a"],
            conclusion="lcn_b",
            subgraph=[inner],
        )
        assert factor.subgraph is not None
        assert len(factor.subgraph) == 1


class TestFactorNodeDeterminism:
    def test_factor_id_deterministic(self):
        kwargs = dict(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_b", "lcn_a"],
            conclusion="lcn_c",
        )
        a = FactorNode(**kwargs)
        b = FactorNode(**kwargs)
        assert a.factor_id == b.factor_id

    def test_premise_order_irrelevant(self):
        a = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
        )
        b = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["lcn_b", "lcn_a"],
            conclusion="lcn_c",
        )
        assert a.factor_id == b.factor_id


class TestFactorNodeSerialization:
    def test_roundtrip(self):
        factor = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="Step 1", premises=["lcn_a"], conclusion="lcn_b")],
            weak_points=["Assumption X"],
            source_ref=SourceRef(package="pkg1", version="1.0"),
            metadata={"context": ["lcn_z"]},
        )
        data = factor.model_dump()
        restored = FactorNode.model_validate(data)
        assert restored.factor_id == factor.factor_id
        assert restored.scope == factor.scope
        assert restored.category == factor.category
        assert len(restored.steps) == 1

    def test_json_roundtrip(self):
        factor = FactorNode(
            scope="global",
            category=FactorCategory.TOOLCALL,
            stage=FactorStage.INITIAL,
            premises=["gcn_a"],
            conclusion="gcn_b",
        )
        json_str = factor.model_dump_json()
        restored = FactorNode.model_validate_json(json_str)
        assert restored.factor_id == factor.factor_id


# ---------------------------------------------------------------------------
# Graph container tests
# ---------------------------------------------------------------------------


class TestLocalCanonicalGraph:
    def test_creation_with_hash(self):
        kn = KnowledgeNode(type=KnowledgeType.CLAIM, content="A", source_refs=[])
        fn = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=[kn.id],
            conclusion=None,
        )
        graph = LocalCanonicalGraph(knowledge_nodes=[kn], factor_nodes=[fn])
        assert graph.scope == "local"
        assert graph.graph_hash.startswith("sha256:")
        assert len(graph.graph_hash) > len("sha256:")

    def test_hash_deterministic(self):
        kn = KnowledgeNode(type=KnowledgeType.CLAIM, content="A", source_refs=[])
        fn = FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=[kn.id],
            conclusion=None,
        )
        g1 = LocalCanonicalGraph(knowledge_nodes=[kn], factor_nodes=[fn])
        g2 = LocalCanonicalGraph(knowledge_nodes=[kn], factor_nodes=[fn])
        assert g1.graph_hash == g2.graph_hash


class TestGlobalCanonicalGraph:
    def test_creation(self):
        kn = KnowledgeNode(
            id="gcn_abc",
            type=KnowledgeType.CLAIM,
            content=None,
            source_refs=[],
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_xyz",
                package_id="pkg1",
                version="1.0",
            ),
        )
        fn = FactorNode(
            scope="global",
            category=FactorCategory.INFER,
            stage=FactorStage.INITIAL,
            premises=["gcn_abc"],
            conclusion=None,
        )
        graph = GlobalCanonicalGraph(knowledge_nodes=[kn], factor_nodes=[fn])
        assert graph.scope == "global"
        assert len(graph.knowledge_nodes) == 1
        assert len(graph.factor_nodes) == 1
