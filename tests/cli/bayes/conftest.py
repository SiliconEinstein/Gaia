"""Shared fixtures for ``gaia bayes <verb>`` tests.

The :func:`bayes_package` fixture produces a Gaia knowledge package
that already imports ``bayes`` + the typed-term primitives, mirroring
what a fresh ``gaia pkg scaffold`` would lay down by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

import pytest

_PYPROJECT_TEMPLATE = """\
[project]
name = "{name}"
version = "0.1.0"
description = "Test fixture package for gaia bayes tests."

[tool.hatch.build.targets.wheel]
packages = ["src/{import_name}"]

[tool.gaia]
type = "knowledge-package"
uuid = "{uuid}"
"""

# Package-root entrypoint: a thin composition shell over the authored/
# submodule (the canonical CLI write target).
_ROOT_INIT_TEMPLATE = """\
__all__: list[str] = []

from . import authored as _authored

for _gaia_name, _gaia_value in vars(_authored).items():
    if not _gaia_name.startswith("_"):
        globals()[_gaia_name] = _gaia_value
del _gaia_name, _gaia_value

__all__ = [*__all__, *_authored.__all__]
"""

# authored/__init__.py — where ``gaia bayes`` / ``gaia author`` writes land.
_AUTHORED_INIT_TEMPLATE = """\
from gaia.engine import bayes
from gaia.engine.lang import (
    Beta,
    BetaBinomial,
    Binomial,
    Bool,
    Cauchy,
    ChiSquared,
    ClaimAtom,
    Constant,
    Exponential,
    Gamma,
    LogNormal,
    Nat,
    Normal,
    Poisson,
    Probability,
    Real,
    StudentT,
    Variable,
    claim,
    contradict,
    derive,
    equal,
    equals,
    exclusive,
    land,
    note,
    observe,
    register_prior,
)

hypothesis_a = claim("Bayes test hypothesis A.")
hypothesis_b = claim("Bayes test hypothesis B.")
observable_x = Variable(symbol="x", domain=Nat)

__all__ = ["hypothesis_a", "hypothesis_b", "observable_x"]
"""


@dataclass
class BayesPackage:
    """Handles for a freshly scaffolded bayes-test package."""

    root: Path
    # ``source_init`` aliases authored/__init__.py — the canonical CLI write
    # target — so existing read/seed assertions keep working unchanged.
    source_init: Path
    authored_init: Path
    root_init: Path
    project_name: str
    import_name: str


@pytest.fixture
def bayes_package(tmp_path: Path) -> BayesPackage:
    """Scaffold a Gaia package that pre-imports the bayes surface."""
    project_name = "bayes-fixture-gaia"
    import_name = "bayes_fixture"
    root = tmp_path / project_name
    src = root / "src" / import_name
    src.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        _PYPROJECT_TEMPLATE.format(
            name=project_name,
            import_name=import_name,
            uuid=str(uuid4()),
        )
    )
    root_init = src / "__init__.py"
    root_init.write_text(_ROOT_INIT_TEMPLATE)
    authored = src / "authored"
    authored.mkdir()
    authored_init = authored / "__init__.py"
    authored_init.write_text(_AUTHORED_INIT_TEMPLATE)
    return BayesPackage(
        root=root,
        source_init=authored_init,
        authored_init=authored_init,
        root_init=root_init,
        project_name=project_name,
        import_name=import_name,
    )
