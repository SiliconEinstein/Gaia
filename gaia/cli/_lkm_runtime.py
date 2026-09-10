"""Shared LKM verb plumbing — index resolution, exit codes, output.

Every Gaia command group that talks to an LKM index (``gaia search lkm``
retrieval, ``gaia extract`` PDF extraction) maps the typed client exceptions
onto one uniform exit-code contract and renders the response envelope as
pretty JSON (stdout or an atomically-written ``--out`` file):

  0  ok            response envelope ``code == 0``
  1  business      non-zero envelope ``code`` (raised as ``LKMError``)
  2  transport     network / non-JSON / HTTP >= 400 (``LKMTransportError``)
  3  no key        no access key configured (``NoAccessKeyError``)
  4  arg           argument validation (raised by the verb before the call)

This module owns that contract so a command group does not have to reach into
another group's private modules to reuse it.
"""

from __future__ import annotations

import json
import os
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, NoReturn

import typer

from gaia.cli._onboarding import try_interactive_onboarding
from gaia.lkm.client import (
    LKMClient,
    LKMError,
    LKMNotFoundError,
    LKMPermissionError,
    LKMTransportError,
    NoAccessKeyError,
)
from gaia.lkm.credentials import CredentialPermissionError
from gaia.lkm.indexes import (
    DEFAULT_LKM_INDEX_ID,
    known_lkm_index_ids,
    lkm_index_base_url,
    normalize_lkm_index_id,
)

_NO_KEY_HELP = (
    "Error: No LKM access key configured. "
    "Run `gaia search lkm auth login` or set GAIA_LKM_ACCESS_KEY."
)


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
    into ``typer.Exit`` codes; see this module's docstring for the table —
    callers should not catch these themselves.
    """
    return _call(
        lambda client: client.request(method, path, json_body=json_body, params=params),
        index_id=index_id,
        server_id=server_id,
    )


def run_multipart_request(
    method: str,
    path: str,
    *,
    files: dict[str, tuple[str, Any, str]] | None = None,
    data: dict[str, Any] | None = None,
    index_id: str = DEFAULT_LKM_INDEX_ID,
    server_id: str | None = None,
) -> dict[str, Any]:
    """Upload a multipart or form body to the LKM API under the same exit contract.

    The caller owns the file objects in ``files`` and is responsible for
    closing them; a retry after interactive onboarding rewinds them first.
    ``files`` may be omitted for content-only submits (form fields in ``data``).
    """

    def call(client: LKMClient) -> dict[str, Any]:
        if files:
            _rewind(files)
        return client.request_multipart(method, path, files=files, data=data)

    return _call(call, index_id=index_id, server_id=server_id)


def _rewind(files: dict[str, tuple[str, Any, str]]) -> None:
    for _, handle, _content_type in files.values():
        seek = getattr(handle, "seek", None)
        if callable(seek):
            seek(0)


def _call(
    perform: Callable[[LKMClient], dict[str, Any]],
    *,
    index_id: str,
    server_id: str | None,
) -> dict[str, Any]:
    requested_index = server_id if server_id is not None else index_id
    normalized_index_id = validate_lkm_index(requested_index)
    base_url = lkm_index_base_url(normalized_index_id)
    assert base_url is not None
    try:
        with LKMClient(base_url=base_url) as client:
            payload = perform(client)
    except NoAccessKeyError as exc:
        # Interactive terminal: run the onboarding wizard and retry once.
        # Non-interactive (CI/pipe): print the plain error and exit.
        onboarded = try_interactive_onboarding(
            heading="\nNo LKM access key configured. Let's set one up first.\n"
        )
        if not onboarded:
            typer.echo(_NO_KEY_HELP, err=True)
            raise typer.Exit(3) from exc
        # Retry with the newly stored key.
        try:
            with LKMClient(base_url=base_url) as client:
                payload = perform(client)
        except (
            NoAccessKeyError,
            LKMPermissionError,
            LKMNotFoundError,
            LKMTransportError,
            CredentialPermissionError,
        ) as retry_exc:
            _exit_for_request_error(retry_exc)
    except (
        LKMPermissionError,
        LKMNotFoundError,
        LKMTransportError,
        CredentialPermissionError,
    ) as exc:
        _exit_for_request_error(exc)

    code = payload.get("code")
    if code != 0:
        msg = _business_message(payload)
        data = payload.get("data")
        err = LKMError(int(code) if isinstance(code, int) else -1, str(msg), data)
        typer.echo(f"Error: {err}", err=True)
        raise typer.Exit(1)
    return payload


def _exit_for_request_error(exc: Exception) -> NoReturn:
    if isinstance(exc, NoAccessKeyError):
        exit_code = 3
    elif isinstance(exc, LKMNotFoundError):
        exit_code = 1
    else:
        exit_code = 2
    typer.echo(f"Error: {exc}", err=True)
    raise typer.Exit(exit_code) from exc


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


def emit(
    payload: dict[str, Any],
    out: Path | None,
    *,
    hint: str | None = None,
    show_hint: bool = True,
) -> None:
    """Render ``payload`` as pretty JSON to ``out`` (atomic) or stdout.

    Hints are Gaia CLI affordances, not part of the LKM payload. They are
    therefore written to stderr so stdout / ``--out`` stay raw LKM JSON.
    """
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if out is None:
        typer.echo(text)
    else:
        _atomic_write(out, text + "\n")
    if show_hint and hint:
        typer.echo(hint, err=True)


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
    "LKMClient",
    "emit",
    "run_multipart_request",
    "run_request",
    "validate_lkm_index",
    "validate_lkm_server",
]
