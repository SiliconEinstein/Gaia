"""Interactive LKM access-key onboarding wizard.

Entry points:

* :func:`prompt_lkm_setup` — full guided wizard: show Bohrium URL, prompt for
  the access key, validate it against the API, and persist it to the credentials
  file.  Used by ``gaia search lkm auth login`` and the inline first-run
  intercept.

* :func:`try_interactive_onboarding` — lightweight wrapper that checks whether
  stdin is a TTY before running the wizard.  Called by
  :func:`gaia.cli.commands.search.lkm._shared.run_request` when it catches a
  :class:`~gaia.cli.commands.search.lkm._client.NoAccessKeyError` so the user
  gets guided setup instead of a bare error message.

* :func:`validate_lkm_access_key` — thin probe against the LKM API to confirm a
  key authenticates.  Extracted here so ``auth.py`` can reuse it without
  duplicating the HTTP logic.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime

import typer

from gaia.cli._credentials import credentials_path, write_lkm_key

# NOTE: LKMClient / LKMTransportError are imported lazily inside
# validate_lkm_access_key to avoid a circular import:
#   _onboarding → _client → search/__init__ → auth → _onboarding

_BOHRIUM_URL = "https://www.bohrium.com"

# Business codes that mean the key itself authenticated (even if the specific
# request was rejected on parameters).
_AUTH_VALID_CODES: frozenset[object] = frozenset({0, 290002})

_SETUP_INSTRUCTIONS = (
    f"To get your Bohrium access key:\n"
    f"\n"
    f"  1. Open {_BOHRIUM_URL} in your browser\n"
    f"  2. Sign in or create an account\n"
    f"  3. Go to Account Settings → Access Keys\n"
    f"  4. Create a new key and copy it\n"
)


def validate_lkm_access_key(key: str) -> tuple[bool, str]:
    """Probe the LKM API with *key* to check whether it authenticates.

    Returns ``(True, "ok")`` when the key is accepted, or ``(False, reason)``
    on rejection or transport failure.  A business code of 0 or 290002 is
    treated as valid — the key authenticated even if the ping query itself was
    rejected on parameters.
    """
    # Lazy import to break the circular dependency:
    # _onboarding → _client → search/__init__ → auth → _onboarding
    from gaia.cli.commands.search.lkm._client import LKMClient, LKMTransportError

    try:
        with LKMClient(access_key=key) as client:
            payload = client.request(
                "POST", "/search", json_body={"query": "ping", "limit": 1}
            )
    except LKMTransportError as exc:
        text = str(exc)
        if "HTTP 401" in text or "HTTP 403" in text:
            return False, "access key rejected (HTTP 401/403)"
        return False, f"could not validate: {text}"
    code = payload.get("code")
    if code in _AUTH_VALID_CODES:
        return True, "ok"
    msg = str(payload.get("msg", ""))
    return False, f"access key rejected (code {code}: {msg})"


def prompt_lkm_setup(*, heading: str | None = None) -> None:
    """Guided wizard: display the Bohrium URL, prompt for an access key, validate it, and save.

    Args:
        heading: Optional preamble printed before the setup instructions.
            Pass a non-None string to add context (e.g. "No key configured;
            let's set one up.").

    Raises:
        typer.Exit(3): Access key rejected by the API.
        typer.Exit(4): Empty input or an LKM env var is active (which would
            shadow the credentials file anyway).
    """
    from gaia.cli._credentials import active_lkm_env_var

    env_var = active_lkm_env_var()
    if env_var:
        typer.echo(
            f"Error: {env_var} is set and shadows file-backed credentials. "
            f"Unset it to manage the key via `gaia search lkm auth login`.",
            err=True,
        )
        raise typer.Exit(4)

    if heading:
        typer.echo(heading)
    typer.echo(_SETUP_INSTRUCTIONS)

    key = typer.prompt("Bohrium access key", hide_input=True).strip()
    if not key:
        typer.echo("Error: empty access key; nothing stored.", err=True)
        raise typer.Exit(4)

    typer.echo("Validating access key...", err=True)
    valid, detail = validate_lkm_access_key(key)
    if not valid:
        typer.echo(f"Error: {detail}. Key not stored.", err=True)
        raise typer.Exit(3)

    write_lkm_key(key, datetime.now(UTC))
    path = credentials_path()
    typer.echo("✓ Access key validated and stored.")
    typer.echo(f"  Saved to: {path}")


def try_interactive_onboarding(*, heading: str | None = None) -> bool:
    """Run the onboarding wizard only when stdin is a TTY.

    Returns ``True`` if the wizard ran and the key was stored successfully.
    Returns ``False`` when stdin is not a TTY (non-interactive / CI) — the
    caller should fall back to printing a plain error message.

    Propagates :class:`typer.Exit` if the user enters an invalid or empty key
    so the command exits cleanly rather than retrying with a missing key.

    Args:
        heading: Forwarded verbatim to :func:`prompt_lkm_setup`.
    """
    if not sys.stdin.isatty():
        return False
    prompt_lkm_setup(heading=heading)
    return True


__all__ = [
    "prompt_lkm_setup",
    "try_interactive_onboarding",
    "validate_lkm_access_key",
]
