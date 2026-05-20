"""Tests for ``gaia pkg migrate`` and the embedded-layout pydantic schema."""

from __future__ import annotations

import json
import shutil
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.engine.layout import detect_layout
from gaia.engine.manifest import GaiaManifestError, load_manifest

pytestmark = pytest.mark.pr_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
GALILEO_LEGACY = REPO_ROOT / "examples" / "galileo-v0-5-gaia"


def _run_gaia(*args: str) -> str:
    runner = CliRunner()
    result = runner.invoke(app, list(args))
    if result.exit_code != 0:
        raise AssertionError(
            f"gaia {' '.join(args)} failed (rc={result.exit_code}):\n"
            f"output:\n{result.output}\n"
            f"exception: {result.exception}"
        )
    return result.output


@pytest.fixture()
def galileo_copy(tmp_path: Path) -> Path:
    """Fresh copy of the real galileo-v0-5-gaia package (legacy layout)."""
    target = tmp_path / "galileo-pkg"
    shutil.copytree(GALILEO_LEGACY, target)
    # Ensure no stale embedded layout from a previous mount.
    for cruft in (".gaia", ".venv", "uv.lock"):
        path = target / cruft
        if path.exists():
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
    return target


def test_migrate_keeps_legacy_by_default(galileo_copy: Path) -> None:
    """Migration leaves ``src/`` and ``pyproject.toml`` intact by default.

    The user can verify IR parity before committing the cleanup, then
    re-run with ``--remove-legacy``.
    """
    _run_gaia("pkg", "migrate", str(galileo_copy))
    assert (galileo_copy / "gaia" / "gaia.toml").exists()
    assert (galileo_copy / "src" / "galileo_v0_5").exists()
    pyproject_text = (galileo_copy / "pyproject.toml").read_text()
    assert "[tool.gaia]" in pyproject_text


def test_migrate_remove_legacy_strips_both(galileo_copy: Path) -> None:
    """``--remove-legacy`` deletes ``src/`` and the ``[tool.gaia]`` block."""
    _run_gaia("pkg", "migrate", str(galileo_copy), "--remove-legacy")
    assert (galileo_copy / "gaia" / "gaia.toml").exists()
    assert not (galileo_copy / "src" / "galileo_v0_5").exists()
    assert "[tool.gaia]" not in (galileo_copy / "pyproject.toml").read_text()


def test_migrate_produces_byte_identical_ir(galileo_copy: Path) -> None:
    """The migrated embedded layout must produce the same IR hash as legacy.

    This is the load-bearing parity check: migration is purely
    organisational; no semantic drift is allowed.
    """
    _run_gaia("build", "compile", str(GALILEO_LEGACY))
    legacy_ir = json.loads((GALILEO_LEGACY / ".gaia" / "ir.json").read_text())

    _run_gaia("pkg", "migrate", str(galileo_copy), "--remove-legacy")
    _run_gaia("build", "compile", str(galileo_copy))
    migrated_ir = json.loads((galileo_copy / ".gaia" / "ir.json").read_text())

    assert migrated_ir["ir_hash"] == legacy_ir["ir_hash"]


def test_migrate_refuses_already_embedded(tmp_path: Path) -> None:
    """Migration only runs on legacy packages — already-embedded hosts get a clear error."""
    host = tmp_path / "embedded"
    host.mkdir()
    _run_gaia("pkg", "mount", str(host), "--name", "demo", "--namespace", "x")

    runner = CliRunner()
    result = runner.invoke(app, ["pkg", "migrate", str(host)])
    assert result.exit_code != 0
    envelope = json.loads(result.output)
    assert envelope["status"] == "error"
    assert "embedded" in envelope["diagnostics"][0]["message"]


def test_migrate_rewrites_absolute_imports(galileo_copy: Path) -> None:
    """``from galileo_v0_5 import x`` in priors.py becomes ``from . import x``."""
    _run_gaia("pkg", "migrate", str(galileo_copy))
    priors_text = (galileo_copy / "gaia" / "priors.py").read_text()
    assert "from . import" in priors_text
    assert "from galileo_v0_5 import" not in priors_text


def test_manifest_rejects_unknown_schema_version(tmp_path: Path) -> None:
    """A manifest claiming a higher schema_version than this lib supports fails fast."""
    manifest = tmp_path / "gaia.toml"
    manifest.write_text(
        textwrap.dedent(
            """\
            schema_version = 99

            [package]
            name = "demo"
            """
        )
    )
    with pytest.raises(GaiaManifestError):
        load_manifest(manifest)


def test_manifest_rejects_bad_package_name(tmp_path: Path) -> None:
    """A package name that doesn't normalise to a Python identifier is rejected."""
    manifest = tmp_path / "gaia.toml"
    manifest.write_text('[package]\nname = "1bad-name"\n')
    with pytest.raises(GaiaManifestError):
        load_manifest(manifest)


def test_manifest_accepts_minimal_manifest(tmp_path: Path) -> None:
    """A bare ``[package].name`` is enough — defaults fill the rest."""
    manifest = tmp_path / "gaia.toml"
    manifest.write_text('[package]\nname = "demo"\n')
    loaded = load_manifest(manifest)
    assert loaded.package.name == "demo"
    assert loaded.package.version == "0.0.0"
    assert loaded.package.namespace == "github"
    assert loaded.quality.allow_holes is True
    assert loaded.projection.mode == "scaffold"


def test_manifest_rejects_unknown_projection_mode(tmp_path: Path) -> None:
    """``projection.mode`` is restricted to spec §5 values."""
    manifest = tmp_path / "gaia.toml"
    manifest.write_text('[package]\nname = "demo"\n\n[projection]\nmode = "freestyle"\n')
    with pytest.raises(GaiaManifestError):
        load_manifest(manifest)


def test_migrate_preserves_pyproject_comments_and_order(tmp_path: Path) -> None:
    """`--remove-legacy` must leave the host's pyproject otherwise untouched.

    Using tomlkit rather than regex means comments, key order in the
    surviving ``[project]`` table, and any other ``[tool.*]`` blocks
    are preserved verbatim.
    """
    host = tmp_path / "legacy-rich"
    host.mkdir()
    pyproject_text = textwrap.dedent(
        """\
        # Top-level pyproject comment.

        [project]
        # The name is intentionally NOT *-gaia in this test.
        name = "demo"
        version = "0.1.0"
        dependencies = ["pydantic>=2", "typer"]

        [tool.gaia]
        type = "knowledge-package"
        namespace = "demo"

        [tool.ruff]
        line-length = 100
        """
    )
    (host / "pyproject.toml").write_text(pyproject_text)
    (host / "src" / "demo").mkdir(parents=True)
    (host / "src" / "demo" / "__init__.py").write_text(
        'from gaia.engine.lang import claim\nc = claim("present")\n__all__ = ["c"]\n'
    )

    _run_gaia("pkg", "migrate", str(host), "--remove-legacy")

    out = (host / "pyproject.toml").read_text()
    assert "[tool.gaia]" not in out
    assert "[tool.ruff]" in out, "non-Gaia tool blocks must survive migration"
    assert "# Top-level pyproject comment." in out, "leading comment must survive"
    assert "# The name is intentionally NOT *-gaia in this test." in out, (
        "comments inside [project] must survive"
    )
    _run_gaia("build", "compile", str(host))
    assert (host / ".gaia" / "ir_hash").exists()


def test_detect_layout_warns_on_dual_presence(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """A host with both embedded and legacy manifests must log a warning."""
    host = tmp_path / "dual"
    host.mkdir()
    (host / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "demo-gaia"
            version = "0.1.0"

            [tool.gaia]
            type = "knowledge-package"
            namespace = "github"
            """
        )
    )
    (host / "src" / "demo").mkdir(parents=True)
    (host / "src" / "demo" / "__init__.py").write_text("")
    (host / "gaia").mkdir()
    (host / "gaia" / "gaia.toml").write_text('[package]\nname = "demo"\n')
    (host / "gaia" / "__init__.py").write_text("")

    with caplog.at_level("WARNING", logger="gaia.engine.layout"):
        layout = detect_layout(host)
    assert layout.kind.value == "embedded"
    assert any("both embedded" in rec.message for rec in caplog.records)
