"""Tests for the file-backed credential store (``gaia.cli._credentials``).

Covers: read/write round-trip, env-var shadowing, 0600 enforcement on
read, purge idempotency + file deletion, and the masking helper. Every
test redirects the store to a tmp dir via ``XDG_CONFIG_HOME`` so no real
``~/.config/gaia/credentials.toml`` is touched.
"""

from __future__ import annotations

import stat
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gaia.cli import _credentials as cred

pytestmark = pytest.mark.pr_gate


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the credential store at a tmp dir and clear the env override."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)


@pytest.fixture
def store(tmp_path: Path) -> Path:
    """The redirected credentials file path (env isolation via ``isolated_env``)."""
    return tmp_path / "gaia" / "credentials.toml"


# --------------------------------------------------------------------------- #
# mask_key                                                                    #
# --------------------------------------------------------------------------- #


class TestMaskKey:
    def test_none(self) -> None:
        assert cred.mask_key(None) == "(none)"

    def test_empty(self) -> None:
        assert cred.mask_key("") == "(none)"

    def test_short(self) -> None:
        assert cred.mask_key("abcd") == "****"

    def test_long(self) -> None:
        assert cred.mask_key("supersecretkey1234") == "****1234"


# --------------------------------------------------------------------------- #
# read / write round-trip                                                     #
# --------------------------------------------------------------------------- #


class TestRoundTrip:
    def test_write_then_read(self, store: Path) -> None:
        cred.write_lkm_key("k-12345", datetime(2026, 5, 20, 12, 0, 0, tzinfo=UTC))
        assert store.exists()
        assert cred.read_lkm_key() == "k-12345"

    def test_write_sets_0600(self, store: Path) -> None:
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        mode = stat.S_IMODE(store.stat().st_mode)
        assert mode == 0o600

    def test_status_file_source(self) -> None:
        cred.write_lkm_key("k-abcd6789", datetime(2026, 5, 20, 0, 0, 0, tzinfo=UTC))
        status = cred.lkm_key_status()
        assert status["source"] == "file"
        assert status["present"] is True
        assert status["masked_tail"] == "****6789"
        assert status["last_validated_at"] == "2026-05-20T00:00:00Z"

    def test_status_none_when_absent(self) -> None:
        status = cred.lkm_key_status()
        assert status["source"] == "none"
        assert status["present"] is False
        assert status["masked_tail"] == "(none)"

    def test_read_none_when_absent(self) -> None:
        assert cred.read_lkm_key() is None


# --------------------------------------------------------------------------- #
# env override                                                                #
# --------------------------------------------------------------------------- #


class TestEnvOverride:
    def test_env_shadows_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cred.write_lkm_key("file-key", datetime.now(UTC))
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key-9999")
        assert cred.read_lkm_key() == "env-key-9999"

    def test_lkm_env_is_accepted_for_existing_tooling(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("LKM_ACCESS_KEY", "legacy-env-key-2468")
        assert cred.read_lkm_key() == "legacy-env-key-2468"

    def test_gaia_env_takes_precedence_over_lkm_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LKM_ACCESS_KEY", "legacy-env-key")
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "gaia-env-key")
        assert cred.read_lkm_key() == "gaia-env-key"

    def test_env_status_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key-9999")
        status = cred.lkm_key_status()
        assert status["source"] == "environment"
        assert status["present"] is True
        assert status["masked_tail"] == "****9999"
        assert status["env_var"] == "GAIA_LKM_ACCESS_KEY"
        assert status["last_validated_at"] is None

    def test_lkm_env_status_source(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LKM_ACCESS_KEY", "legacy-env-key-2468")
        status = cred.lkm_key_status()
        assert status["source"] == "environment"
        assert status["present"] is True
        assert status["masked_tail"] == "****2468"
        assert status["env_var"] == "LKM_ACCESS_KEY"
        assert status["last_validated_at"] is None

    def test_write_refused_when_env_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key")
        with pytest.raises(RuntimeError):
            cred.write_lkm_key("file-key", datetime.now(UTC))

    def test_write_refused_when_lkm_env_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("LKM_ACCESS_KEY", "legacy-env-key")
        with pytest.raises(RuntimeError):
            cred.write_lkm_key("file-key", datetime.now(UTC))


# --------------------------------------------------------------------------- #
# permission enforcement on read                                             #
# --------------------------------------------------------------------------- #


class TestPermissionEnforcement:
    def test_read_refuses_wide_mode(self, store: Path) -> None:
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        store.chmod(0o644)
        with pytest.raises(cred.CredentialPermissionError):
            cred.read_lkm_key()

    def test_status_refuses_wide_mode(self, store: Path) -> None:
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        store.chmod(0o640)
        with pytest.raises(cred.CredentialPermissionError):
            cred.lkm_key_status()


# --------------------------------------------------------------------------- #
# purge                                                                       #
# --------------------------------------------------------------------------- #


class TestPurge:
    def test_purge_removes_and_reports(self) -> None:
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        assert cred.purge_lkm_key() is True
        assert cred.read_lkm_key() is None

    def test_purge_deletes_empty_file(self, store: Path) -> None:
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        cred.purge_lkm_key()
        # The document had only [lkm]; the file should be gone entirely.
        assert not store.exists()

    def test_purge_idempotent(self) -> None:
        assert cred.purge_lkm_key() is False
        cred.write_lkm_key("k-12345", datetime.now(UTC))
        assert cred.purge_lkm_key() is True
        assert cred.purge_lkm_key() is False


# --------------------------------------------------------------------------- #
# path resolution                                                             #
# --------------------------------------------------------------------------- #


def test_credentials_path_uses_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert cred.credentials_path() == tmp_path / "gaia" / "credentials.toml"
