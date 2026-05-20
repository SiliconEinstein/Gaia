"""File-backed credential store for gaia CLI integrations.

Currently stores a single section ``[lkm]`` holding the Bohrium LKM access
key. Designed to be extensible — other integrations can add their own
sections without touching the lkm shape.

Storage location: ``$XDG_CONFIG_HOME/gaia/credentials.toml`` (falling back
to ``~/.config/gaia/credentials.toml``). The directory is created with
mode 0700 and the file is written with mode 0600 on every write. Reads
refuse a file whose mode is not 0600 and tell the user how to fix.

Environment override: when ``GAIA_LKM_ACCESS_KEY`` is set, the env var
shadows the file completely — no file read, no file write.
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from datetime import datetime
from pathlib import Path

import tomli_w

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


_ENV_VAR = "GAIA_LKM_ACCESS_KEY"


class CredentialPermissionError(Exception):
    """Raised when the credentials file has unsafe permissions."""


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

    Env var ``GAIA_LKM_ACCESS_KEY`` shadows the file entirely. If the file
    exists with unsafe permissions, raises ``CredentialPermissionError``.
    """
    env = os.environ.get(_ENV_VAR)
    if env:
        return env
    path = credentials_path()
    doc = _load_document(path)
    lkm = doc.get("lkm")
    if not isinstance(lkm, dict):
        return None
    key = lkm.get("access_key")
    return key if isinstance(key, str) and key else None


def write_lkm_key(key: str, validated_at: datetime) -> None:
    """Persist ``key`` and the validation timestamp to the credentials file.

    Refuses to write when ``GAIA_LKM_ACCESS_KEY`` is set in the environment.
    """
    if os.environ.get(_ENV_VAR):
        raise RuntimeError(
            f"{_ENV_VAR} is set; refusing to write file-backed credentials. "
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
    """Remove the ``[lkm]`` section. Returns True if something was removed.

    Deletes the file entirely if the document becomes empty.
    """
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


def lkm_key_status() -> dict[str, object]:
    """Report where the LKM access key is sourced from and its display form.

    Returns a dict with keys ``source`` (``"environment"`` / ``"file"`` /
    ``"none"``), ``present`` (bool), ``masked_tail`` (str), ``path`` (str
    when source is file, else empty), ``last_validated_at`` (str or None).
    """
    env = os.environ.get(_ENV_VAR)
    if env:
        return {
            "source": "environment",
            "present": True,
            "masked_tail": mask_key(env),
            "path": "",
            "last_validated_at": None,
        }
    path = credentials_path()
    if not path.exists():
        return {
            "source": "none",
            "present": False,
            "masked_tail": mask_key(None),
            "path": str(path),
            "last_validated_at": None,
        }
    doc = _load_document(path)
    lkm = doc.get("lkm")
    if not isinstance(lkm, dict) or not lkm.get("access_key"):
        return {
            "source": "none",
            "present": False,
            "masked_tail": mask_key(None),
            "path": str(path),
            "last_validated_at": None,
        }
    return {
        "source": "file",
        "present": True,
        "masked_tail": mask_key(str(lkm.get("access_key"))),
        "path": str(path),
        "last_validated_at": lkm.get("last_validated_at"),
    }


__all__ = [
    "CredentialPermissionError",
    "credentials_path",
    "lkm_key_status",
    "mask_key",
    "purge_lkm_key",
    "read_lkm_key",
    "write_lkm_key",
]
