import pytest

from gaia.ir import QuantityLiteral
from gaia.unit import Quantity, from_literal, q, to_literal, ureg


def test_q_creates_shared_registry_quantity():
    qty = q(80, "K")

    assert isinstance(qty, Quantity)
    assert qty._REGISTRY is ureg
    assert qty.magnitude == 80
    assert str(qty.units) == "kelvin"


def test_to_literal_is_deterministic_json_native():
    literal = to_literal(q(80, "K"))

    assert literal == QuantityLiteral(value=80.0, unit="kelvin")
    assert literal.model_dump(mode="json") == {
        "schema_version": "gaia.quantity_literal.v1",
        "value": 80.0,
        "unit": "kelvin",
    }


def test_from_literal_roundtrips_quantity():
    literal = QuantityLiteral(value=3.0, unit="meter / second")

    qty = from_literal(literal)

    assert isinstance(qty, Quantity)
    assert qty.to("m/s").magnitude == pytest.approx(3.0)


def test_to_literal_rejects_non_quantity():
    with pytest.raises(TypeError, match="Expected a gaia.unit.Quantity"):
        to_literal(80)
