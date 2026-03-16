"""Tests for storage Pydantic models — validates fixture data and model behaviors."""

import json
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import ValidationError

from libs.storage.models import (
    BeliefSnapshot,
    CanonicalBinding,
    Chain,
    ChainStep,
    FactorNode,
    FactorParams,
    GlobalCanonicalNode,
    GlobalInferenceState,
    Knowledge,
    KnowledgeEmbedding,
    KnowledgeRef,
    LocalCanonicalRef,
    Module,
    Package,
    PackageRef,
    PackageSubmissionArtifact,
    Parameter,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredKnowledge,
    SourceRef,
    Subgraph,
)


def load_fixture(name: str) -> list[dict]:
    path = (
        Path(__file__).parents[2]
        / "fixtures"
        / "storage"
        / "gelileo_falling_bodies"
        / f"{name}.json"
    )
    return json.loads(path.read_text())


# ── Fixture validation tests ──


class TestFixtureValidation:
    """Load each fixture file and validate all records through the corresponding model."""

    def test_packages_fixture(self):
        records = load_fixture("packages")
        packages = [Package.model_validate(r) for r in records]
        assert len(packages) == 1
        assert packages[0].package_id == "galileo_falling_bodies"
        assert packages[0].status == "merged"

    def test_modules_fixture(self):
        records = load_fixture("modules")
        modules = [Module.model_validate(r) for r in records]
        assert len(modules) == 2
        names = {m.name for m in modules}
        assert names == {"setting", "reasoning"}

    def test_knowledge_fixture(self):
        records = load_fixture("knowledge")
        knowledge_items = [Knowledge.model_validate(r) for r in records]
        assert len(knowledge_items) == 6

    def test_chains_fixture(self):
        records = load_fixture("chains")
        chains = [Chain.model_validate(r) for r in records]
        assert len(chains) == 2

    def test_probabilities_fixture(self):
        records = load_fixture("probabilities")
        probs = [ProbabilityRecord.model_validate(r) for r in records]
        assert len(probs) == 4

    def test_beliefs_fixture(self):
        records = load_fixture("beliefs")
        beliefs = [BeliefSnapshot.model_validate(r) for r in records]
        assert len(beliefs) == 3

    def test_resources_fixture(self):
        records = load_fixture("resources")
        resources = [Resource.model_validate(r) for r in records]
        assert len(resources) == 1
        assert resources[0].type == "image"

    def test_attachments_fixture(self):
        records = load_fixture("attachments")
        attachments = [ResourceAttachment.model_validate(r) for r in records]
        assert len(attachments) == 2


# ── Model behavior tests ──


class TestKnowledgeRef:
    def test_creation(self):
        ref = KnowledgeRef(
            knowledge_id="galileo_falling_bodies.reasoning.heavier_falls_faster", version=1
        )
        assert ref.knowledge_id == "galileo_falling_bodies.reasoning.heavier_falls_faster"
        assert ref.version == 1

    def test_equality(self):
        ref1 = KnowledgeRef(knowledge_id="a.b.c", version=1)
        ref2 = KnowledgeRef(knowledge_id="a.b.c", version=1)
        assert ref1 == ref2

    def test_version_difference(self):
        ref1 = KnowledgeRef(knowledge_id="a.b.c", version=1)
        ref2 = KnowledgeRef(knowledge_id="a.b.c", version=2)
        assert ref1 != ref2


class TestChainStep:
    def test_with_multiple_premises(self):
        step = ChainStep(
            step_index=0,
            premises=[
                KnowledgeRef(knowledge_id="a.b.premise1", version=1),
                KnowledgeRef(knowledge_id="a.b.premise2", version=1),
            ],
            reasoning="From premise1 and premise2 we deduce the conclusion.",
            conclusion=KnowledgeRef(knowledge_id="a.b.conclusion", version=1),
        )
        assert len(step.premises) == 2
        assert step.conclusion.knowledge_id == "a.b.conclusion"


class TestKnowledgePrior:
    def test_setting_allows_prior_one(self):
        """Settings may have prior=1.0 (certain context)."""
        knowledge_items = [Knowledge.model_validate(r) for r in load_fixture("knowledge")]
        setting = next(c for c in knowledge_items if c.type == "setting")
        assert setting.prior == 1.0

    def test_claim_has_fractional_prior(self):
        knowledge_items = [Knowledge.model_validate(r) for r in load_fixture("knowledge")]
        claim = next(c for c in knowledge_items if c.knowledge_id.endswith("heavier_falls_faster"))
        assert 0 < claim.prior < 1

    @pytest.mark.parametrize("bad_prior", [0.0, -0.5, 1.7, 2.0])
    def test_prior_rejects_out_of_range(self, bad_prior):
        """prior must be in (0, 1]."""
        base = load_fixture("knowledge")[0]
        base["prior"] = bad_prior
        with pytest.raises(ValidationError):
            Knowledge.model_validate(base)


class TestProbabilityValidation:
    @pytest.mark.parametrize("bad_value", [0.0, -0.2, 1.5])
    def test_probability_rejects_out_of_range(self, bad_value):
        """value must be in (0, 1]."""
        base = load_fixture("probabilities")[0]
        base["value"] = bad_value
        with pytest.raises(ValidationError):
            ProbabilityRecord.model_validate(base)


class TestBeliefValidation:
    @pytest.mark.parametrize("bad_belief", [-0.1, 1.8, 2.0])
    def test_belief_rejects_out_of_range(self, bad_belief):
        """belief must be in [0, 1]."""
        base = load_fixture("beliefs")[0]
        base["belief"] = bad_belief
        with pytest.raises(ValidationError):
            BeliefSnapshot.model_validate(base)

    def test_belief_allows_zero(self):
        """belief=0.0 is valid (completely disbelieved)."""
        base = load_fixture("beliefs")[0]
        base["belief"] = 0.0
        snapshot = BeliefSnapshot.model_validate(base)
        assert snapshot.belief == 0.0


class TestResourceAttachmentCompositeKey:
    def test_chain_step_target_uses_composite_key(self):
        """chain_step target_id uses 'chain_id:step_index' format."""
        attachments = [ResourceAttachment.model_validate(r) for r in load_fixture("attachments")]
        step_attachment = next(a for a in attachments if a.target_type == "chain_step")
        assert ":" in step_attachment.target_id
        chain_id, step_index_str = step_attachment.target_id.rsplit(":", 1)
        assert chain_id == "galileo_falling_bodies.reasoning.contradiction_chain"
        assert step_index_str == "0"


class TestImportRef:
    def test_strong_import(self):
        modules = [Module.model_validate(r) for r in load_fixture("modules")]
        reasoning = next(m for m in modules if m.name == "reasoning")
        assert len(reasoning.imports) == 1
        assert reasoning.imports[0].strength == "strong"


class TestQueryModels:
    def test_scored_knowledge(self):
        knowledge_data = load_fixture("knowledge")[0]
        knowledge = Knowledge.model_validate(knowledge_data)
        scored = ScoredKnowledge(knowledge=knowledge, score=0.95)
        assert scored.score == 0.95
        assert scored.knowledge.knowledge_id == knowledge.knowledge_id

    def test_subgraph(self):
        sg = Subgraph(knowledge_ids={"a", "b"}, chain_ids={"c"})
        assert len(sg.knowledge_ids) == 2
        assert "c" in sg.chain_ids

    def test_subgraph_defaults_empty(self):
        sg = Subgraph()
        assert sg.knowledge_ids == set()
        assert sg.chain_ids == set()

    def test_knowledge_embedding(self):
        emb = KnowledgeEmbedding(knowledge_id="a.b.c", version=1, embedding=[0.1, 0.2, 0.3])
        assert len(emb.embedding) == 3


# ── Knowledge extensions (Task 1) ──


class TestKnowledgeExtensions:
    def test_knowledge_kind_field(self):
        k = Knowledge(
            knowledge_id="test/q1",
            version=1,
            type="question",
            kind="hypothesis",
            content="Is X true?",
            prior=0.5,
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime(2026, 1, 1),
        )
        assert k.kind == "hypothesis"

    def test_knowledge_kind_defaults_none(self):
        k = Knowledge(
            knowledge_id="test/c1",
            version=1,
            type="claim",
            content="X is true",
            prior=0.7,
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime(2026, 1, 1),
        )
        assert k.kind is None

    def test_knowledge_parameters_field(self):
        k = Knowledge(
            knowledge_id="test/schema1",
            version=1,
            type="claim",
            content="For all A: P(A)",
            prior=0.5,
            parameters=[Parameter(name="A", constraint="any substance")],
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime(2026, 1, 1),
        )
        assert len(k.parameters) == 1
        assert k.parameters[0].name == "A"
        assert k.is_schema is True

    def test_knowledge_is_schema_false_when_no_parameters(self):
        k = Knowledge(
            knowledge_id="test/ground1",
            version=1,
            type="claim",
            content="X is true",
            prior=0.7,
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime(2026, 1, 1),
        )
        assert k.is_schema is False

    def test_knowledge_contradiction_type(self):
        k = Knowledge(
            knowledge_id="test/contra1",
            version=1,
            type="contradiction",
            content="A contradicts B",
            prior=0.5,
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime(2026, 1, 1),
        )
        assert k.type == "contradiction"

    def test_knowledge_equivalence_type(self):
        k = Knowledge(
            knowledge_id="test/equiv1",
            version=1,
            type="equivalence",
            content="A is equivalent to B",
            prior=0.5,
            source_package_id="pkg",
            source_module_id="pkg.mod",
            created_at=datetime(2026, 1, 1),
        )
        assert k.type == "equivalence"


# ── FactorNode (Task 2) ──


class TestFactorNode:
    def test_factor_node_reasoning(self):
        f = FactorNode(
            factor_id="pkg.mod.chain1",
            type="reasoning",
            premises=["pkg/k1", "pkg/k2"],
            contexts=["pkg/k3"],
            conclusion="pkg/k4",
            package_id="pkg",
            source_ref=SourceRef(
                package="pkg", version="1.0.0", module="pkg.mod", knowledge_name="k4"
            ),
        )
        assert f.type == "reasoning"
        assert f.is_gate_factor is False
        assert set(f.bp_participant_ids) == {"pkg/k1", "pkg/k2", "pkg/k4"}

    def test_factor_node_mutex_constraint(self):
        f = FactorNode(
            factor_id="pkg.mutex.1",
            type="mutex_constraint",
            premises=["pkg/k1", "pkg/k2"],
            conclusion="pkg/contra1",
            package_id="pkg",
        )
        assert f.is_gate_factor is True
        assert f.bp_participant_ids == ["pkg/k1", "pkg/k2"]

    def test_factor_node_equiv_constraint(self):
        f = FactorNode(
            factor_id="pkg.equiv.1",
            type="equiv_constraint",
            premises=["pkg/k1", "pkg/k2"],
            conclusion="pkg/equiv1",
            package_id="pkg",
        )
        assert f.is_gate_factor is True

    def test_factor_node_instantiation(self):
        f = FactorNode(
            factor_id="pkg.inst.1",
            type="instantiation",
            premises=["pkg/schema1"],
            conclusion="pkg/ground1",
            package_id="pkg",
        )
        assert f.is_gate_factor is False
        assert set(f.bp_participant_ids) == {"pkg/schema1", "pkg/ground1"}


# ── Global Identity models (Task 3) ──


class TestGlobalIdentityModels:
    def test_canonical_binding(self):
        b = CanonicalBinding(
            package="pkg",
            version="1.0.0",
            local_graph_hash="sha256:abc123",
            local_canonical_id="pkg/lc_k1",
            decision="create_new",
            global_canonical_id="gcn_01ABC",
            decided_at=datetime(2026, 1, 1),
            decided_by="auto_matcher",
        )
        assert b.decision == "create_new"
        assert b.reason is None

    def test_global_canonical_node(self):
        node = GlobalCanonicalNode(
            global_canonical_id="gcn_01ABC",
            knowledge_type="claim",
            representative_content="X is true",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg", version="1.0.0", local_canonical_id="pkg/lc_k1"),
            ],
            provenance=[PackageRef(package="pkg", version="1.0.0")],
        )
        assert node.kind is None
        assert len(node.member_local_nodes) == 1
        assert node.parameters == []

    def test_global_inference_state(self):
        state = GlobalInferenceState(
            graph_hash="sha256:xyz",
            node_priors={"gcn_01": 0.7, "gcn_02": 0.5},
            factor_parameters={"f1": FactorParams(conditional_probability=0.9)},
            node_beliefs={"gcn_01": 0.8},
            updated_at=datetime(2026, 1, 1),
        )
        assert state.node_priors["gcn_01"] == 0.7
        assert state.factor_parameters["f1"].conditional_probability == 0.9

    def test_package_submission_artifact(self):
        art = PackageSubmissionArtifact(
            package_name="pkg",
            commit_hash="abc123def",
            source_files={"main.gaia": "knowledge { ... }"},
            raw_graph={"schema_version": "1.0", "knowledge_nodes": []},
            local_canonical_graph={"schema_version": "1.0", "knowledge_nodes": []},
            canonicalization_log=[
                {"local_canonical_id": "lc1", "members": ["r1"], "reason": "unique"}
            ],
            submitted_at=datetime(2026, 1, 1),
        )
        assert art.package_name == "pkg"
        assert len(art.source_files) == 1


def test_package_preparing_status():
    from datetime import datetime

    pkg = Package(
        package_id="test",
        name="test",
        version="1.0.0",
        modules=[],
        exports=[],
        submitter="tester",
        submitted_at=datetime(2026, 1, 1),
        status="preparing",
    )
    assert pkg.status == "preparing"
