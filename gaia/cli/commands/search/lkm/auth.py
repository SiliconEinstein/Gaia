"""``gaia search lkm auth`` — credential lifecycle for the LKM API.

Four verbs:

* ``login``   interactive access-key prompt → validate → persist to file.
* ``status``  report source / presence / masked tail / last-validated time.
* ``logout``  purge the stored key (idempotent).
* ``rotate``  logout (silently) then login.

The access key lives in ``$XDG_CONFIG_HOME/gaia/credentials.toml`` (mode
0600). When ``GAIA_LKM_ACCESS_KEY`` or legacy ``LKM_ACCESS_KEY`` is set it
shadows the file entirely, and the file-mutating verbs refuse rather than
fight the env var.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

import typer

from gaia.cli._credentials import (
    CredentialPermissionError,
    active_lkm_env_var,
    lkm_key_status,
    purge_lkm_key,
    read_lkm_key,
    write_lkm_key,
)
from gaia.cli.commands.search.lkm._client import (
    LKMClient,
    LKMTransportError,
)

_ENV_VAR = "GAIA_LKM_ACCESS_KEY"
_COMPAT_ENV_VAR = "LKM_ACCESS_KEY"

# Business codes that still imply the access key itself authenticated:
#   0       request succeeded
#   290002  request reached the service and was rejected on *parameters*
_AUTH_VALID_CODES = {0, 290002}

auth_app = typer.Typer(
    name="auth",
    help="Manage the LKM access key (login / status / logout / rotate).",
    no_args_is_help=True,
)


def _validate_key(key: str) -> tuple[bool, str]:
    """Probe the API with ``key`` via a cheap ``POST /search``.

    Returns ``(is_valid, detail)``. A code of 0 or 290002 means the key
    authenticated (the request reached the service); a 401/403 transport
    error or an auth-flavoured business code means it did not.
    """
    try:
        with LKMClient(access_key=key) as client:
            payload = client.request("POST", "/search", json_body={"query": "ping", "limit": 1})
    except LKMTransportError as exc:
        text = str(exc)
        if "HTTP 401" in text or "HTTP 403" in text:
            return False, "access key rejected (HTTP 401/403)"
        # Network / decode failure — surface as inconclusive, treat as invalid
        # for login purposes but with a transport-flavoured message.
        return False, f"could not validate: {text}"
    code = payload.get("code")
    if code in _AUTH_VALID_CODES:
        return True, "ok"
    msg = str(payload.get("msg", ""))
    return False, f"access key rejected (code {code}: {msg})"


@auth_app.command(name="login")
def login_command(
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-validate and overwrite even if a valid key exists."),
    ] = False,
) -> None:
    """Prompt for an access key, validate it, and persist to the credentials file."""
    env_var = active_lkm_env_var()
    if env_var:
        typer.echo(
            f"Error: {env_var} is set; it shadows file-backed credentials. "
            f"Unset it to manage the key via `gaia search lkm auth login`.",
            err=True,
        )
        raise typer.Exit(4)

    if not force:
        existing = read_lkm_key()
        if existing:
            valid, _ = _validate_key(existing)
            if valid:
                typer.echo(
                    "A valid access key is already stored. Use "
                    "`gaia search lkm auth rotate` to replace it, or pass --force."
                )
                raise typer.Exit(0)

    key = typer.prompt("Bohrium access key", hide_input=True).strip()
    if not key:
        typer.echo("Error: empty access key; nothing stored.", err=True)
        raise typer.Exit(4)

    valid, detail = _validate_key(key)
    if not valid:
        typer.echo(f"Access key rejected ({detail}). Not stored.", err=True)
        raise typer.Exit(3)

    write_lkm_key(key, datetime.now(UTC))
    typer.echo("Access key validated and stored.")


@auth_app.command(name="status")
def status_command() -> None:
    """Report where the LKM access key is sourced from and its display form."""
    try:
        status = lkm_key_status()
    except CredentialPermissionError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc

    source = status["source"]
    if source == "environment":
        source_line = f"environment {status.get('env_var', _ENV_VAR)}"
        validated = "(env-supplied, no validation timestamp)"
    elif source == "file":
        source_line = f"file {status['path']}"
        validated = str(status["last_validated_at"] or "(never)")
    else:
        source_line = "none"
        validated = "(never)"

    typer.echo(f"source:            {source_line}")
    typer.echo(f"present:           {'yes' if status['present'] else 'no'}")
    typer.echo(f"masked tail:       {status['masked_tail']}")
    typer.echo(f"last validated:    {validated}")
    if not status["present"]:
        typer.echo(
            "\nNo access key configured. Run `gaia search lkm auth login` or set "
            f"{_ENV_VAR} / {_COMPAT_ENV_VAR}."
        )


@auth_app.command(name="logout")
def logout_command() -> None:
    """Purge the stored access key (idempotent)."""
    env_var = active_lkm_env_var()
    if env_var:
        typer.echo(
            f"Error: the active key comes from {env_var}, not the file store. "
            f"Unset {env_var} to remove it.",
            err=True,
        )
        raise typer.Exit(4)
    try:
        removed = purge_lkm_key()
    except CredentialPermissionError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    if removed:
        typer.echo("Stored access key removed.")
    else:
        typer.echo("No stored access key; nothing to remove.")


@auth_app.command(name="rotate")
def rotate_command(
    ctx: typer.Context,
    force: Annotated[
        bool,
        typer.Option("--force", help="Overwrite even if a valid key exists."),
    ] = True,
) -> None:
    """Replace the stored access key: silent logout, then login."""
    env_var = active_lkm_env_var()
    if env_var:
        typer.echo(
            f"Error: {env_var} is set; it shadows file-backed credentials. "
            f"Unset it to rotate the file-stored key.",
            err=True,
        )
        raise typer.Exit(4)
    # Silent purge — ignore the "nothing to remove" case.
    try:
        purge_lkm_key()
    except CredentialPermissionError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(2) from exc
    ctx.invoke(login_command, force=force)


__all__ = ["auth_app"]
