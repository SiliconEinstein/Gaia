"""Tests for Parameterization data models."""

import pytest
from gaia.gaia_ir import (
    PriorRecord,
    StrategyParamRecord,
    ParameterizationSource,
    ResolutionPolicy,
    CROMWELL_EPS,
)


class TestCromwellEps:
    def test_value(self):
        assert CROMWELL_EPS == 1e-3


class TestPriorRecord:
    def test_creation(self):
        r = PriorRecord(gcn_id="gcn_abc", value=0.7, source_id="src_001")
        assert r.gcn_id == "gcn_abc"
        assert r.value == 0.7
        assert r.created_at is not None

    def test_cromwell_clamp_low(self):
        r = PriorRecord(gcn_id="gcn_1", value=0.0, source_id="s")
        assert r.value == CROMWELL_EPS

    def test_cromwell_clamp_high(self):
        r = PriorRecord(gcn_id="gcn_1", value=1.0, source_id="s")
        assert r.value == 1 - CROMWELL_EPS

    def test_negative_clamped(self):
        r = PriorRecord(gcn_id="gcn_1", value=-0.5, source_id="s")
        assert r.value == CROMWELL_EPS

    def test_in_range_unchanged(self):
        r = PriorRecord(gcn_id="gcn_1", value=0.5, source_id="s")
        assert r.value == 0.5


class TestStrategyParamRecord:
    def test_single_param(self):
        """noisy_and: single conditional probability."""
        r = StrategyParamRecord(
            strategy_id="gcs_abc",
            conditional_probabilities=[0.85],
            source_id="src_001",
        )
        assert r.conditional_probabilities == [0.85]

    def test_multi_param_cpt(self):
        """infer with 2 premises: 2^2 = 4 parameters."""
        r = StrategyParamRecord(
            strategy_id="gcs_abc",
            conditional_probabilities=[0.9, 0.3, 0.4, 0.1],
            source_id="src_001",
        )
        assert len(r.conditional_probabilities) == 4

    def test_cromwell_clamping(self):
        r = StrategyParamRecord(
            strategy_id="gcs_1",
            conditional_probabilities=[0.0, 1.0],
            source_id="s",
        )
        assert r.conditional_probabilities[0] == CROMWELL_EPS
        assert r.conditional_probabilities[1] == 1 - CROMWELL_EPS

    def test_auto_timestamp(self):
        r = StrategyParamRecord(
            strategy_id="gcs_1",
            conditional_probabilities=[0.5],
            source_id="s",
        )
        assert r.created_at is not None


class TestParameterizationSource:
    def test_creation(self):
        from datetime import datetime, timezone

        s = ParameterizationSource(
            source_id="src_001",
            model="gpt-5-mini",
            policy="conservative",
            created_at=datetime.now(timezone.utc),
        )
        assert s.source_id == "src_001"
        assert s.model == "gpt-5-mini"

    def test_optional_fields(self):
        from datetime import datetime, timezone

        s = ParameterizationSource(
            source_id="src_002",
            model="claude-opus",
            created_at=datetime.now(timezone.utc),
        )
        assert s.policy is None
        assert s.config is None


class TestResolutionPolicy:
    def test_latest(self):
        p = ResolutionPolicy(strategy="latest")
        assert p.strategy == "latest"
        assert p.source_id is None

    def test_source_with_id(self):
        p = ResolutionPolicy(strategy="source", source_id="src_001")
        assert p.source_id == "src_001"

    def test_source_without_id_rejected(self):
        with pytest.raises(ValueError, match="source_id"):
            ResolutionPolicy(strategy="source")

    def test_with_prior_cutoff(self):
        from datetime import datetime, timezone

        cutoff = datetime(2026, 3, 29, tzinfo=timezone.utc)
        p = ResolutionPolicy(strategy="latest", prior_cutoff=cutoff)
        assert p.prior_cutoff == cutoff
