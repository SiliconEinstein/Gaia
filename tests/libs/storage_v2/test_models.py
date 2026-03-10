"""Tests for storage_v2 Pydantic models — validates fixture data and model behaviors."""

import json
from pathlib import Path

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    ChainStep,
    Closure,
    ClosureEmbedding,
    ClosureRef,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredClosure,
    Subgraph,
)


def load_fixture(name: str) -> list[dict]:
    path = Path(__file__).parents[2] / "fixtures" / "storage_v2" / f"{name}.json"
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

    def test_closures_fixture(self):
        records = load_fixture("closures")
        closures = [Closure.model_validate(r) for r in records]
        assert len(closures) == 5

    def test_chains_fixture(self):
        records = load_fixture("chains")
        chains = [Chain.model_validate(r) for r in records]
        assert len(chains) == 2

    def test_probabilities_fixture(self):
        records = load_fixture("probabilities")
        probs = [ProbabilityRecord.model_validate(r) for r in records]
        assert len(probs) == 3

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


class TestClosureRef:
    def test_creation(self):
        ref = ClosureRef(
            closure_id="galileo_falling_bodies.reasoning.heavier_falls_faster", version=1
        )
        assert ref.closure_id == "galileo_falling_bodies.reasoning.heavier_falls_faster"
        assert ref.version == 1

    def test_equality(self):
        ref1 = ClosureRef(closure_id="a.b.c", version=1)
        ref2 = ClosureRef(closure_id="a.b.c", version=1)
        assert ref1 == ref2

    def test_version_difference(self):
        ref1 = ClosureRef(closure_id="a.b.c", version=1)
        ref2 = ClosureRef(closure_id="a.b.c", version=2)
        assert ref1 != ref2


class TestChainStep:
    def test_with_multiple_premises(self):
        step = ChainStep(
            step_index=0,
            premises=[
                ClosureRef(closure_id="a.b.premise1", version=1),
                ClosureRef(closure_id="a.b.premise2", version=1),
            ],
            reasoning="From premise1 and premise2 we deduce the conclusion.",
            conclusion=ClosureRef(closure_id="a.b.conclusion", version=1),
        )
        assert len(step.premises) == 2
        assert step.conclusion.closure_id == "a.b.conclusion"


class TestClosurePrior:
    def test_setting_allows_prior_one(self):
        """Settings may have prior=1.0 (certain context)."""
        closures = [Closure.model_validate(r) for r in load_fixture("closures")]
        setting = next(c for c in closures if c.type == "setting")
        assert setting.prior == 1.0

    def test_claim_has_fractional_prior(self):
        closures = [Closure.model_validate(r) for r in load_fixture("closures")]
        claim = next(c for c in closures if c.closure_id.endswith("heavier_falls_faster"))
        assert 0 < claim.prior < 1


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
    def test_scored_closure(self):
        closure_data = load_fixture("closures")[0]
        closure = Closure.model_validate(closure_data)
        scored = ScoredClosure(closure=closure, score=0.95)
        assert scored.score == 0.95
        assert scored.closure.closure_id == closure.closure_id

    def test_subgraph(self):
        sg = Subgraph(closure_ids={"a", "b"}, chain_ids={"c"})
        assert len(sg.closure_ids) == 2
        assert "c" in sg.chain_ids

    def test_subgraph_defaults_empty(self):
        sg = Subgraph()
        assert sg.closure_ids == set()
        assert sg.chain_ids == set()

    def test_closure_embedding(self):
        emb = ClosureEmbedding(closure_id="a.b.c", version=1, embedding=[0.1, 0.2, 0.3])
        assert len(emb.embedding) == 3
