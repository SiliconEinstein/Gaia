import pytest

from gaia.lang.runtime.grounding import Grounding


def test_grounding_source_fact():
    g = Grounding(kind="source_fact", rationale="Extracted from Fig.2.")
    assert g.kind == "source_fact"
    assert g.rationale == "Extracted from Fig.2."
    assert g.source_refs == []


def test_grounding_with_source_refs():
    g = Grounding(kind="source_fact", rationale="From paper.", source_refs=["ctx_1"])
    assert g.source_refs == ["ctx_1"]


def test_grounding_invalid_kind():
    with pytest.raises(ValueError):
        Grounding(kind="invalid_kind", rationale="bad")
