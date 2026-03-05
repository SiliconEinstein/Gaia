"""Tests for gaia publish command."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_publish_server_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["build"])

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"commit_id": "abc123", "status": "pending_review"}
    mock_response.raise_for_status = MagicMock()

    with patch("cli.server_client.httpx.post", return_value=mock_response):
        result = runner.invoke(app, ["publish", "--server"])
    assert result.exit_code == 0
    assert "Published" in result.output or "abc123" in result.output


def test_publish_git_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["build"])

    with patch("cli.commands.publish.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stderr="", stdout="")
        result = runner.invoke(app, ["publish", "--git"])
    assert result.exit_code == 0
