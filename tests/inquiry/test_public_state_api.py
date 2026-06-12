"""Public inquiry-state contract for downstream research packages."""

from __future__ import annotations

import pytest

from gaia.engine import inquiry
from gaia.engine.inquiry import state as state_module

pytestmark = pytest.mark.pr_gate


EXPECTED_RESEARCH_STATE_API = (
    "STATE_SCHEMA_VERSION",
    "VALID_OBLIGATION_KINDS",
    "InquiryState",
    "SyntheticHypothesis",
    "SyntheticObligation",
    "append_tactic_event",
    "load_state",
    "mint_qid",
    "save_state",
)


def test_research_public_state_api_is_declared_and_facade_exported() -> None:
    """Pin the inquiry-state subset that gaia-research may import."""
    assert inquiry.RESEARCH_PUBLIC_STATE_API == EXPECTED_RESEARCH_STATE_API
    assert state_module.RESEARCH_PUBLIC_STATE_API == EXPECTED_RESEARCH_STATE_API

    for name in EXPECTED_RESEARCH_STATE_API:
        assert hasattr(inquiry, name)
        assert hasattr(state_module, name)
        assert getattr(inquiry, name) == getattr(state_module, name)
