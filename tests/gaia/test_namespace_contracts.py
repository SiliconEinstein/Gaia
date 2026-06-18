"""Public .gaia namespace ownership contracts."""

from __future__ import annotations

import pytest

from gaia.engine.namespaces import (
    GAIA_NAMESPACE_REGISTRY,
    RESEARCH_NAMESPACE,
    namespace_path,
    namespace_record,
)

pytestmark = pytest.mark.pr_gate


def test_research_namespace_is_reserved_for_external_research_package() -> None:
    record = namespace_record("research")

    assert RESEARCH_NAMESPACE == ".gaia/research"
    assert record.path == ".gaia/research"
    assert record.owner == "gaia-research"
    assert record.lifecycle == "external-plugin"
    assert record.description


def test_research_loop_is_not_a_registered_canonical_namespace() -> None:
    assert "research_loop" not in GAIA_NAMESPACE_REGISTRY
    assert namespace_record("research_loop") is None


def test_namespace_path_rejects_unknown_namespace() -> None:
    with pytest.raises(KeyError, match=r"unknown \.gaia namespace"):
        namespace_path("research_loop")
