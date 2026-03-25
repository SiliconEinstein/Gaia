"""Tests for BeliefState model."""

from datetime import datetime, timezone

import pytest

from gaia.libs.models.belief_state import BeliefState


class TestBeliefStateCreation:
    def test_basic_creation(self):
        bs = BeliefState(
            bp_run_id="run_001",
            resolution_policy="latest",
            prior_cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            beliefs={"gcn_abc": 0.9, "gcn_def": 0.3},
            converged=True,
            iterations=10,
            max_residual=0.001,
        )
        assert bs.bp_run_id == "run_001"
        assert bs.resolution_policy == "latest"
        assert bs.converged is True
        assert bs.iterations == 10
        assert bs.max_residual == 0.001
        assert bs.beliefs["gcn_abc"] == pytest.approx(0.9)

    def test_created_at_defaults_to_utc_now(self):
        before = datetime.now(timezone.utc)
        bs = BeliefState(
            bp_run_id="run_002",
            resolution_policy="latest",
            prior_cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            beliefs={},
            converged=False,
            iterations=0,
            max_residual=0.0,
        )
        after = datetime.now(timezone.utc)
        assert before <= bs.created_at <= after

    def test_source_resolution_policy(self):
        bs = BeliefState(
            bp_run_id="run_003",
            resolution_policy="source:pkg_xyz",
            prior_cutoff=datetime(2024, 6, 1, tzinfo=timezone.utc),
            beliefs={"gcn_claim1": 0.75},
            converged=True,
            iterations=5,
            max_residual=0.0005,
        )
        assert bs.resolution_policy == "source:pkg_xyz"

    def test_empty_beliefs(self):
        bs = BeliefState(
            bp_run_id="run_empty",
            resolution_policy="latest",
            prior_cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            beliefs={},
            converged=True,
            iterations=0,
            max_residual=0.0,
        )
        assert bs.beliefs == {}

    def test_unconverged_belief_state_is_valid(self):
        """Unconverged BeliefState is still valid — marked as approximate."""
        bs = BeliefState(
            bp_run_id="run_unconverged",
            resolution_policy="latest",
            prior_cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            beliefs={"gcn_x": 0.5},
            converged=False,
            iterations=100,
            max_residual=0.05,
        )
        assert bs.converged is False
        assert bs.iterations == 100
        assert bs.max_residual == pytest.approx(0.05)


class TestBeliefStateSerialization:
    def test_roundtrip_model_dump(self):
        bs = BeliefState(
            bp_run_id="run_rt",
            resolution_policy="latest",
            prior_cutoff=datetime(2024, 3, 15, 12, 0, 0, tzinfo=timezone.utc),
            beliefs={"gcn_a": 0.8, "gcn_b": 0.2},
            converged=True,
            iterations=20,
            max_residual=0.0001,
        )
        data = bs.model_dump()
        restored = BeliefState.model_validate(data)
        assert restored.bp_run_id == bs.bp_run_id
        assert restored.resolution_policy == bs.resolution_policy
        assert restored.beliefs == bs.beliefs
        assert restored.converged == bs.converged
        assert restored.iterations == bs.iterations
        assert restored.max_residual == pytest.approx(bs.max_residual)

    def test_json_roundtrip(self):
        bs = BeliefState(
            bp_run_id="run_json",
            resolution_policy="source:src_abc",
            prior_cutoff=datetime(2024, 3, 15, tzinfo=timezone.utc),
            beliefs={"gcn_claim_x": 0.95},
            converged=True,
            iterations=15,
            max_residual=0.00001,
        )
        json_str = bs.model_dump_json()
        restored = BeliefState.model_validate_json(json_str)
        assert restored.bp_run_id == bs.bp_run_id
        assert restored.beliefs == bs.beliefs
        assert restored.prior_cutoff == bs.prior_cutoff

    def test_beliefs_only_claim_keys_by_convention(self):
        """beliefs dict only maps gcn_ IDs (only claim nodes carry beliefs per spec)."""
        bs = BeliefState(
            bp_run_id="run_claims_only",
            resolution_policy="latest",
            prior_cutoff=datetime(2024, 1, 1, tzinfo=timezone.utc),
            beliefs={"gcn_claim1": 0.7, "gcn_claim2": 0.4},
            converged=True,
            iterations=8,
            max_residual=0.002,
        )
        assert all(k.startswith("gcn_") for k in bs.beliefs)
