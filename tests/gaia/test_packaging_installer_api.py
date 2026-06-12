"""Public package dependency installer API tests."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest

from gaia.engine.packaging import (
    GaiaPackagingError,
    add_editable_package_dependency,
    resolve_gaia_package_root,
)

pytestmark = pytest.mark.pr_gate


def _write_gaia_package(root: Path, *, name: str) -> None:
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        "dependencies = []\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n',
        encoding="utf-8",
    )


def test_resolve_gaia_package_root_walks_up_from_nested_paths(tmp_path: Path) -> None:
    package = tmp_path / "consumer"
    _write_gaia_package(package, name="consumer-gaia")
    nested = package / "src" / "consumer" / "__init__.py"
    nested.parent.mkdir(parents=True)
    nested.write_text("", encoding="utf-8")

    assert resolve_gaia_package_root(nested) == package


def test_add_editable_package_dependency_runs_uv_from_consumer_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumer = tmp_path / "consumer"
    dependency = tmp_path / "dependency"
    _write_gaia_package(consumer, name="consumer-gaia")
    _write_gaia_package(dependency, name="dependency-gaia")
    (dependency / "src").mkdir()
    calls: list[tuple[list[str], dict[str, Any]]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        calls.append((args, kwargs))
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr("gaia.engine.packaging.subprocess.run", fake_run)

    resolved = add_editable_package_dependency(
        dependency / "src",
        package_root=consumer,
    )

    assert resolved == dependency
    assert calls == [
        (
            ["uv", "add", "--editable", str(dependency)],
            {"cwd": consumer, "text": True, "capture_output": True},
        )
    ]


def test_add_editable_package_dependency_rejects_non_gaia_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    consumer = tmp_path / "consumer"
    not_gaia = tmp_path / "not-gaia"
    _write_gaia_package(consumer, name="consumer-gaia")
    not_gaia.mkdir()
    calls: list[list[str]] = []

    def fake_run(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr("gaia.engine.packaging.subprocess.run", fake_run)

    with pytest.raises(GaiaPackagingError, match="not a Gaia knowledge package"):
        add_editable_package_dependency(not_gaia, package_root=consumer)

    assert calls == []
