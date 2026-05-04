"""Tests for Domain Knowledge subclass and Lang-only registration."""

import pytest

from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Knowledge


def test_domain_is_knowledge_subclass():
    assert issubclass(Domain, Knowledge)


def test_domain_basic_construction():
    d = Domain(content="Single-celled organisms used in genetics", members=["yeast", "ecoli"])
    assert d.members == ["yeast", "ecoli"]
    assert d.content == "Single-celled organisms used in genetics"


def test_domain_members_required_nonempty():
    with pytest.raises(ValueError, match="members"):
        Domain(content="x", members=[])


def test_domain_members_must_be_a_list():
    with pytest.raises(TypeError, match="members"):
        Domain(content="x", members="yeast")  # type: ignore[arg-type]


def test_domain_metadata_independent_per_instance():
    d1 = Domain(content="d1", members=[1])
    d2 = Domain(content="d2", members=[2])
    d1.metadata["k"] = "v"
    assert "k" not in d2.metadata


def test_domain_has_no_prior_field():
    d = Domain(content="x", members=[1])
    assert not hasattr(d, "prior")


def test_domain_does_not_register_into_package_knowledge_map():
    """Spec §2.4: Domain must NOT enter pkg._register_knowledge so compile stays IR-clean."""
    from gaia.lang.runtime.knowledge import _current_package
    from gaia.lang.runtime.package import CollectedPackage

    pkg = CollectedPackage(name="test_pkg", namespace="test")
    token = _current_package.set(pkg)
    try:
        d = Domain(content="x", members=[1])
        # The domain should associate with the package for provenance...
        assert d._package is pkg
        # ...but NOT appear in the IR-bound knowledge list.
        registered = list(getattr(pkg, "knowledge", []) or [])
        assert d not in registered, (
            f"Domain leaked into pkg.knowledge — IR compile would attempt to translate it. "
            f"Registered: {registered}"
        )
    finally:
        _current_package.reset(token)
