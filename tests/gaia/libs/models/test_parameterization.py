"""Tests for parameterization models — PriorRecord, FactorParamRecord, etc."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from gaia.libs.models.parameterization import (
    CROMWELL_EPS,
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
    ResolutionPolicy,
)


# ---------------------------------------------------------------------------
# PriorRecord tests
# ---------------------------------------------------------------------------


class TestPriorRecord:
    def test_creation(self):
        rec = PriorRecord(gcn_id="gcn_abc", value=0.7, source_id="src_1")
        assert rec.gcn_id == "gcn_abc"
        assert rec.value == pytest.approx(0.7)
        assert rec.source_id == "src_1"
        assert isinstance(rec.created_at, datetime)

    def test_created_at_defaults_to_utc_now(self):
        before = datetime.now(timezone.utc)
        rec = PriorRecord(gcn_id="gcn_x", value=0.5, source_id="s")
        after = datetime.now(timezone.utc)
        assert before <= rec.created_at <= after

    def test_cromwell_clamp_zero_to_eps(self):
        rec = PriorRecord(gcn_id="gcn_x", value=0.0, source_id="s")
        assert rec.value == pytest.approx(CROMWELL_EPS)

    def test_cromwell_clamp_one_to_one_minus_eps(self):
        rec = PriorRecord(gcn_id="gcn_x", value=1.0, source_id="s")
        assert rec.value == pytest.approx(1 - CROMWELL_EPS)

    def test_cromwell_clamp_negative(self):
        rec = PriorRecord(gcn_id="gcn_x", value=-0.5, source_id="s")
        assert rec.value == pytest.approx(CROMWELL_EPS)

    def test_value_in_range_unchanged(self):
        rec = PriorRecord(gcn_id="gcn_x", value=0.4, source_id="s")
        assert rec.value == pytest.approx(0.4)

    def test_roundtrip(self):
        rec = PriorRecord(gcn_id="gcn_abc", value=0.6, source_id="src_1")
        data = rec.model_dump()
        restored = PriorRecord.model_validate(data)
        assert restored.gcn_id == rec.gcn_id
        assert restored.value == pytest.approx(rec.value)
        assert restored.source_id == rec.source_id
        assert restored.created_at == rec.created_at

    def test_json_roundtrip(self):
        rec = PriorRecord(gcn_id="gcn_abc", value=0.3, source_id="src_2")
        json_str = rec.model_dump_json()
        restored = PriorRecord.model_validate_json(json_str)
        assert restored.gcn_id == rec.gcn_id
        assert restored.value == pytest.approx(rec.value)


# ---------------------------------------------------------------------------
# FactorParamRecord tests
# ---------------------------------------------------------------------------


class TestFactorParamRecord:
    def test_creation(self):
        rec = FactorParamRecord(factor_id="gcf_abc", probability=0.8, source_id="src_1")
        assert rec.factor_id == "gcf_abc"
        assert rec.probability == pytest.approx(0.8)
        assert rec.source_id == "src_1"
        assert isinstance(rec.created_at, datetime)

    def test_created_at_defaults_to_utc_now(self):
        before = datetime.now(timezone.utc)
        rec = FactorParamRecord(factor_id="gcf_x", probability=0.5, source_id="s")
        after = datetime.now(timezone.utc)
        assert before <= rec.created_at <= after

    def test_cromwell_clamp_zero(self):
        rec = FactorParamRecord(factor_id="gcf_x", probability=0.0, source_id="s")
        assert rec.probability == pytest.approx(CROMWELL_EPS)

    def test_cromwell_clamp_one(self):
        rec = FactorParamRecord(factor_id="gcf_x", probability=1.0, source_id="s")
        assert rec.probability == pytest.approx(1 - CROMWELL_EPS)

    def test_cromwell_clamp_negative(self):
        rec = FactorParamRecord(factor_id="gcf_x", probability=-1.0, source_id="s")
        assert rec.probability == pytest.approx(CROMWELL_EPS)

    def test_value_in_range_unchanged(self):
        rec = FactorParamRecord(factor_id="gcf_x", probability=0.55, source_id="s")
        assert rec.probability == pytest.approx(0.55)

    def test_roundtrip(self):
        rec = FactorParamRecord(factor_id="gcf_abc", probability=0.75, source_id="src_1")
        data = rec.model_dump()
        restored = FactorParamRecord.model_validate(data)
        assert restored.factor_id == rec.factor_id
        assert restored.probability == pytest.approx(rec.probability)
        assert restored.source_id == rec.source_id


# ---------------------------------------------------------------------------
# ParameterizationSource tests
# ---------------------------------------------------------------------------


class TestParameterizationSource:
    def test_creation_minimal(self):
        src = ParameterizationSource(
            source_id="src_001",
            model="openai/gpt-5-mini",
            created_at=datetime.now(timezone.utc),
        )
        assert src.source_id == "src_001"
        assert src.model == "openai/gpt-5-mini"
        assert src.policy is None
        assert src.config is None

    def test_creation_with_optional_fields(self):
        src = ParameterizationSource(
            source_id="src_002",
            model="openai/claude-opus",
            policy="conservative",
            config={"threshold": 0.7, "prompt_version": "v3"},
            created_at=datetime.now(timezone.utc),
        )
        assert src.policy == "conservative"
        assert src.config["threshold"] == 0.7
        assert src.config["prompt_version"] == "v3"

    def test_roundtrip(self):
        src = ParameterizationSource(
            source_id="src_003",
            model="openai/gpt-5-mini",
            policy="aggressive",
            config={"k": "v"},
            created_at=datetime.now(timezone.utc),
        )
        data = src.model_dump()
        restored = ParameterizationSource.model_validate(data)
        assert restored.source_id == src.source_id
        assert restored.model == src.model
        assert restored.policy == src.policy
        assert restored.config == src.config


# ---------------------------------------------------------------------------
# ResolutionPolicy tests
# ---------------------------------------------------------------------------


class TestResolutionPolicy:
    def test_latest_strategy(self):
        policy = ResolutionPolicy(strategy="latest")
        assert policy.strategy == "latest"
        assert policy.source_id is None
        assert policy.prior_cutoff is None

    def test_source_strategy_with_source_id(self):
        policy = ResolutionPolicy(strategy="source", source_id="src_001")
        assert policy.strategy == "source"
        assert policy.source_id == "src_001"

    def test_source_strategy_without_source_id_rejected(self):
        with pytest.raises(ValidationError):
            ResolutionPolicy(strategy="source")

    def test_latest_with_prior_cutoff(self):
        cutoff = datetime(2025, 1, 1, tzinfo=timezone.utc)
        policy = ResolutionPolicy(strategy="latest", prior_cutoff=cutoff)
        assert policy.prior_cutoff == cutoff

    def test_source_with_prior_cutoff(self):
        cutoff = datetime(2025, 6, 15, tzinfo=timezone.utc)
        policy = ResolutionPolicy(strategy="source", source_id="src_xyz", prior_cutoff=cutoff)
        assert policy.prior_cutoff == cutoff

    def test_roundtrip_latest(self):
        policy = ResolutionPolicy(strategy="latest")
        data = policy.model_dump()
        restored = ResolutionPolicy.model_validate(data)
        assert restored.strategy == policy.strategy

    def test_roundtrip_source(self):
        policy = ResolutionPolicy(strategy="source", source_id="src_001")
        data = policy.model_dump()
        restored = ResolutionPolicy.model_validate(data)
        assert restored.strategy == policy.strategy
        assert restored.source_id == policy.source_id
