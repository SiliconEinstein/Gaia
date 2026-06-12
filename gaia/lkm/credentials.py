"""Public credential and readiness helpers for LKM integrations."""

from __future__ import annotations

import contextlib
import os
import tempfile
import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Literal

import tomli_w

_ENV_VAR = "GAIA_LKM_ACCESS_KEY"
_COMPAT_ENV_VAR = "LKM_ACCESS_KEY"
_ENV_VARS = (_ENV_VAR, _COMPAT_ENV_VAR)

LKMCredentialSource = Literal["environment", "file", "none"]


class CredentialPermissionError(Exception):
    """Raised when the credentials file has unsafe permissions."""


LKMCredentialPermissionError = CredentialPermissionError


@dataclass(frozen=True)
class LKMCredentialStatus:
    """Typed readiness status for configured LKM credentials."""

    source: LKMCredentialSource
    present: bool
    masked_tail: str
    path: str
    env_var: str | None = None
    last_validated_at: str | None = None

    def as_dict(self) -> dict[str, object]:
        """Return the legacy dictionary shape used by CLI callers."""
        payload: dict[str, object] = {
            "source": self.source,
            "present": self.present,
            "masked_tail": self.masked_tail,
            "path": self.path,
            "last_validated_at": self.last_validated_at,
        }
        if self.env_var is not None:
            payload["env_var"] = self.env_var
        return payload


def credentials_path() -> Path:
    """Resolve the canonical credentials file path."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "gaia" / "credentials.toml"


def mask_key(key: str | None) -> str:
    """Render a non-revealing display form for ``key``."""
    if not key:
        return "(none)"
    if len(key) <= 4:
        return "****"
    return f"****{key[-4:]}"


def active_lkm_env_var() -> str | None:
    """Return the first configured LKM env var name, if any."""
    for name in _ENV_VARS:
        if os.environ.get(name):
            return name
    return None


def _env_key_source() -> tuple[str, str] | None:
    name = active_lkm_env_var()
    if name is None:
        return None
    return name, str(os.environ[name])


def _ensure_parent(path: Path) -> None:
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError, NotImplementedError):
        parent.chmod(0o700)


def _load_document(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    mode = path.stat().st_mode & 0o777
    if mode != 0o600:
        raise CredentialPermissionError(
            f"Credentials file {path} has mode {mode:o}; expected 600. Fix with: chmod 600 {path}"
        )
    with path.open("rb") as fh:
        return dict(tomllib.load(fh))


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    _ensure_parent(path)
    fd, tmp = tempfile.mkstemp(prefix=".credentials-", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "wb") as fh:
            tomli_w.dump(payload, fh)
        os.chmod(tmp_path, 0o600)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def read_lkm_key() -> str | None:
    """Return the LKM access key from env, then file. ``None`` if unset.

    Env vars ``GAIA_LKM_ACCESS_KEY`` / ``LKM_ACCESS_KEY`` shadow the file
    entirely. If the file exists with unsafe permissions, raises
    ``CredentialPermissionError``.
    """
    env = _env_key_source()
    if env:
        return env[1]
    path = credentials_path()
    doc = _load_document(path)
    lkm = doc.get("lkm")
    if not isinstance(lkm, dict):
        return None
    key = lkm.get("access_key")
    return key if isinstance(key, str) and key else None


def write_lkm_key(key: str, validated_at: datetime) -> None:
    """Persist ``key`` and the validation timestamp to the credentials file.

    Refuses to write when an LKM access-key env var is set in the environment.
    """
    env_var = active_lkm_env_var()
    if env_var:
        raise RuntimeError(
            f"{env_var} is set; refusing to write file-backed credentials. "
            f"Unset the env var to manage credentials via file storage."
        )
    path = credentials_path()
    doc = _load_document(path) if path.exists() else {}
    doc["lkm"] = {
        "access_key": key,
        "last_validated_at": validated_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    _atomic_write(path, doc)


def purge_lkm_key() -> bool:
    """Remove the ``[lkm]`` section. Returns True if something was removed."""
    path = credentials_path()
    if not path.exists():
        return False
    doc = _load_document(path)
    if "lkm" not in doc:
        return False
    del doc["lkm"]
    if not doc:
        path.unlink()
        return True
    _atomic_write(path, doc)
    return True


def credential_status() -> LKMCredentialStatus:
    """Report the active LKM credential source and readiness metadata."""
    env = _env_key_source()
    if env:
        name, key = env
        return LKMCredentialStatus(
            source="environment",
            present=True,
            masked_tail=mask_key(key),
            path="",
            env_var=name,
            last_validated_at=None,
        )
    path = credentials_path()
    if not path.exists():
        return LKMCredentialStatus(
            source="none",
            present=False,
            masked_tail=mask_key(None),
            path=str(path),
            last_validated_at=None,
        )
    doc = _load_document(path)
    lkm = doc.get("lkm")
    if not isinstance(lkm, dict):
        return LKMCredentialStatus(
            source="none",
            present=False,
            masked_tail=mask_key(None),
            path=str(path),
            last_validated_at=None,
        )
    file_key = lkm.get("access_key")
    if not isinstance(file_key, str) or not file_key:
        return LKMCredentialStatus(
            source="none",
            present=False,
            masked_tail=mask_key(None),
            path=str(path),
            last_validated_at=None,
        )
    return LKMCredentialStatus(
        source="file",
        present=True,
        masked_tail=mask_key(file_key),
        path=str(path),
        last_validated_at=str(lkm.get("last_validated_at"))
        if lkm.get("last_validated_at") is not None
        else None,
    )


def lkm_key_status() -> dict[str, object]:
    """Return LKM credential readiness in the legacy dictionary shape."""
    return credential_status().as_dict()


__all__ = [
    "CredentialPermissionError",
    "LKMCredentialPermissionError",
    "LKMCredentialSource",
    "LKMCredentialStatus",
    "active_lkm_env_var",
    "credential_status",
    "credentials_path",
    "lkm_key_status",
    "mask_key",
    "purge_lkm_key",
    "read_lkm_key",
    "write_lkm_key",
]
