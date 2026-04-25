from gaia.ir import CallableRef, DistributionSpec, QuantityLiteral
from gaia.stats import (
    Beta,
    Binomial,
    Cauchy,
    Exponential,
    LogNormal,
    Normal,
    Poisson,
    StudentT,
    from_callable,
)
from gaia.unit import q


def test_normal_constructor_converts_quantities_to_literals():
    spec = Normal(mu=q(80, "K"), sigma=q(3, "K"))

    assert spec == DistributionSpec(
        kind="normal",
        params={
            "mu": QuantityLiteral(value=80.0, unit="kelvin"),
            "sigma": QuantityLiteral(value=3.0, unit="kelvin"),
        },
    )


def test_all_builtin_constructors_return_specs():
    specs = [
        LogNormal(mu=0.0, sigma=1.0),
        StudentT(df=5, mu=0.0, sigma=1.0),
        Cauchy(mu=0.0, gamma=1.0),
        Binomial(n=12, p=0.4),
        Poisson(rate=q(2, "1/s")),
        Exponential(rate=q(2, "1/s")),
        Beta(alpha=2.0, beta=3.0),
    ]

    assert [spec.kind for spec in specs] == [
        "lognormal",
        "student_t",
        "cauchy",
        "binomial",
        "poisson",
        "exponential",
        "beta",
    ]


def test_from_callable_builds_custom_distribution_spec():
    def logpdf(x: float) -> float:
        return -x * x

    spec = from_callable(
        logpdf,
        name="pkg:unit_normal_logpdf",
        version="1.0",
        params={"scale": 1.0},
        purity="pure",
    )

    assert spec.kind == "custom"
    assert spec.params == {"scale": 1.0}
    assert isinstance(spec.callable_ref, CallableRef)
    assert spec.callable_ref.name == "pkg:unit_normal_logpdf"
    assert spec.callable_ref.version == "1.0"
    assert spec.callable_ref.signature == "(x: float) -> float"
    assert spec.callable_ref.source_hash.startswith("sha256:")
    assert spec.callable_ref.purity == "pure"


def test_stats_module_does_not_import_scipy():
    import sys

    assert "scipy" not in sys.modules
    assert "scipy.stats" not in sys.modules
