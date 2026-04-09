"""End-to-end integration tests for the refs system in compile.py."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_package(
    root: Path,
    name: str,
    module_body: str,
    references_json: dict | None = None,
) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "1.0.0"\n\n'
        f'[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    src_dir = pkg_dir / name.replace("-", "_")
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text(module_body)
    if references_json is not None:
        (pkg_dir / "references.json").write_text(json.dumps(references_json))
    return pkg_dir


def test_compile_errors_on_label_citation_collision(tmp_path: Path) -> None:
    """Per spec §3.5, a key that exists in both the label table and
    references.json must cause a compile error."""
    pkg = _write_package(
        tmp_path,
        name="collision_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'bell_lemma = claim("A lemma about Bell.")\n'
            'main_result = claim("Main result.")\n'
            "deduction(premises=[bell_lemma], conclusion=main_result)\n"
            '__all__ = ["main_result", "bell_lemma"]\n'
        ),
        references_json={
            "bell_lemma": {
                "type": "article-journal",
                "title": "Bell's inequality paper",
            }
        },
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0, f"Expected non-zero exit but got output: {result.output}"
    assert "ambiguous" in result.output.lower()
    assert "bell_lemma" in result.output
