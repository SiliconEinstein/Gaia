"""Shared verb plumbing for ``gaia search lkm`` — exit codes + output.

Every LKM verb maps the typed client exceptions onto a uniform exit-code
contract and renders the response envelope as pretty JSON (stdout or an
atomically-written ``--out`` file):

  0  ok            response envelope ``code == 0``
  1  business      non-zero envelope ``code`` (raised as ``LKMError``)
  2  transport     network / non-JSON / HTTP >= 400 (``LKMTransportError``)
  3  no key        no access key configured (``NoAccessKeyError``)
  4  arg           argument validation (raised by the verb before the call)
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

import typer

from gaia.cli._credentials import CredentialPermissionError
from gaia.cli.commands.search.lkm._client import (
    LKMClient,
    LKMError,
    LKMTransportError,
    NoAccessKeyError,
)
from gaia.cli.commands.search.lkm._indexes import (
    DEFAULT_LKM_INDEX_ID,
    known_lkm_index_ids,
    lkm_index_base_url,
    normalize_lkm_index_id,
)

# Lexical-channel keyword cap, shared by knowledge / reasoning.
MAX_KEYWORDS = 10
# Per-call id caps.
MAX_OFFSET = 10000
MAX_LIMIT = 100
MAX_PAPER_IDS = 100
MAX_VARIABLE_IDS = 100


def validate_lkm_index(index_id: str, *, option_name: str = "--index") -> str:
    """Validate and normalize the requested LKM index id."""
    normalized = normalize_lkm_index_id(index_id)
    if not normalized:
        typer.echo(f"Error: {option_name} must be non-empty.", err=True)
        raise typer.Exit(4)
    if lkm_index_base_url(normalized) is None:
        known = ", ".join(known_lkm_index_ids())
        typer.echo(
            f"Error: unknown LKM index {index_id!r}. Configured indexes: {known}. "
            f"Set GAIA_LKM_INDEX_<NAME>_URL to add an index URL.",
            err=True,
        )
        raise typer.Exit(4)
    return normalized


def validate_lkm_server(server_id: str) -> str:
    """Compatibility wrapper for the older LKM server option."""
    return validate_lkm_index(server_id, option_name="--server")


def run_request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, Any] | None = None,
    index_id: str = DEFAULT_LKM_INDEX_ID,
    server_id: str | None = None,
) -> dict[str, Any]:
    """Call the LKM API and return the envelope, translating errors to exits.

    Opens an :class:`LKMClient` (loading the access key from env/file),
    performs the request, and raises ``LKMError`` when the envelope reports
    a non-zero ``code``. The verb wrapper translates the typed exceptions
    into ``typer.Exit`` codes; see :func:`run_request`'s docstring for the
    table — callers should not catch these themselves.
    """
    requested_index = server_id if server_id is not None else index_id
    normalized_index_id = validate_lkm_index(requested_index)
    base_url = lkm_index_base_url(normalized_index_id)
    assert base_url is not None
    try:
        with LKMClient(base_url=base_url) as client:
            payload = client.request(method, path, json_body=json_body, params=params)
    except NoAccessKeyError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(3) from exc
    except LKMTransportError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    except CredentialPermissionError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    code = payload.get("code")
    if code != 0:
        msg = _business_message(payload)
        data = payload.get("data")
        err = LKMError(int(code) if isinstance(code, int) else -1, str(msg), data)
        typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(1)
    return payload


def _business_message(payload: dict[str, Any]) -> str:
    """Extract human-readable business errors from live LKM envelopes."""
    for key in ("msg", "message"):
        value = payload.get(key)
        if value:
            return str(value)
    error = payload.get("error")
    if isinstance(error, dict):
        for key in ("msg", "message", "title"):
            value = error.get(key)
            if value:
                return str(value)
        return json.dumps(error, ensure_ascii=False)
    return ""


def emit(payload: dict[str, Any], out: Path | None) -> None:
    """Render ``payload`` as pretty JSON to ``out`` (atomic) or stdout."""
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out is None:
        typer.echo(text)
        return
    _atomic_write(out, text + "\n")


def _atomic_write(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` via a temp file + rename in the same dir."""
    parent = path.parent
    parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".lkm-out-", dir=str(parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


__all__ = [
    "DEFAULT_LKM_INDEX_ID",
    "MAX_KEYWORDS",
    "MAX_LIMIT",
    "MAX_OFFSET",
    "MAX_PAPER_IDS",
    "MAX_VARIABLE_IDS",
    "emit",
    "run_request",
    "validate_lkm_index",
    "validate_lkm_server",
]
