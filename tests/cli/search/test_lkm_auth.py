"""Tests for ``gaia search lkm auth`` (login / status / logout / rotate).

All HTTP is mocked: ``_validate_key`` is patched per test so no real LKM
endpoint is hit. The credential file is redirected to a tmp dir via
``XDG_CONFIG_HOME``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli import _credentials as cred
from gaia.cli.commands.search.lkm import auth as auth_module
from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

_AUTH = ("search", "lkm", "auth")


@pytest.fixture(autouse=True)
def isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the credential store and clear the env override for every test."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)
    return tmp_path / "gaia" / "credentials.toml"


def _patch_validate(monkeypatch: pytest.MonkeyPatch, result: tuple[bool, str]) -> None:
    monkeypatch.setattr(auth_module, "_validate_key", lambda _key: result)


# --------------------------------------------------------------------------- #
# login                                                                       #
# --------------------------------------------------------------------------- #


class TestLogin:
    def test_login_happy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_validate(monkeypatch, (True, "ok"))
        result = runner.invoke(app, [*_AUTH, "login"], input="my-secret-key\n")
        assert result.exit_code == 0, result.output
        assert "validated and stored" in result.output
        assert cred.read_lkm_key() == "my-secret-key"

    def test_login_rejected_exits_3(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_validate(monkeypatch, (False, "access key rejected (HTTP 401/403)"))
        result = runner.invoke(app, [*_AUTH, "login"], input="bad-key\n")
        assert result.exit_code == 3, result.output
        assert "rejected" in result.output
        assert cred.read_lkm_key() is None

    def test_login_blank_key_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # typer.prompt accepts a whitespace string; our .strip() empties it.
        _patch_validate(monkeypatch, (True, "ok"))
        result = runner.invoke(app, [*_AUTH, "login"], input="   \n")
        assert result.exit_code == 4, result.output
        assert "empty access key" in result.output

    def test_login_env_set_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key")
        result = runner.invoke(app, [*_AUTH, "login"], input="x\n")
        assert result.exit_code == 4, result.output
        assert "GAIA_LKM_ACCESS_KEY" in result.output

    def test_login_already_valid_exits_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cred.write_lkm_key("existing-key", datetime.now(UTC))
        _patch_validate(monkeypatch, (True, "ok"))
        result = runner.invoke(app, [*_AUTH, "login"])
        assert result.exit_code == 0, result.output
        assert "already stored" in result.output
        # Untouched.
        assert cred.read_lkm_key() == "existing-key"

    def test_login_force_overwrites(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cred.write_lkm_key("existing-key", datetime.now(UTC))
        _patch_validate(monkeypatch, (True, "ok"))
        result = runner.invoke(app, [*_AUTH, "login", "--force"], input="new-key\n")
        assert result.exit_code == 0, result.output
        assert cred.read_lkm_key() == "new-key"


# --------------------------------------------------------------------------- #
# status                                                                      #
# --------------------------------------------------------------------------- #


class TestStatus:
    def test_status_none(self) -> None:
        result = runner.invoke(app, [*_AUTH, "status"])
        assert result.exit_code == 0, result.output
        assert "source:            none" in result.output
        assert "present:           no" in result.output

    def test_status_file(self) -> None:
        cred.write_lkm_key("k-abcd1234", datetime(2026, 5, 20, 0, 0, 0, tzinfo=UTC))
        result = runner.invoke(app, [*_AUTH, "status"])
        assert result.exit_code == 0, result.output
        assert "file " in result.output
        assert "****1234" in result.output
        assert "2026-05-20T00:00:00Z" in result.output

    def test_status_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key-5678")
        result = runner.invoke(app, [*_AUTH, "status"])
        assert result.exit_code == 0, result.output
        assert "environment GAIA_LKM_ACCESS_KEY" in result.output
        assert "****5678" in result.output
        assert "env-supplied" in result.output


# --------------------------------------------------------------------------- #
# logout                                                                      #
# --------------------------------------------------------------------------- #


class TestLogout:
    def test_logout_removes(self) -> None:
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        result = runner.invoke(app, [*_AUTH, "logout"])
        assert result.exit_code == 0, result.output
        assert "removed" in result.output
        assert cred.read_lkm_key() is None

    def test_logout_idempotent(self) -> None:
        result = runner.invoke(app, [*_AUTH, "logout"])
        assert result.exit_code == 0, result.output
        assert "nothing to remove" in result.output

    def test_logout_env_set_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key")
        result = runner.invoke(app, [*_AUTH, "logout"])
        assert result.exit_code == 4, result.output
        assert "GAIA_LKM_ACCESS_KEY" in result.output


# --------------------------------------------------------------------------- #
# rotate                                                                      #
# --------------------------------------------------------------------------- #


class TestRotate:
    def test_rotate_replaces(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cred.write_lkm_key("old-key", datetime.now(UTC))
        _patch_validate(monkeypatch, (True, "ok"))
        result = runner.invoke(app, [*_AUTH, "rotate"], input="rotated-key\n")
        assert result.exit_code == 0, result.output
        assert cred.read_lkm_key() == "rotated-key"

    def test_rotate_from_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _patch_validate(monkeypatch, (True, "ok"))
        result = runner.invoke(app, [*_AUTH, "rotate"], input="fresh-key\n")
        assert result.exit_code == 0, result.output
        assert cred.read_lkm_key() == "fresh-key"

    def test_rotate_env_set_exits_4(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key")
        result = runner.invoke(app, [*_AUTH, "rotate"], input="x\n")
        assert result.exit_code == 4, result.output
