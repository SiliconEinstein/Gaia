"""Tests for gaia clean command."""


from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_clean_removes_gaia_dir(tmp_path):
    gaia_dir = tmp_path / ".gaia"
    gaia_dir.mkdir()
    (gaia_dir / "build").mkdir()
    (gaia_dir / "build" / "elaborated.yaml").write_text("test")
    result = runner.invoke(app, ["clean", str(tmp_path)])
    assert result.exit_code == 0
    assert not gaia_dir.exists()


def test_clean_noop_if_no_gaia_dir(tmp_path):
    result = runner.invoke(app, ["clean", str(tmp_path)])
    assert result.exit_code == 0
    assert "No .gaia" in result.output or "nothing" in result.output.lower()
