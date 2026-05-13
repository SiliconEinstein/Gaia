"""Tests for Parameterization data models."""

from datetime import UTC

import pytest

from gaia.ir import (
    CROMWELL_EPS,
    ParameterizationSource,
    PriorRecord,
    ResolutionPolicy,
)


def test_strategy_param_record_is_not_public_ir_contract():
    """Strategy probabilities live inline on Strategy in the v0.5 IR contract."""
    import gaia.ir as ir

    assert not hasattr(ir, "StrategyParamRecord")


class TestCromwellEps:
    def test_value(self):
        assert CROMWELL_EPS == 1e-3


class TestPriorRecord:
    def test_creation(self):
        r = PriorRecord(knowledge_id="github:test::abc", value=0.7, source_id="src_001")
        assert r.knowledge_id == "github:test::abc"
        assert r.value == 0.7
        assert r.created_at is not None

    def test_cromwell_clamp_low(self):
        r = PriorRecord(knowledge_id="github:test::k1", value=0.0, source_id="s")
        assert r.value == CROMWELL_EPS

    def test_cromwell_clamp_high(self):
        r = PriorRecord(knowledge_id="github:test::k1", value=1.0, source_id="s")
        assert r.value == 1 - CROMWELL_EPS

    def test_negative_clamped(self):
        r = PriorRecord(knowledge_id="github:test::k1", value=-0.5, source_id="s")
        assert r.value == CROMWELL_EPS

    def test_in_range_unchanged(self):
        r = PriorRecord(knowledge_id="github:test::k1", value=0.5, source_id="s")
        assert r.value == 0.5


class TestParameterizationSource:
    def test_creation(self):
        from datetime import datetime

        s = ParameterizationSource(
            source_id="src_001",
            model="gpt-5-mini",
            policy="conservative",
            created_at=datetime.now(UTC),
        )
        assert s.source_id == "src_001"
        assert s.model == "gpt-5-mini"

    def test_optional_fields(self):
        from datetime import datetime

        s = ParameterizationSource(
            source_id="src_002",
            model="claude-opus",
            created_at=datetime.now(UTC),
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
        from datetime import datetime

        cutoff = datetime(2026, 3, 29, tzinfo=UTC)
        p = ResolutionPolicy(strategy="latest", prior_cutoff=cutoff)
        assert p.prior_cutoff == cutoff
