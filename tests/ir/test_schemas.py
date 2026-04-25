import pytest
from pydantic import ValidationError

from gaia.ir import CallableRef, DistributionLiteral, QuantityLiteral


def test_quantity_literal_is_json_native():
    literal = QuantityLiteral(value=80, unit="K")

    assert literal.model_dump(mode="json") == {
        "schema_version": "gaia.quantity_literal.v1",
        "value": 80.0,
        "unit": "K",
    }


def test_builtin_distribution_rejects_callable_ref():
    callable_ref = CallableRef(name="pkg:normal", version="1.0")

    with pytest.raises(ValidationError, match="Built-in distributions"):
        DistributionLiteral(
            kind="normal",
            params={"mu": 0.0, "sigma": 1.0},
            callable_ref=callable_ref,
        )


def test_custom_distribution_requires_callable_ref():
    with pytest.raises(ValidationError, match="custom distributions require callable_ref"):
        DistributionLiteral(kind="custom", params={})


def test_custom_distribution_accepts_callable_ref():
    callable_ref = CallableRef(
        name="pkg:studentized_residual",
        version="1.0",
        signature="(x: float) -> float",
        source_hash="sha256:abc123",
        purity="pure",
    )

    spec = DistributionLiteral(
        kind="custom",
        params={"scale": 2.0},
        callable_ref=callable_ref,
    )

    assert spec.kind == "custom"
    assert spec.callable_ref == callable_ref
