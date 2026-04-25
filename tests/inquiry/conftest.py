"""Shared fixtures for inquiry tests — build minimal real Gaia packages."""

from __future__ import annotations

from pathlib import Path

import pytest


def _write_simple_pkg(pkg_dir: Path, name: str = "simple_pkg") -> Path:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / name
    src.mkdir(exist_ok=True)
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, setting, question\n"
        'main_claim = claim("main hypothesis", metadata={"prior": 0.5})\n'
        'iid_setting = setting("data is i.i.d.")\n'
        'rq = question("does the result generalize?")\n'
        '__all__ = ["main_claim", "iid_setting", "rq"]\n',
        encoding="utf-8",
    )
    return pkg_dir


@pytest.fixture
def simple_pkg(tmp_path: Path) -> Path:
    return _write_simple_pkg(tmp_path / "p")


@pytest.fixture
def simple_pkg_factory(tmp_path: Path):
    def _make(name: str = "simple_pkg") -> Path:
        return _write_simple_pkg(tmp_path / name, name=name)

    return _make
