from gaia.lang import compute
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.action import Compute
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.package import CollectedPackage


class IntClaim(Claim):
    """Value is {value}."""

    value: int


class SumResult(Claim):
    """Sum is {value}."""

    value: int


def test_compute_function():
    a = IntClaim(value=3)
    b = IntClaim(value=4)
    result = compute(
        SumResult, fn=lambda a, b: a.value + b.value, given=(a, b), rationale="Addition."
    )
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


def test_compute_decorator_keyword_args_record_given_claims():
    @compute
    def add(a: IntClaim, b: IntClaim) -> SumResult:
        """Add two integers."""
        return a.value + b.value

    with CollectedPackage("kw_compute") as pkg:
        a = IntClaim(value=3)
        a.label = "a"
        b = IntClaim(value=4)
        b.label = "b"
        result = add(a=a, b=b)
        result.label = "sum"

    assert result.supports[0].given == (a, b)

    compiled = compile_package_artifact(pkg)
    strategy = compiled.graph.strategies[0]
    assert strategy.premises == ["github:kw_compute::a", "github:kw_compute::b"]


def test_compute_creates_reviewable_implication_warrant():
    a = IntClaim(value=3)
    b = IntClaim(value=4)
    result = compute(
        SumResult,
        fn=lambda a, b: a.value + b.value,
        given=(a, b),
        rationale="Addition.",
    )
    action = result.supports[0]
    assert len(action.warrants) == 1
    warrant = action.warrants[0]
    assert warrant.metadata["generated"] is True
    assert warrant.metadata["helper_kind"] == "implication_warrant"
    assert warrant.metadata["review"] is True
    assert warrant.metadata["relation"] == {
        "type": "compute",
        "given": (a, b),
        "conclusion": result,
    }
