"""End-to-end test: build -> review(mock) -> infer -> publish --local for all 3 packages."""

import json
import shutil
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"

runner = CliRunner()


def _copy_all_fixtures(tmp_path: Path) -> Path:
    """Copy all fixture packages under a single parent dir so sibling deps resolve.

    _load_with_deps() resolves dependencies via ``pkg_path.parent / dep.package``,
    so Newton (depends on Galileo) and Einstein (depends on Newton + Galileo) need
    all packages to be siblings under the same parent directory.
    """
    parent = tmp_path / "packages"
    for pkg_dir in FIXTURES.iterdir():
        if pkg_dir.is_dir():
            shutil.copytree(pkg_dir, parent / pkg_dir.name)
    return parent


def _run_pipeline(pkg_path: Path, db_path: str) -> None:
    """Run build -> review(mock) -> infer -> publish --local."""
    result = runner.invoke(app, ["build", str(pkg_path)])
    assert result.exit_code == 0, f"build failed: {result.output}"

    result = runner.invoke(app, ["review", str(pkg_path), "--mock"])
    assert result.exit_code == 0, f"review failed: {result.output}"

    result = runner.invoke(app, ["infer", str(pkg_path)])
    assert result.exit_code == 0, f"infer failed: {result.output}"

    result = runner.invoke(app, ["publish", str(pkg_path), "--local", "--db-path", db_path])
    assert result.exit_code == 0, f"publish failed: {result.output}"


def test_galileo_full_pipeline(tmp_path):
    """Galileo: build -> review -> infer -> publish produces receipt."""
    parent = _copy_all_fixtures(tmp_path)
    pkg_dir = parent / "galileo_falling_bodies"
    db_path = str(tmp_path / "db")

    _run_pipeline(pkg_dir, db_path)

    # Verify receipt exists
    receipt = json.loads((pkg_dir / ".gaia" / "publish" / "receipt.json").read_text())
    assert receipt["package_id"] == "galileo_falling_bodies"
    assert receipt["stats"]["knowledge_items"] > 0
    assert receipt["stats"]["chains"] > 0


def test_three_packages_no_id_collision(tmp_path):
    """All 3 packages published to same DB should not collide."""
    parent = _copy_all_fixtures(tmp_path)
    db_path = str(tmp_path / "db")

    # Must build in dependency order: Galileo first, then Newton, then Einstein
    galileo_dir = parent / "galileo_falling_bodies"
    newton_dir = parent / "newton_principia"
    einstein_dir = parent / "einstein_gravity"

    _run_pipeline(galileo_dir, db_path)
    _run_pipeline(newton_dir, db_path)
    _run_pipeline(einstein_dir, db_path)

    # Verify all receipts exist and have distinct package_ids
    galileo_receipt = json.loads((galileo_dir / ".gaia" / "publish" / "receipt.json").read_text())
    newton_receipt = json.loads((newton_dir / ".gaia" / "publish" / "receipt.json").read_text())
    einstein_receipt = json.loads((einstein_dir / ".gaia" / "publish" / "receipt.json").read_text())

    assert galileo_receipt["package_id"] == "galileo_falling_bodies"
    assert newton_receipt["package_id"] == "newton_principia"
    assert einstein_receipt["package_id"] == "einstein_gravity"

    # Verify all three wrote to the same DB
    assert galileo_receipt["db_path"] == db_path
    assert newton_receipt["db_path"] == db_path
    assert einstein_receipt["db_path"] == db_path

    # Verify each package produced non-zero knowledge and chains
    for receipt in [galileo_receipt, newton_receipt, einstein_receipt]:
        assert receipt["stats"]["knowledge_items"] > 0
        assert receipt["stats"]["chains"] > 0


def test_idempotent_republish(tmp_path):
    """Publishing same package twice should not error or create duplicates."""
    parent = _copy_all_fixtures(tmp_path)
    pkg_dir = parent / "galileo_falling_bodies"
    db_path = str(tmp_path / "db")

    _run_pipeline(pkg_dir, db_path)

    # Run again -- should succeed (delete-before-insert)
    _run_pipeline(pkg_dir, db_path)

    receipt = json.loads((pkg_dir / ".gaia" / "publish" / "receipt.json").read_text())
    assert receipt["stats"]["knowledge_items"] > 0
    assert receipt["stats"]["chains"] > 0
