"""Tests for BeliefState data model."""

from datetime import datetime, timezone

from gaia.gaia_ir import BeliefState


class TestBeliefState:
    def test_creation(self):
        bs = BeliefState(
            bp_run_id="run_001",
            resolution_policy="latest",
            prior_cutoff=datetime(2026, 3, 29, tzinfo=timezone.utc),
            beliefs={"gcn_a": 0.82, "gcn_b": 0.71},
            converged=True,
            iterations=23,
            max_residual=4.2e-7,
        )
        assert bs.bp_run_id == "run_001"
        assert len(bs.beliefs) == 2
        assert bs.converged is True

    def test_auto_timestamp(self):
        bs = BeliefState(
            bp_run_id="run_002",
            resolution_policy="latest",
            prior_cutoff=datetime.now(timezone.utc),
            beliefs={},
            converged=True,
            iterations=0,
            max_residual=0.0,
        )
        assert bs.created_at is not None

    def test_compilation_summary(self):
        bs = BeliefState(
            bp_run_id="run_003",
            resolution_policy="source:src_001",
            prior_cutoff=datetime.now(timezone.utc),
            beliefs={"gcn_a": 0.9},
            compilation_summary={"gcs_1": "direct", "gcs_2": "formal_expr"},
            converged=True,
            iterations=10,
            max_residual=1e-5,
        )
        assert bs.compilation_summary["gcs_1"] == "direct"
        assert bs.compilation_summary["gcs_2"] == "formal_expr"

    def test_compilation_summary_optional(self):
        bs = BeliefState(
            bp_run_id="run_004",
            resolution_policy="latest",
            prior_cutoff=datetime.now(timezone.utc),
            beliefs={},
            converged=False,
            iterations=100,
            max_residual=0.05,
        )
        assert bs.compilation_summary is None

    def test_unconverged_still_valid(self):
        bs = BeliefState(
            bp_run_id="run_005",
            resolution_policy="latest",
            prior_cutoff=datetime.now(timezone.utc),
            beliefs={"gcn_x": 0.6},
            converged=False,
            iterations=500,
            max_residual=0.01,
        )
        assert bs.converged is False
        assert bs.beliefs["gcn_x"] == 0.6
