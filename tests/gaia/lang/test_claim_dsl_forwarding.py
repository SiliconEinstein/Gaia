"""Tests for claim() DSL surface and its interaction with register_prior().

In v0.5+ the prior pipeline is multi-source. Two author-facing entry points:

- ``claim(content, prior=X)`` — convenience shortcut equivalent to
  ``register_prior(c, X, source_id="claim_inline", justification="(inline ...)")``.
  Inline priors sit at the lowest deliberate tier of the default
  ResolutionPolicy priority order.
- ``register_prior(c, value=..., justification=..., source_id=...)`` — the
  canonical, ranked-above-inline path. Use this whenever the prior is
  load-bearing and deserves a documented justification.

Any explicit ``register_prior()`` call wins over the inline shortcut.
"""

from datetime import UTC, datetime

import pytest

from gaia.engine.lang import (
    ClaimKind,
    Constant,
    Equals,
    Probability,
    Variable,
    claim,
    register_prior,
)
from gaia.engine.lang.dsl.register_prior import (
    DEFAULT_SOURCE_ID,
    PRIOR_RECORDS_METADATA_KEY,
    get_prior_records,
)


def test_dsl_claim_forwards_inline_prior_as_claim_inline_record():
    """claim(prior=X) routes through register_prior(source_id='claim_inline')."""
    c = claim("test", prior=0.5)
    records = c.metadata[PRIOR_RECORDS_METADATA_KEY]
    assert len(records) == 1
    assert records[0]["value"] == 0.5
    assert records[0]["source_id"] == "claim_inline"
    assert "inline default" in records[0]["justification"]
    # The Claim.prior attribute is intentionally NOT set — inline priors flow
    # only through the prior_records pipeline so resolution can override them.
    assert c.prior is None


def test_dsl_claim_forwards_formula():
    """formula= still forwards through DSL claim()."""
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(p, Constant(0.75, Probability))

    c = claim("p = 0.75", formula=eq)

    assert c.formula is eq
    assert "formula" not in c.metadata


def test_dsl_claim_forwards_kind():
    """kind= still forwards through DSL claim()."""
    p = Variable(symbol="p", domain=Probability)
    eq = Equals(p, Constant(0.75, Probability))

    c = claim("p = 0.75", formula=eq, kind=ClaimKind.PARAMETER)

    assert c.kind is ClaimKind.PARAMETER
    assert "kind" not in c.metadata


def test_dsl_claim_default_kind_general():
    """Bare claim() defaults to GENERAL kind, no formula, no prior."""
    c = claim("plain")
    assert c.kind is ClaimKind.GENERAL
    assert c.formula is None
    assert c.prior is None
    # No prior_records yet because no prior was set.
    assert PRIOR_RECORDS_METADATA_KEY not in c.metadata


def test_dsl_claim_other_metadata_still_passes_through():
    """Genuine metadata keys (custom annotations) still flow into c.metadata."""
    c = claim("test", custom_tag="foo", another="bar")
    assert c.metadata.get("custom_tag") == "foo"
    assert c.metadata.get("another") == "bar"


def test_register_prior_overrides_claim_inline_under_default_policy():
    """Explicit register_prior() with default source_id beats the inline shortcut."""
    from gaia.engine.ir import default_resolution_policy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    c = claim("Subject p smokes daily.", prior=0.3)
    register_prior(c, 0.45, justification="adjusted after literature review")

    records = c.metadata[PRIOR_RECORDS_METADATA_KEY]
    assert len(records) == 2
    assert {r["source_id"] for r in records} == {"claim_inline", "user_priors"}

    resolve_priors_to_metadata([c], default_resolution_policy())
    assert c.metadata["prior"] == 0.45
    assert "literature review" in c.metadata["prior_justification"]
    assert c.metadata["prior_source_id"] == "user_priors"


def test_register_prior_appends_record_with_default_source():
    """register_prior() with default source_id stores a 'user_priors' record."""
    c = claim("Subject S smokes daily.")
    register_prior(c, value=0.3, justification="literature base rate")
    records = c.metadata[PRIOR_RECORDS_METADATA_KEY]
    assert len(records) == 1
    assert records[0]["value"] == 0.3
    assert records[0]["source_id"] == DEFAULT_SOURCE_ID
    assert records[0]["justification"] == "literature base rate"
    assert "created_at" in records[0]


def test_get_prior_records_returns_copy_and_rejects_non_claim():
    c = claim("Subject S smokes daily.")
    register_prior(c, value=0.3, justification="literature base rate")

    records = get_prior_records(c)
    assert records == c.metadata[PRIOR_RECORDS_METADATA_KEY]
    records.append({"value": 0.9, "source_id": "agent_x"})
    assert len(c.metadata[PRIOR_RECORDS_METADATA_KEY]) == 1

    with pytest.raises(TypeError, match="expects a Claim"):
        get_prior_records("not a claim")  # type: ignore[arg-type]


def test_get_prior_records_returns_empty_for_malformed_metadata():
    c = claim("Subject S smokes daily.")
    c.metadata[PRIOR_RECORDS_METADATA_KEY] = "reserved key collision"

    assert get_prior_records(c) == []


def test_register_prior_rejects_reserved_metadata_collision():
    c = claim("Subject S smokes daily.")
    c.metadata[PRIOR_RECORDS_METADATA_KEY] = "reserved key collision"

    with pytest.raises(TypeError, match="reserved"):
        register_prior(c, value=0.3, justification="literature base rate")


def test_register_prior_supports_multiple_named_sources():
    """Calling register_prior twice with different sources yields two records."""
    c = claim("Subject S smokes daily.")
    register_prior(c, value=0.3, justification="literature")
    register_prior(
        c,
        value=0.45,
        source_id="continuous_inference",
        justification="posterior mean from continuous engine",
    )
    records = c.metadata[PRIOR_RECORDS_METADATA_KEY]
    assert len(records) == 2
    assert {r["source_id"] for r in records} == {"user_priors", "continuous_inference"}


def test_register_prior_rejects_non_claim():
    with pytest.raises(TypeError, match="must be a Claim"):
        register_prior("not a claim", 0.5, justification="bad")  # type: ignore[arg-type]


def test_register_prior_rejects_out_of_bounds():
    c = claim("Bound test.")
    with pytest.raises(ValueError, match="Cromwell bounds"):
        register_prior(c, 1.0, justification="boundary")
    with pytest.raises(ValueError, match="Cromwell bounds"):
        register_prior(c, 0.0, justification="boundary")
    with pytest.raises(ValueError, match="Cromwell bounds"):
        register_prior(c, -0.1, justification="negative")


def test_register_prior_rejects_empty_justification():
    c = claim("Justification test.")
    with pytest.raises(ValueError, match="non-empty justification"):
        register_prior(c, 0.5, justification="")
    with pytest.raises(ValueError, match="non-empty justification"):
        register_prior(c, 0.5, justification="   ")


def test_register_prior_rejects_empty_source_id():
    c = claim("Source test.")
    with pytest.raises(ValueError, match="non-empty string"):
        register_prior(c, 0.5, source_id="", justification="reason")


def test_register_prior_rejects_bool_value():
    """Booleans must not silently coerce to 0/1."""
    c = claim("Bool test.")
    with pytest.raises(TypeError, match="numeric scalar"):
        register_prior(c, True, justification="bad")  # type: ignore[arg-type]


def test_register_prior_rejects_nan_value():
    c = claim("NaN test.")
    with pytest.raises(ValueError, match="finite"):
        register_prior(c, float("nan"), justification="bad")


def test_resolve_priors_to_metadata_ignores_non_claims_and_claims_without_records():
    from gaia.engine.ir import default_resolution_policy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    c = claim("No prior records.")

    resolve_priors_to_metadata([object(), c], default_resolution_policy())  # type: ignore[list-item]

    assert "prior" not in c.metadata
    assert "prior_source_id" not in c.metadata


def test_resolve_priors_to_metadata_handles_datetime_and_missing_created_at():
    from gaia.engine.ir import ResolutionPolicy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    c = claim("Subject S smokes daily.")
    c.metadata[PRIOR_RECORDS_METADATA_KEY] = [
        {
            "value": 0.3,
            "source_id": "agent_old",
            "justification": "legacy IR record",
        },
        {
            "value": 0.7,
            "source_id": "agent_new",
            "justification": "fresh record",
            "created_at": datetime(2026, 1, 1, tzinfo=UTC),
        },
    ]

    resolve_priors_to_metadata([c], ResolutionPolicy(strategy="latest"))

    assert c.metadata["prior"] == 0.7
    assert c.metadata["prior_source_id"] == "agent_new"


def test_resolve_priors_to_metadata_rejects_malformed_prior_records():
    from gaia.engine.ir import default_resolution_policy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    c = claim("Subject S smokes daily.")
    c.metadata[PRIOR_RECORDS_METADATA_KEY] = "reserved key collision"

    with pytest.raises(TypeError, match="reserved"):
        resolve_priors_to_metadata([c], default_resolution_policy())


def test_resolve_priors_to_metadata_rejects_malformed_created_at():
    from gaia.engine.ir import default_resolution_policy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    c = claim("Subject S smokes daily.")
    c.metadata[PRIOR_RECORDS_METADATA_KEY] = [
        {
            "value": 0.3,
            "source_id": "agent_x",
            "justification": "bad timestamp",
            "created_at": 123,
        }
    ]

    with pytest.raises(ValueError, match="malformed created_at"):
        resolve_priors_to_metadata([c], default_resolution_policy())


def test_resolve_priors_to_metadata_leaves_metadata_when_policy_has_no_winner():
    from gaia.engine.ir import ResolutionPolicy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    c = claim("Subject S smokes daily.")
    register_prior(c, value=0.3, justification="literature base rate")

    resolve_priors_to_metadata(
        [c],
        ResolutionPolicy(strategy="source", source_id="missing_source"),
    )

    assert "prior" not in c.metadata
    assert "prior_source_id" not in c.metadata
