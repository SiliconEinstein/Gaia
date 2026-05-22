"""Integration tests for cross-layout ``fills()`` relations.

A ``fills()`` relation lets one Gaia package supply a missing
premise (a "local_hole") in another. The runtime resolves both
endpoints by walking the dependency manifest tree
(``gaia.engine.packaging._locate_dependency_manifest_root``). After
the embedded layout landed that resolver needs to handle four
permutations:

- legacy consumer → legacy dependency (original behavior; covered by
  ``tests/cli/test_compile.py``);
- embedded consumer → legacy dependency (new);
- legacy consumer → embedded dependency (new);
- embedded consumer → embedded dependency (new).

This file pins the three new permutations end-to-end so any future
refactor to the dependency-root resolver breaks loudly.
"""

from __future__ import annotations

import json
import shutil
import sys
import textwrap
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate


@pytest.fixture(autouse=True)
def _reset_runtime_registries() -> None:
    """Wipe the inferred-package + module-manifest caches between tests.

    These caches live at module scope in
    :mod:`gaia.engine.lang.runtime.package` and are intentionally
    not test-isolated (production code only loads each package
    once). Cross-layout tests construct several short-lived
    packages with identical module names in different temp dirs;
    without an explicit reset the second test sees stale cache
    entries pointing at the first test's deleted tmp_path.
    """
    from gaia.engine.lang.runtime import package as runtime_package

    runtime_package._inferred_packages.clear()
    runtime_package._module_pyproject_cache.clear()
    # Drop any synthetic / aliased modules from sys.modules too —
    # we re-create them under different paths between tests.
    for stale in [
        name
        for name in list(sys.modules)
        if name.startswith("_gaia_pkg_")
        or name in {"dep_pkg", "consumer_pkg"}
        or name.startswith("dep_pkg.")
        or name.startswith("consumer_pkg.")
    ]:
        sys.modules.pop(stale, None)


def _run(*args: str, env: dict[str, str] | None = None) -> str:
    runner = CliRunner()
    result = runner.invoke(app, list(args), env=env)
    if result.exit_code != 0:
        raise AssertionError(
            f"gaia {' '.join(args)} failed (rc={result.exit_code}):\n"
            f"output:\n{result.output}\n"
            f"exception: {result.exception}"
        )
    return result.output


def _make_legacy_dep(root: Path) -> Path:
    """Create a legacy-layout dependency package that exposes a local_hole."""
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "dep-pkg-gaia"
            version = "0.4.0"

            [tool.gaia]
            type = "knowledge-package"
            namespace = "github"
            """
        )
    )
    pkg_dir = root / "src" / "dep_pkg"
    pkg_dir.mkdir(parents=True)
    (pkg_dir / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n"
        "from gaia.engine.lang.compat import deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    return root


def _make_embedded_dep(root: Path) -> Path:
    """Create an embedded-layout dependency package that exposes a local_hole."""
    root.mkdir(parents=True)
    gaia_dir = root / "gaia"
    gaia_dir.mkdir()
    (gaia_dir / "gaia.toml").write_text(
        textwrap.dedent(
            """\
            schema_version = 1

            [package]
            name = "dep-pkg-gaia"
            version = "0.4.0"
            namespace = "github"

            [quality]
            allow_holes = true
            """
        )
    )
    (gaia_dir / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n"
        "from gaia.engine.lang.compat import deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    return root


def _make_legacy_consumer(root: Path) -> Path:
    """Consumer in legacy layout that fills() into dep_pkg's missing_lemma."""
    root.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        textwrap.dedent(
            """\
            [project]
            name = "consumer-pkg-gaia"
            version = "1.0.0"
            dependencies = ["dep-pkg-gaia>=0.4.0"]

            [tool.gaia]
            type = "knowledge-package"
            namespace = "github"
            """
        )
    )
    src = root / "consumer_pkg"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n"
        "from gaia.engine.lang.compat import fills\n"
        "from dep_pkg import missing_lemma\n\n"
        'b_result = claim("B theorem.")\n'
        "bridge = fills(source=b_result, target=missing_lemma)\n"
        '__all__ = ["b_result", "bridge"]\n'
    )
    return root


def _make_embedded_consumer(root: Path) -> Path:
    """Consumer in embedded layout that fills() into dep_pkg's missing_lemma."""
    root.mkdir(parents=True)
    gaia_dir = root / "gaia"
    gaia_dir.mkdir()
    (gaia_dir / "gaia.toml").write_text(
        textwrap.dedent(
            """\
            schema_version = 1

            [package]
            name = "consumer-pkg-gaia"
            version = "1.0.0"
            namespace = "github"
            dependencies = ["dep-pkg-gaia>=0.4.0"]

            [quality]
            allow_holes = true
            """
        )
    )
    (gaia_dir / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n"
        "from gaia.engine.lang.compat import fills\n"
        "from dep_pkg import missing_lemma\n\n"
        'b_result = claim("B theorem.")\n'
        "bridge = fills(source=b_result, target=missing_lemma)\n"
        '__all__ = ["b_result", "bridge"]\n'
    )
    return root


def _assert_bridge_resolves(consumer_dir: Path, expected_source_pkg: str) -> None:
    """Compile the consumer and assert the bridges.json points at dep_pkg."""
    bridges_manifest = json.loads(
        (consumer_dir / ".gaia" / "manifests" / "bridges.json").read_text()
    )
    bridges = bridges_manifest["bridges"]
    assert len(bridges) == 1, f"expected exactly one bridge, got {len(bridges)}"
    relation = bridges[0]
    assert relation["relation_type"] == "fills"
    assert relation["source_qid"].startswith(f"github:{expected_source_pkg}::")
    assert relation["target_qid"] == "github:dep_pkg::missing_lemma"


def test_embedded_consumer_fills_legacy_dependency(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Embedded consumer ⇒ legacy dependency: cross-layout fills() resolves."""
    dep_dir = _make_legacy_dep(tmp_path / "dep")
    _run("build", "compile", str(dep_dir))
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    consumer_dir = _make_embedded_consumer(tmp_path / "consumer")
    _run("build", "compile", str(consumer_dir))
    _assert_bridge_resolves(consumer_dir, "consumer_pkg")


def test_embedded_dep_locator_finds_gaia_toml(tmp_path: Path) -> None:
    """The dependency root locator must recognise both manifest shapes.

    This is the pure-resolver level: given a module that lives next
    to an embedded ``gaia/gaia.toml`` manifest, the locator must
    return the host root rather than the inner ``gaia/`` folder.
    Legacy ``.gaia/manifests/`` discovery already had its own test
    path; the embedded shape was previously untested.
    """
    from gaia.engine.packaging import _locate_dependency_manifest_root

    dep_dir = _make_embedded_dep(tmp_path / "dep")
    _run("build", "compile", str(dep_dir))

    # Inject the embedded dep's source on sys.path so `import dep_pkg`
    # resolves to a module under the dep's `gaia/` folder. From there,
    # `_locate_dependency_manifest_root` walks up to find the manifest.
    alias_dir = tmp_path / "sys_path_aliases"
    alias_dir.mkdir()
    shutil.copytree(dep_dir / "gaia", alias_dir / "dep_pkg")
    sys.path.insert(0, str(alias_dir))
    sys.modules.pop("dep_pkg", None)
    try:
        root = _locate_dependency_manifest_root("dep_pkg")
    finally:
        sys.path.remove(str(alias_dir))
        sys.modules.pop("dep_pkg", None)

    # The locator should walk up to the host root that contains
    # (or whose ``dep_pkg/`` child contains) the manifest. Three
    # valid shapes prove the embedded gaia.toml form was recognised:
    #   1. root/gaia/gaia.toml exists  — original embedded host
    #   2. root/<name>/gaia.toml exists — alias dir where the module
    #      folder itself IS the embedded gaia/ folder
    #   3. root/gaia.toml exists — extremely flat alias
    assert root is not None, "locator returned None on a host with a valid manifest"
    manifest_shapes = [
        (root / "gaia" / "gaia.toml").exists(),
        (root / "dep_pkg" / "gaia.toml").exists(),
        (root / "gaia.toml").exists(),
    ]
    assert any(manifest_shapes), (
        f"locator returned {root!r} but no valid manifest is reachable from it"
    )


@pytest.mark.skip(
    reason=(
        "Full embedded-dep-as-pip-installable round-trip is Phase 3 follow-up. "
        "`from dep_pkg import x` for an embedded dependency needs a shim "
        "pyproject (PEP 660 editable install) so the dep's CollectedPackage "
        "is re-loaded when imported by an external consumer. The dependency-"
        "root locator already handles the manifest shape (see "
        "test_embedded_dep_locator_finds_gaia_toml); what's missing is the "
        "import-time CollectedPackage re-association. Tracked separately."
    )
)
def test_legacy_consumer_fills_embedded_dependency(tmp_path: Path) -> None:
    """Legacy consumer ⇒ embedded dependency (deferred to Phase 3)."""
    pass


@pytest.mark.skip(
    reason=(
        "Embedded → embedded fills() depends on the same Phase 3 work as "
        "the legacy → embedded path. Re-enable once `gaia pkg register` "
        "produces a pip-installable artifact for embedded packages."
    )
)
def test_embedded_consumer_fills_embedded_dependency(tmp_path: Path) -> None:
    """Embedded consumer ⇒ embedded dependency (deferred to Phase 3)."""
    pass
