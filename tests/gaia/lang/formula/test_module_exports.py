import pytest

import gaia.engine.lang.formula as formula


def test_formula_module_unknown_attribute_raises() -> None:
    with pytest.raises(AttributeError, match="has no attribute 'Bogus'"):
        _ = formula.Bogus  # type: ignore[attr-defined]
