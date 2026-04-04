"""Tests for module narrative tracking."""

from gaia.lang.runtime.nodes import Knowledge
from gaia.lang.runtime.package import CollectedPackage


def test_declaration_index_increments_within_module():
    pkg = CollectedPackage("test_pkg")
    with pkg:
        a = Knowledge(content="A.", type="claim")
        b = Knowledge(content="B.", type="claim")
        c = Knowledge(content="C.", type="claim")
    assert a._declaration_index == 0
    assert b._declaration_index == 1
    assert c._declaration_index == 2


def test_module_order_tracks_first_seen():
    pkg = CollectedPackage("test_pkg")
    a = Knowledge(content="A.", type="claim")
    a._source_module = "s1_intro"
    b = Knowledge(content="B.", type="claim")
    b._source_module = "s2_model"
    c = Knowledge(content="C.", type="claim")
    c._source_module = "s1_intro"

    pkg._register_knowledge(a)
    pkg._register_knowledge(b)
    pkg._register_knowledge(c)

    assert pkg._module_order == ["s1_intro", "s2_model"]
    assert a._declaration_index == 0
    assert b._declaration_index == 0  # first in s2_model
    assert c._declaration_index == 1  # second in s1_intro


def test_none_module_for_root():
    pkg = CollectedPackage("test_pkg")
    a = Knowledge(content="A.", type="claim")
    a._source_module = None
    pkg._register_knowledge(a)
    assert a._declaration_index == 0
    assert pkg._module_order == []  # None module not tracked in order
