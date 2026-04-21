from gaia.lang import compute
from gaia.lang.runtime.action import Compute
from gaia.lang.runtime.knowledge import Claim


class IntClaim(Claim):
    """Value is {value}."""

    value: int


class SumResult(Claim):
    """Sum is {value}."""

    value: int


def test_compute_function():
    a = IntClaim(value=3)
    b = IntClaim(value=4)
    result = compute(SumResult, fn=lambda a, b: a.value + b.value, given=(a, b), rationale="Addition.")
    assert isinstance(result, SumResult)
    assert result.value == 7
    assert len(result.supports) == 1
    assert isinstance(result.supports[0], Compute)
    assert result.supports[0].given == (a, b)


def test_compute_decorator():
    @compute
    def add(a: IntClaim, b: IntClaim) -> SumResult:
        """Add two integers."""
        return a.value + b.value

    a = IntClaim(value=3)
    b = IntClaim(value=4)
    result = add(a, b)
    assert isinstance(result, SumResult)
    assert result.value == 7
    assert len(result.supports) == 1
    assert isinstance(result.supports[0], Compute)
    assert result.supports[0].rationale == "Add two integers."
