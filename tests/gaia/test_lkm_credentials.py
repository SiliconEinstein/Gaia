"""Public LKM credential/readiness API tests."""

from __future__ import annotations

import ast
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gaia.lkm.credentials import (
    LKMCredentialStatus,
    credential_status,
    read_lkm_key,
    write_lkm_key,
)

pytestmark = pytest.mark.pr_gate


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the public credential store at a tmp dir and clear env overrides."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.delenv("GAIA_LKM_ACCESS_KEY", raising=False)
    monkeypatch.delenv("LKM_ACCESS_KEY", raising=False)


def test_public_status_reports_file_backed_readiness(tmp_path: Path) -> None:
    write_lkm_key("file-key-1234", datetime(2026, 6, 12, 0, 0, 0, tzinfo=UTC))

    status = credential_status()

    assert status == LKMCredentialStatus(
        source="file",
        present=True,
        masked_tail="****1234",
        path=str(tmp_path / "gaia" / "credentials.toml"),
        env_var=None,
        last_validated_at="2026-06-12T00:00:00Z",
    )
    assert status.as_dict()["source"] == "file"
    assert read_lkm_key() == "file-key-1234"


def test_public_status_ignores_malformed_file_backed_key(tmp_path: Path) -> None:
    credentials = tmp_path / "gaia" / "credentials.toml"
    credentials.parent.mkdir(parents=True)
    credentials.write_text(
        '[lkm]\naccess_key = 12345\nlast_validated_at = "2026-06-12T00:00:00Z"\n',
        encoding="utf-8",
    )
    credentials.chmod(0o600)

    status = credential_status()

    assert status == LKMCredentialStatus(
        source="none",
        present=False,
        masked_tail="(none)",
        path=str(credentials),
        env_var=None,
        last_validated_at=None,
    )
    assert read_lkm_key() is None


def test_public_status_reports_env_backed_readiness(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GAIA_LKM_ACCESS_KEY", "env-key-5678")

    status = credential_status()

    assert status.source == "environment"
    assert status.present is True
    assert status.masked_tail == "****5678"
    assert status.env_var == "GAIA_LKM_ACCESS_KEY"
    assert status.path == ""
    assert status.last_validated_at is None


def test_lkm_client_imports_public_credentials_not_cli_private_module() -> None:
    client_module = Path("gaia/lkm/client.py").read_text()
    tree = ast.parse(client_module)

    imported_modules = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }

    assert "gaia.lkm.credentials" in imported_modules
    assert "gaia.cli._credentials" not in imported_modules
