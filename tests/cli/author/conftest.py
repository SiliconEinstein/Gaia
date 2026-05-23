"""Shared fixtures for `gaia author <verb>` tests.

The :func:`gaia_package` fixture produces a minimal-but-valid Gaia
knowledge package on disk, matching v0.5 conventions:

* ``pyproject.toml`` with ``[project] name`` ending ``-gaia`` plus
  ``[tool.gaia].type = "knowledge-package"``.
* ``src/<import_name>/__init__.py`` importing the DSL surface and
  declaring at least one ``claim`` so the package is non-empty (some
  invariants only fire when there's something to collide with).
* ``__all__`` populated so post-write loading can read the exported
  symbols.

The fixture returns a small dataclass with the package root, source
``__init__.py`` path, and a couple of well-known seed labels — tests
use those labels directly when exercising reference resolution.
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
description = "Test fixture package for gaia author tests."

[tool.hatch.build.targets.wheel]
packages = ["src/{import_name}"]

[tool.gaia]
type = "knowledge-package"
uuid = "{uuid}"
"""

# Package-root ``__init__.py`` — a thin re-export shell. Hand-authored
# DSL would live here directly; the fixture keeps its seed statements in
# the ``authored/`` submodule (where ``gaia author`` writes), so the
# package's effective authoring surface is the canonical CLI target. The
# root re-exports ``authored/`` so the composed package loads as one DSL.
_ROOT_INIT_TEMPLATE = """\
__all__: list[str] = []

from .authored import *  # noqa: E402, F403  (CLI-authored statements)
from . import authored as _authored  # noqa: E402

__all__ = [*__all__, *_authored.__all__]
"""

# The re-exported ``authored/`` submodule — the canonical home for every
# ``gaia author <verb>`` write. Imports the full agent-author DSL surface
# so the post-write ``--check`` integration can load freshly-authored
# statements without name-resolution errors, and seeds two claims so the
# reference-resolution / collision invariants have something to bind.
_AUTHORED_INIT_TEMPLATE = """\
from gaia.engine.lang import (
    ClaimAtom,
    associate,
    candidate_relation,
    claim,
    compute,
    contradict,
    decompose,
    depends_on,
    derive,
    equal,
    exclusive,
    iff,
    implies,
    infer,
    land,
    lnot,
    lor,
    materialize,
    note,
    observe,
    parameter,
    question,
    register_prior,
)

hypothesis = claim("Test hypothesis claim.", title="Hypothesis")
observation = claim("Test observation claim.", title="Observation")

__all__ = ["hypothesis", "observation"]
"""


@dataclass
class FixturePackage:
    """Handles for a freshly scaffolded test package."""

    root: Path
    # ``source_init`` points at the ``authored/__init__.py`` — the canonical
    # target every ``gaia author`` write lands in. Tests read it to assert
    # the appended statement and seed bindings into it for collision /
    # reference checks. The package-root ``__init__.py`` (a thin re-export
    # shell) is exposed separately as ``root_init`` for the handful of tests
    # that assert the root re-export composition.
    source_init: Path
    authored_init: Path
    root_init: Path
    project_name: str
    import_name: str
    seed_labels: tuple[str, ...]


@pytest.fixture
def gaia_package(tmp_path: Path) -> FixturePackage:
    """Scaffold a minimal Gaia knowledge package under ``tmp_path``."""
    project_name = "fixture-gaia"
    import_name = "fixture"
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
    return FixturePackage(
        root=root,
        # ``source_init`` aliases the authored init — the canonical write
        # target — so existing read/seed assertions keep working.
        source_init=authored_init,
        authored_init=authored_init,
        root_init=root_init,
        project_name=project_name,
        import_name=import_name,
        seed_labels=("hypothesis", "observation"),
    )


@pytest.fixture
def not_a_gaia_package(tmp_path: Path) -> Path:
    """A directory containing a pyproject without the Gaia type marker."""
    root = tmp_path / "plain"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname = "plain"\nversion = "0.1.0"\n')
    return root
