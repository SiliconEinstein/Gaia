import json
import subprocess
import sys

import pytest

from gaia.ir import CallableRef, DistributionLiteral, QuantityLiteral
from gaia.stats import (
    Beta,
    Binomial,
    Cauchy,
    Exponential,
    LogNormal,
    Normal,
    Poisson,
    StudentT,
    custom_distribution,
)
from gaia.unit import q


def test_normal_constructor_converts_quantities_to_literals():
    spec = Normal(mu=q(80, "K"), sigma=q(3, "K"))

    assert spec == DistributionLiteral(
        kind="normal",
        params={
            "mu": QuantityLiteral(value=80.0, unit="kelvin"),
            "sigma": QuantityLiteral(value=3.0, unit="kelvin"),
        },
    )


def test_all_builtin_constructors_return_literals():
    literals = [
        LogNormal(mu=0.0, sigma=1.0),
        StudentT(df=5, mu=0.0, sigma=1.0),
        Cauchy(mu=0.0, gamma=1.0),
        Binomial(n=12, p=0.4),
        Poisson(rate=q(2, "1/s")),
        Exponential(rate=q(2, "1/s")),
        Beta(alpha=2.0, beta=3.0),
    ]

    assert [literal.kind for literal in literals] == [
        "lognormal",
        "student_t",
        "cauchy",
        "binomial",
        "poisson",
        "exponential",
        "beta",
    ]


def test_builtin_constructor_rejects_bool_params():
    with pytest.raises(TypeError, match="not bool"):
        Normal(mu=True, sigma=1.0)


def test_builtin_constructor_rejects_unsupported_param_type():
    with pytest.raises(TypeError, match="Unsupported distribution parameter type: str"):
        Normal(mu="abc", sigma=1.0)


def test_custom_distribution_builds_distribution_literal():
    def logpdf(x: float) -> float:
        return -x * x

    spec = custom_distribution(
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


def test_custom_distribution_hash_falls_back_when_source_is_unavailable():
    spec = custom_distribution(len, name="python:len")

    assert spec.callable_ref is not None
    assert spec.callable_ref.source_hash.startswith("sha256:")


def test_stats_module_does_not_import_scipy():
    script = (
        "import json, sys; "
        "import gaia.stats; "
        "print(json.dumps({'scipy': 'scipy' in sys.modules, "
        "'scipy.stats': 'scipy.stats' in sys.modules}))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert json.loads(result.stdout) == {"scipy": False, "scipy.stats": False}
