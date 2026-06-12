"""Alpha-0 packaging contract tests."""

from __future__ import annotations

import tomllib
from pathlib import Path


def test_setuptools_package_find_includes_engine_namespace() -> None:
    """The built wheel must include the new ``gaia.engine.*`` package tree."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    package_includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "gaia.engine*" in package_includes


def test_setuptools_package_find_includes_lkm_namespace() -> None:
    """The built wheel must include the public ``gaia.lkm`` API package."""
    pyproject = tomllib.loads(Path("pyproject.toml").read_text())

    package_includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]

    assert "gaia.lkm*" in package_includes
