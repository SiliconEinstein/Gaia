"""Regression test — DSL claim() wrapper must forward prior/formula/kind to Claim."""

from gaia.lang import (
    ClaimKind,
    Constant,
    Equals,
    Probability,
    Variable,
    claim,
)


def test_dsl_claim_forwards_prior():
    c = claim("test", prior=0.5)
    assert c.prior == 0.5
    assert "prior" not in c.metadata


def test_dsl_claim_forwards_formula():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(p, Constant(0.75, Probability))

    c = claim("p = 0.75", formula=eq, prior=0.5)

    assert c.formula is eq
    assert "formula" not in c.metadata


def test_dsl_claim_forwards_kind():
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(p, Constant(0.75, Probability))

    c = claim("p = 0.75", formula=eq, kind=ClaimKind.PARAMETER, prior=0.5)

    assert c.kind is ClaimKind.PARAMETER
    assert "kind" not in c.metadata


def test_dsl_claim_full_forwarding():
    """All three new structural fields together — Codex's suggested test."""
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(p, Constant(0.75, Probability))

    c = claim("p = 0.75", formula=eq, kind=ClaimKind.PARAMETER, prior=0.5)

    assert c.formula is eq
    assert c.kind is ClaimKind.PARAMETER
    assert c.prior == 0.5
    assert "formula" not in c.metadata
    assert "kind" not in c.metadata
    assert "prior" not in c.metadata


def test_dsl_claim_default_kind_general():
    c = claim("plain")
    assert c.kind is ClaimKind.GENERAL
    assert c.formula is None
    assert c.prior is None


def test_dsl_claim_other_metadata_still_passes_through():
    """Genuine metadata keys (custom annotations) still flow into c.metadata."""
    c = claim("test", custom_tag="foo", another="bar")
    assert c.metadata.get("custom_tag") == "foo"
    assert c.metadata.get("another") == "bar"
