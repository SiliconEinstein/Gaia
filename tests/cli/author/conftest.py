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

_INIT_TEMPLATE = """\
from gaia.engine.lang import claim, derive, equal

hypothesis = claim("Test hypothesis claim.", title="Hypothesis")
observation = claim("Test observation claim.", title="Observation")

__all__ = ["hypothesis", "observation"]
"""


@dataclass
class FixturePackage:
    """Handles for a freshly scaffolded test package."""

    root: Path
    source_init: Path
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
    source_init = src / "__init__.py"
    source_init.write_text(_INIT_TEMPLATE)
    return FixturePackage(
        root=root,
        source_init=source_init,
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
