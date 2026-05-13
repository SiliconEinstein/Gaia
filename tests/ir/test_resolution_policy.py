"""ResolutionPolicy.resolve() tests.

The policy walks a list of PriorRecord instances and returns a single winner
according to its strategy + tiebreaker rules. The default strategy
``explicit_priority`` matches sources against a priority order of patterns
(supporting trailing wildcards) with within-pattern recency as the tiebreaker.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from gaia.ir import (
    DEFAULT_PRIORITY_ORDER,
    PriorRecord,
    ResolutionPolicy,
    default_resolution_policy,
)


def _record(value: float, source_id: str, *, created_at: datetime | None = None) -> PriorRecord:
    return PriorRecord(
        knowledge_id="test::claim",
        value=value,
        source_id=source_id,
        justification="t",
        created_at=created_at or datetime.now(UTC),
    )


def test_resolve_empty_returns_none():
    policy = ResolutionPolicy()
    assert policy.resolve([]) is None


def test_resolve_single_record_returns_it():
    record = _record(0.5, "user_priors")
    assert default_resolution_policy().resolve([record]) is record


# --------------------------------------------------------------------------- #
# explicit_priority strategy                                                  #
# --------------------------------------------------------------------------- #


def test_explicit_priority_user_priors_beats_continuous_inference():
    user = _record(0.7, "user_priors")
    engine = _record(0.45, "continuous_inference")
    winner = default_resolution_policy().resolve([engine, user])
    assert winner is user


def test_explicit_priority_calibration_beats_user_priors_when_present():
    """DEFAULT_PRIORITY_ORDER lets retrospective calibration override authors."""
    # Reverse order so we know it's not "first in input list".
    user = _record(0.5, "user_priors")
    calib = _record(0.62, "calibration_2026q2")
    winner = default_resolution_policy().resolve([user, calib])
    assert winner is calib


def test_explicit_priority_continuous_inference_beats_agent():
    engine = _record(0.45, "continuous_inference")
    agent = _record(0.55, "agent_xyz")
    winner = default_resolution_policy().resolve([engine, agent])
    assert winner is engine


def test_explicit_priority_claim_inline_below_user_priors():
    """claim(prior=) shortcut sits below explicit register_prior."""
    inline = _record(0.5, "claim_inline")
    user = _record(0.7, "user_priors")
    winner = default_resolution_policy().resolve([inline, user])
    assert winner is user


def test_explicit_priority_recency_tiebreaks_within_same_source():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    older = _record(0.4, "user_priors", created_at=base)
    newer = _record(0.6, "user_priors", created_at=base + timedelta(days=30))
    winner = default_resolution_policy().resolve([older, newer])
    assert winner is newer


def test_explicit_priority_wildcard_matches_prefix():
    reviewer_a = _record(0.3, "reviewer_alice")
    reviewer_b = _record(0.6, "reviewer_bob")
    agent = _record(0.99, "agent_xyz")
    # DEFAULT_PRIORITY_ORDER: reviewer_* before agent_*.
    winner = default_resolution_policy().resolve([agent, reviewer_a, reviewer_b])
    # Recency tiebreaker within reviewer_*: bob was registered after alice
    # because it was constructed second with default created_at=now().
    assert winner.source_id.startswith("reviewer_")


def test_explicit_priority_falls_back_to_recency_when_no_pattern_matches():
    """A custom priority_order without catch-all falls back to global recency."""
    policy = ResolutionPolicy(
        strategy="explicit_priority",
        priority_order=["user_priors"],
    )
    base = datetime(2026, 1, 1, tzinfo=UTC)
    older = _record(0.3, "agent_xyz", created_at=base)
    newer = _record(0.7, "continuous_inference", created_at=base + timedelta(days=10))
    winner = policy.resolve([older, newer])
    assert winner is newer


def test_invalid_wildcard_in_pattern_raises_at_construction():
    with pytest.raises(ValueError, match="wildcards may only appear at the end"):
        ResolutionPolicy(strategy="explicit_priority", priority_order=["us*er_priors"])


def test_default_priority_order_places_calibration_above_user_priors():
    assert DEFAULT_PRIORITY_ORDER.index("calibration_*") < DEFAULT_PRIORITY_ORDER.index(
        "user_priors"
    )
    assert "claim_inline" in DEFAULT_PRIORITY_ORDER
    assert DEFAULT_PRIORITY_ORDER.index("user_priors") < DEFAULT_PRIORITY_ORDER.index(
        "claim_inline"
    )


# --------------------------------------------------------------------------- #
# latest strategy                                                             #
# --------------------------------------------------------------------------- #


def test_latest_strategy_picks_most_recent_irrespective_of_source():
    base = datetime(2026, 1, 1, tzinfo=UTC)
    user = _record(0.5, "user_priors", created_at=base)
    engine = _record(0.7, "continuous_inference", created_at=base + timedelta(days=1))
    winner = ResolutionPolicy(strategy="latest").resolve([user, engine])
    assert winner is engine


# --------------------------------------------------------------------------- #
# source strategy                                                             #
# --------------------------------------------------------------------------- #


def test_source_strategy_filters_to_matching_records():
    user_old = _record(
        0.5,
        "user_priors",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    user_new = _record(
        0.7,
        "user_priors",
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    engine = _record(0.99, "continuous_inference")
    policy = ResolutionPolicy(strategy="source", source_id="user_priors")
    winner = policy.resolve([engine, user_old, user_new])
    assert winner is user_new


def test_source_strategy_returns_none_when_target_source_absent():
    engine = _record(0.5, "continuous_inference")
    policy = ResolutionPolicy(strategy="source", source_id="reviewer_alice")
    assert policy.resolve([engine]) is None


def test_source_strategy_requires_source_id():
    with pytest.raises(ValueError, match="requires source_id"):
        ResolutionPolicy(strategy="source")


# --------------------------------------------------------------------------- #
# prior_cutoff filter                                                         #
# --------------------------------------------------------------------------- #


def test_prior_cutoff_filters_records_after_cutoff():
    early = _record(0.3, "user_priors", created_at=datetime(2026, 1, 1, tzinfo=UTC))
    late = _record(0.7, "user_priors", created_at=datetime(2026, 12, 1, tzinfo=UTC))
    policy = ResolutionPolicy(prior_cutoff=datetime(2026, 6, 1, tzinfo=UTC))
    winner = policy.resolve([early, late])
    assert winner is early


def test_prior_cutoff_returning_none_when_all_filtered():
    late = _record(0.7, "user_priors", created_at=datetime(2026, 12, 1, tzinfo=UTC))
    policy = ResolutionPolicy(prior_cutoff=datetime(2026, 1, 1, tzinfo=UTC))
    assert policy.resolve([late]) is None
