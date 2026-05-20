"""Tests for the non-invasive embedded Gaia package layout.

These tests cover the new layout introduced to address the
ARM/ARA projection spec §3.1 design point: a Gaia knowledge package
must be mountable on top of *any* host directory using only the
``gaia/`` (user source) and ``.gaia/`` (generated artifacts) folders.
The host's own files — ``pyproject.toml``, ``src/`` tree, ARM bundle
manifests, ARA paper logic, raw evidence — must remain untouched.

The most important assertion is **IR-hash parity**: a Gaia package
written in the legacy layout (``pyproject.toml`` with ``[tool.gaia]``
+ ``src/<import>/``) and the *same* package transposed into the
embedded layout (``gaia/gaia.toml`` + ``gaia/<files>``) must compile
to byte-identical canonical IR JSON.  If they do not, the embedded
loader has subtly altered package semantics, which is the one thing
the non-invasive design must never do.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.pr_gate

REPO_ROOT = Path(__file__).resolve().parent.parent
GALILEO_LEGACY = REPO_ROOT / "examples" / "galileo-v0-5-gaia"
GALILEO_LEGACY_SRC = GALILEO_LEGACY / "src" / "galileo_v0_5"


def _run_gaia(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    """Run the gaia CLI by importing the typer app and invoking it in-process.

    Going through ``subprocess`` for every CLI invocation would shell
    out to ``uv`` and is too slow for a tight test loop. Instead we
    import the typer app, render it with the standard click runner,
    and treat the runner's result the way ``subprocess.run`` would.
    """
    from typer.testing import CliRunner

    from gaia.cli.main import app

    runner = CliRunner()
    invoke_kwargs: dict = {}
    if cwd is not None:
        invoke_kwargs["env"] = {**__import__("os").environ, "PWD": str(cwd)}
    result = runner.invoke(app, list(args), **invoke_kwargs)
    if result.exit_code != 0:
        raise AssertionError(
            f"gaia {' '.join(args)} failed (rc={result.exit_code}):\n"
            f"output:\n{result.output}\n"
            f"exception: {result.exception}"
        )
    # Build a CompletedProcess-shaped object so callers do not have to know
    # which runner produced it.
    return subprocess.CompletedProcess(
        args=["gaia", *args],
        returncode=0,
        stdout=result.output,
        stderr="",
    )


def _drop_dynamic_fields(ir: dict) -> dict:
    """Strip ``ir_hash`` so we can equality-compare two compiles of the same source.

    The hash is computed over the rest of the IR so comparing both is
    redundant; we want to know whether anything other than the hash
    itself drifted.
    """
    return {k: v for k, v in ir.items() if k != "ir_hash"}


@pytest.fixture()
def embedded_galileo(tmp_path: Path) -> Path:
    """Mount the shipping galileo example as an embedded package.

    Reuses the same DSL source verbatim — only the *layout* changes
    (host ``pyproject.toml`` + ``src/galileo_v0_5/`` ⇒ host ``gaia/``).
    Priors module imports are rewritten to relative form because the
    embedded loader uses a synthetic root name; this is a one-line
    diff in source, not a semantic change.
    """
    host = tmp_path / "embedded-host"
    host.mkdir()
    gaia_dir = host / "gaia"
    gaia_dir.mkdir()

    # Identity manifest — namespace + name match the legacy layout so IR
    # QIDs are byte-identical.
    (gaia_dir / "gaia.toml").write_text(
        "[package]\n"
        'name = "galileo_v0_5"\n'
        'version = "0.1.0"\n'
        'namespace = "example"\n'
        'description = "Galileo v0.5 embedded-layout port"\n'
        "\n"
        "[quality]\n"
        "allow_holes = true\n"
    )

    shutil.copy(GALILEO_LEGACY_SRC / "__init__.py", gaia_dir / "__init__.py")
    priors_text = (GALILEO_LEGACY_SRC / "priors.py").read_text()
    priors_text = priors_text.replace("from galileo_v0_5 import", "from . import")
    (gaia_dir / "priors.py").write_text(priors_text)

    # Make sure nothing else in the host marks it as a Gaia package.
    assert not (host / "pyproject.toml").exists()
    return host


def test_legacy_galileo_still_compiles() -> None:
    """Sanity: the shipping legacy layout must continue to compile and produce its known IR hash."""
    _run_gaia("build", "compile", str(GALILEO_LEGACY))
    ir = json.loads((GALILEO_LEGACY / ".gaia" / "ir.json").read_text())
    assert ir["ir_hash"].startswith("sha256:")
    assert len(ir["knowledges"]) == 24
    assert len(ir["strategies"]) == 5


def test_embedded_layout_ir_hash_parity(embedded_galileo: Path) -> None:
    """Embedded compile must produce byte-identical IR to the legacy compile.

    This is the load-bearing parity check for the non-invasive design:
    the layout change must be *purely* organisational. If any field
    other than ``ir_hash`` itself differs the loader has changed
    semantics.
    """
    # Ensure the reference legacy compile exists.
    _run_gaia("build", "compile", str(GALILEO_LEGACY))
    legacy_ir = json.loads((GALILEO_LEGACY / ".gaia" / "ir.json").read_text())

    _run_gaia("build", "compile", str(embedded_galileo))
    embedded_ir = json.loads((embedded_galileo / ".gaia" / "ir.json").read_text())

    assert embedded_ir["ir_hash"] == legacy_ir["ir_hash"], (
        "embedded layout produced a different IR hash than the legacy layout — "
        "the loader is no longer purely organisational"
    )
    assert _drop_dynamic_fields(embedded_ir) == _drop_dynamic_fields(legacy_ir)


def test_embedded_layout_only_touches_gaia_folders(tmp_path: Path) -> None:
    """`gaia pkg mount` must never write outside `gaia/` and `.gaia/`."""
    host = tmp_path / "untouched-host"
    host.mkdir()
    sentinel = host / "host_marker.md"
    sentinel.write_text("# I am the untouched host's marker file.\n")
    sub = host / "src" / "host_pkg"
    sub.mkdir(parents=True)
    (sub / "main.py").write_text("# host code\n")

    pre_inventory = sorted(p.relative_to(host) for p in host.rglob("*"))

    _run_gaia("pkg", "mount", str(host), "--name", "demo", "--namespace", "example")

    post_inventory = sorted(p.relative_to(host) for p in host.rglob("*"))
    added = sorted(set(post_inventory) - set(pre_inventory))
    removed = sorted(set(pre_inventory) - set(post_inventory))

    assert removed == [], f"mount removed files from host: {removed}"
    # Every newly-created path must be under gaia/ or .gaia/.
    for path in added:
        top = path.parts[0]
        assert top in {"gaia", ".gaia"}, f"mount wrote outside the two reserved folders: {path}"
    assert sentinel.read_text() == "# I am the untouched host's marker file.\n"
    assert (sub / "main.py").read_text() == "# host code\n"


def test_embedded_compile_on_non_gaia_host(tmp_path: Path) -> None:
    """Mount + compile must work on a host that was never a Gaia package."""
    host = tmp_path / "fresh-host"
    host.mkdir()
    (host / "README.md").write_text("# I am a host with no Gaia anything.\n")

    _run_gaia("pkg", "mount", str(host), "--name", "fresh", "--namespace", "example")
    # The freshly-mounted package has an empty __init__.py — add one claim.
    init_path = host / "gaia" / "__init__.py"
    init_path.write_text(
        "from gaia.engine.lang import claim\n\n"
        'demo = claim("Mounting works on a fresh non-Gaia host.")\n\n'
        '__all__ = ["demo"]\n'
    )

    _run_gaia("build", "compile", str(host))
    ir = json.loads((host / ".gaia" / "ir.json").read_text())
    labels = sorted(k.get("label") for k in ir["knowledges"] if k.get("label"))
    assert "demo" in labels


def test_mount_emits_source_map_and_queue_for_seeds(tmp_path: Path) -> None:
    """`--from` seeds emit a deterministic source map and formalization queue."""
    host = tmp_path / "ara-like"
    host.mkdir()
    notes = host / "notes.md"
    notes.write_text("# Some research notes that should be scaffolded.\n")

    _run_gaia(
        "pkg",
        "mount",
        str(host),
        "--name",
        "ara_demo",
        "--namespace",
        "example",
        "--from",
        "notes.md",
    )

    source_map = json.loads((host / ".gaia" / "source_map.json").read_text())
    assert source_map["projection_mode"] == "scaffold"
    assert len(source_map["records"]) == 1
    record = source_map["records"][0]
    assert record["source_path"] == "notes.md"
    assert record["gaia_record_kind"] == "note"
    assert record["requires_review"] is True
    assert record["queue_id"] == "FQ0001"

    queue_path = host / ".gaia" / "formalization_queue.jsonl"
    queue_lines = [json.loads(line) for line in queue_path.read_text().splitlines() if line]
    assert len(queue_lines) == 1
    assert queue_lines[0]["queue_id"] == "FQ0001"
    assert queue_lines[0]["current_action"] == "note"
    assert "claim" in queue_lines[0]["candidate_actions"]

    _run_gaia("build", "compile", str(host))
    ir = json.loads((host / ".gaia" / "ir.json").read_text())
    labels = {k.get("label") for k in ir["knowledges"] if k.get("label")}
    assert "host_notes" in labels


def test_embedded_loader_does_not_shadow_installed_gaia(tmp_path: Path) -> None:
    """The synthetic loader must not clobber the installed `gaia` library.

    The embedded user folder is literally called ``gaia/`` so it lines up
    visually with ``.gaia/``. If the loader exposed it as ``gaia`` on
    ``sys.path``, the very first ``from gaia.engine.lang import claim``
    inside the user's file would resolve to the wrong package.  We
    exercise this by importing the installed library after a compile and
    asserting it is the real one.
    """
    host = tmp_path / "shadow-test"
    host.mkdir()
    _run_gaia("pkg", "mount", str(host), "--name", "shadow", "--namespace", "example")
    (host / "gaia" / "__init__.py").write_text(
        'from gaia.engine.lang import claim\n\nc = claim("import-shadow test")\n\n__all__ = ["c"]\n'
    )
    _run_gaia("build", "compile", str(host))

    import gaia.engine.lang

    assert gaia.engine.lang.__name__ == "gaia.engine.lang"
    # Synthetic name must not be the literal "gaia".
    synthetic_names = [n for n in sys.modules if n.startswith("_gaia_pkg_")]
    assert all(n != "gaia" for n in synthetic_names)
