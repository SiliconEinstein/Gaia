"""End-to-end integration test: ingest 3 packages → global BP → verify beliefs."""

import pytest

from gaia.libs.embedding import StubEmbeddingModel
from gaia.models import KnowledgeType
from gaia.models.parameterization import CROMWELL_EPS, ResolutionPolicy
from gaia.libs.storage.config import StorageConfig
from gaia.libs.storage.manager import StorageManager
from gaia.lkm.pipelines.run_global_bp import run_global_bp
from gaia.lkm.pipelines.run_ingest import run_ingest
from tests.gaia.fixtures.graphs import (
    make_einstein_equivalence,
    make_galileo_falling_bodies,
    make_newton_gravity,
)


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "e2e.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


@pytest.fixture
def embedding_model():
    return StubEmbeddingModel(dim=64)


class TestEndToEndPipeline:
    async def test_three_package_pipeline(self, storage, embedding_model):
        """Ingest galileo + newton + einstein → global BP → verify beliefs."""
        # Stage 1: Ingest all three packages
        packages = [
            ("galileo_falling_bodies", make_galileo_falling_bodies),
            ("newton_principia", make_newton_gravity),
            ("einstein_gravity", make_einstein_equivalence),
        ]
        all_results = []
        for pkg_id, builder in packages:
            graph, params = builder()
            result = await run_ingest(
                local_graph=graph,
                local_params=params,
                package_id=pkg_id,
                version="1.0",
                storage=storage,
                embedding_model=embedding_model,
            )
            all_results.append(result)
            assert len(result.bindings) > 0

        # Stage 2: Verify global graph state
        global_nodes = await storage.get_knowledge_nodes(prefix="gcn_")
        global_factors = await storage.get_factor_nodes(scope="global")
        assert len(global_nodes) > 0
        assert len(global_factors) > 0

        claim_nodes = [n for n in global_nodes if n.type == KnowledgeType.CLAIM]
        assert len(claim_nodes) > 0

        # Verify bindings exist for all packages
        for pkg_id, _ in packages:
            bindings = await storage.get_bindings(package_id=pkg_id)
            assert len(bindings) > 0

        # Verify prior records exist
        prior_records = await storage.get_prior_records()
        assert len(prior_records) > 0

        # Verify factor param records exist
        factor_records = await storage.get_factor_param_records()
        assert len(factor_records) > 0

        # Stage 3: Run global BP
        belief_state = await run_global_bp(
            storage=storage,
            policy=ResolutionPolicy(strategy="latest"),
        )

        # Stage 4: Verify belief state
        assert belief_state.converged
        assert belief_state.iterations > 0
        assert len(belief_state.beliefs) == len(claim_nodes)

        # All beliefs in Cromwell bounds
        for gcn_id, val in belief_state.beliefs.items():
            assert CROMWELL_EPS <= val <= 1.0 - CROMWELL_EPS, (
                f"Belief {val} for {gcn_id} outside Cromwell bounds"
            )

        # Verify belief state was persisted
        stored_states = await storage.get_belief_states(limit=1)
        assert len(stored_states) == 1
        assert stored_states[0].bp_run_id == belief_state.bp_run_id

        # Print summary for manual inspection
        print("\n=== E2E Pipeline Summary ===")
        print(f"Global nodes: {len(global_nodes)} ({len(claim_nodes)} claims)")
        print(f"Global factors: {len(global_factors)}")
        print(f"BP: converged={belief_state.converged}, iters={belief_state.iterations}")
        print(f"Beliefs: {len(belief_state.beliefs)} claims")
        for gcn_id, val in sorted(belief_state.beliefs.items(), key=lambda x: -x[1])[:5]:
            node = next((n for n in global_nodes if n.id == gcn_id), None)
            content = (node.content or "(ref)")[:60] if node else "?"
            print(f"  {val:.4f}  {content}")
