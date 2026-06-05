"""Non-blocking PyPI update-check + upgrade notice for the ``gaia`` CLI.

On invocation the CLI checks PyPI (prereleases included — the published
line is the ``0.5.0aN`` alpha) for a newer ``gaia-lang`` and, if one exists,
prints a one-line upgrade notice to **stderr** — but only when stderr is an
interactive terminal, i.e. a human is there to act on it. The check is
agent-safe by construction:

- Output goes to stderr only (machine-parsed stdout stays clean) and stdin
  is never read (a notice, never an interactive prompt).
- The network call has a short timeout and fails silent — any HTTP error,
  timeout, non-200, malformed JSON, or offline state is swallowed.
- At most one network call *and* one notice per TTL (default 24h), cached
  under the XDG cache dir; the stamp is rewritten after every *attempt* so a
  flaky network can't cause a per-invocation retry storm, and a fresh stamp
  stays silent so an interactive session isn't nagged on every command.
- Several conditions skip the check entirely *before* any network: the
  opt-out env var ``GAIA_NO_UPDATE_CHECK``, ``CI`` set, an unresolvable
  installed version (source checkout), and a **non-interactive stderr** (no
  TTY — so agents, CI, pipes, and redirected output stay silent). The TTY
  gate is the primary agent-safety primitive (cf. npm's update-notifier,
  ``gh``, ``rustup``).

The CLI call site (``gaia/cli/main.py``) wraps :func:`maybe_notify_update`
in a broad ``try/except`` so this feature can never break a command.

Spec: ``docs/specs/2026-06-04-cli-update-check-design.md``.
"""

from __future__ import annotations

import contextlib
import json
import os
import sys
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

from gaia._meta import get_library_version

if TYPE_CHECKING:
    from packaging.version import Version

#: PyPI distribution name (the wheel ships both CLI and library).
_DIST_NAME = "gaia-lang"
#: PyPI JSON metadata endpoint for the distribution.
_PYPI_URL = f"https://pypi.org/pypi/{_DIST_NAME}/json"
#: Network timeout for the PyPI GET. ``httpx.Timeout(1.5, connect=0.75)`` sets
#: **per-phase** bounds — connect 0.75s and read/write/pool 1.5s each — not a
#: single total wall-clock deadline (a slow trickle could run ~0.75s connect +
#: ~1.5s read). A bare float would apply the same value to every phase, so cap
#: connect tightly: a hung connect (the common stall) bails in 0.75s while the
#: read stays bounded at 1.5s. Fine for a once-daily, fail-silent check.
_HTTP_TIMEOUT = httpx.Timeout(1.5, connect=0.75)
#: Default throttle window between network checks, in seconds (24h).
_DEFAULT_TTL_S = 24 * 60 * 60

#: Opt-out env var (truthy → skip entirely).
_OPT_OUT_ENV = "GAIA_NO_UPDATE_CHECK"
#: TTL override env var (integer seconds; for tests + power users).
_TTL_ENV = "GAIA_UPDATE_CHECK_TTL"

#: A fetcher returns the parsed PyPI JSON payload, or ``None`` on any failure.
Fetcher = Callable[[], "dict[str, object] | None"]


def _is_truthy(value: str | None) -> bool:
    """Treat any non-empty, non-falsey string as truthy for opt-out flags."""
    if value is None:
        return False
    return value.strip().lower() not in ("", "0", "false", "no", "off")


def cache_path() -> Path:
    """Resolve the throttle-stamp path under the XDG cache dir.

    ``$XDG_CACHE_HOME/gaia/update-check.json`` (fallback
    ``~/.cache/gaia/update-check.json``) — cache, not config, so it follows
    ``XDG_CACHE_HOME`` (cf. ``_credentials`` which uses ``XDG_CONFIG_HOME``).
    """
    xdg = os.environ.get("XDG_CACHE_HOME")
    base = Path(xdg) if xdg else Path.home() / ".cache"
    return base / "gaia" / "update-check.json"


def _ttl_seconds() -> int:
    """Throttle window in seconds; ``GAIA_UPDATE_CHECK_TTL`` overrides the default."""
    raw = os.environ.get(_TTL_ENV)
    if raw is None:
        return _DEFAULT_TTL_S
    try:
        ttl = int(raw)
    except ValueError:
        return _DEFAULT_TTL_S
    return ttl if ttl >= 0 else _DEFAULT_TTL_S


def _read_stamp(path: Path) -> dict[str, object] | None:
    """Read the cached stamp, or ``None`` if absent / unreadable / malformed."""
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _atomic_write(path: Path, payload: dict[str, object]) -> None:
    """Atomically write ``payload`` as JSON (mirrors ``_credentials._atomic_write``).

    Best-effort: any filesystem error is swallowed by the caller so an
    unwritable cache dir never breaks the check.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".update-check-", dir=str(path.parent))
    tmp_path = Path(tmp)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(payload, fh)
        os.replace(tmp_path, path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise


def _write_stamp(path: Path, latest: str | None) -> None:
    """Rewrite the throttle stamp after an attempt; failures are swallowed."""
    payload: dict[str, object] = {"checked_at": time.time(), "latest": latest}
    # Unwritable cache dir → can't throttle, but never error.
    with contextlib.suppress(OSError):
        _atomic_write(path, payload)


def _default_fetcher() -> dict[str, object] | None:
    """Fetch + parse the PyPI JSON; ``None`` on any HTTP/decode failure.

    Mirrors the ``_registry`` fail-silent pattern (``try/except
    httpx.HTTPError``) with a short timeout so the check never hangs.
    """
    try:
        resp = httpx.get(_PYPI_URL, timeout=_HTTP_TIMEOUT)
    except httpx.HTTPError:
        # httpx.TimeoutException subclasses HTTPError → connect/read timeouts
        # are caught here and fail silent.
        return None
    if resp.status_code != 200:
        return None
    try:
        data = resp.json()
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def latest_pypi_version(payload: dict[str, object]) -> str | None:
    """Pick the max version from a PyPI JSON payload, prereleases included.

    Scans **all keys** of the ``releases`` object — not ``info.version``,
    which is the latest *stable* and would miss the prerelease line. Skips
    fully-yanked releases (every file ``yanked``); orders by PEP 440 via
    ``packaging.version.Version`` (never hand-rolled). Returns ``None`` when
    no usable version is present.
    """
    from packaging.version import InvalidVersion, Version

    releases = payload.get("releases")
    if not isinstance(releases, dict):
        return None

    best: Version | None = None
    best_raw: str | None = None
    for raw, files in releases.items():
        if not isinstance(raw, str):
            continue
        # Skip a release whose every file is yanked. An empty file list (a
        # registered-but-unuploaded version) is treated as present-but-skippable.
        if isinstance(files, list):
            if not files:
                continue
            if all(isinstance(f, dict) and f.get("yanked") for f in files):
                continue
        try:
            ver = Version(raw)
        except InvalidVersion:
            continue
        if best is None or ver > best:
            best = ver
            best_raw = raw
    return best_raw


def _upgrade_command() -> str:
    """Best-effort install-method detection → a tailored, prerelease-allowing upgrade hint.

    All returned commands allow prereleases (``--pre`` / ``--prerelease=allow``)
    so they stay on the published alpha line. When the method is unclear, a
    generic fallback shows both the pip and uv-tool forms.
    """
    exe = Path(sys.executable).resolve()
    prefix = Path(sys.prefix).resolve()
    exe_str = str(exe)

    # uv tool install layout: executables/venv live under .../uv/tools/<name>/...
    if "uv/tools" in exe_str.replace(os.sep, "/") or "uv/tools" in str(prefix).replace(os.sep, "/"):
        return f"uv tool upgrade --prerelease=allow {_DIST_NAME}"

    # uv-managed project venv: a .venv with a sibling pyproject.toml / uv.lock.
    venv_root = prefix
    if venv_root.name == ".venv":
        project = venv_root.parent
        if (project / "pyproject.toml").exists() or (project / "uv.lock").exists():
            return f"uv add --prerelease=allow {_DIST_NAME}@latest"

    # Inside a virtualenv but not obviously uv-managed → pip with --pre.
    if sys.prefix != getattr(sys, "base_prefix", sys.prefix):
        return f"pip install -U --pre {_DIST_NAME}"

    # Unsure → show both common forms.
    return (
        f"pip install -U --pre {_DIST_NAME}   (or: uv tool upgrade --prerelease=allow {_DIST_NAME})"
    )


def _stderr_is_interactive() -> bool:
    """True iff stderr exists, is open, and is a TTY — i.e. a human is watching.

    The notice is only useful to a person who can act on it; agents, CI, pipes,
    and redirected stderr have no TTY, so the check stays silent for them. This
    is the primary agent-safety gate (cf. npm's update-notifier, ``gh``).
    """
    stream = sys.stderr
    if stream is None:
        return False
    if getattr(stream, "closed", False):
        return False
    isatty = getattr(stream, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        # A broken stream that raises on isatty() → treat as non-interactive.
        return False


def maybe_notify_update(*, fetcher: Fetcher | None = None) -> None:
    """Check PyPI for a newer ``gaia-lang`` and print an upgrade notice to stderr.

    Non-blocking, fail-silent, and agent-safe: the notice only fires when
    stderr is an interactive terminal, and at most once per TTL (both the
    network call and the notice). All skip conditions are evaluated before any
    network access. ``fetcher`` is injectable for tests; production uses
    :func:`_default_fetcher`.

    Args:
        fetcher: Optional override that returns the PyPI JSON payload (or
            ``None`` on failure) instead of hitting the network.
    """
    from packaging.version import InvalidVersion, Version

    # --- Skip conditions (before any network) ----------------------------- #
    if _is_truthy(os.environ.get(_OPT_OUT_ENV)):
        return
    if os.environ.get("CI"):
        return
    if not _stderr_is_interactive():
        return

    try:
        installed_raw = get_library_version()
    except Exception:
        # Package metadata not resolvable (e.g. an un-installed source checkout).
        return
    try:
        installed = Version(installed_raw)
    except InvalidVersion:
        return

    # --- Throttle: skip BOTH the network and the notice if the stamp is fresh.
    # The notice fires at most once per TTL — on the refresh below, not on every
    # invocation — so an interactive session isn't nagged on each command.
    path = cache_path()
    ttl = _ttl_seconds()
    stamp = _read_stamp(path)
    latest_raw: str | None = None
    if stamp is not None:
        checked_at = stamp.get("checked_at")
        if isinstance(checked_at, (int, float)) and (time.time() - checked_at) < ttl:
            return

    # --- Network attempt (always re-stamp afterwards) ---------------------- #
    fetch = fetcher if fetcher is not None else _default_fetcher
    payload = fetch()
    if payload is not None:
        latest_raw = latest_pypi_version(payload)
    _write_stamp(path, latest_raw)
    _emit_if_newer(installed, latest_raw)


def _emit_if_newer(installed: Version, latest_raw: str | None) -> None:
    """Print the upgrade notice to stderr iff ``latest_raw`` outranks ``installed``."""
    from packaging.version import InvalidVersion, Version

    if latest_raw is None:
        return
    try:
        latest = Version(latest_raw)
    except InvalidVersion:
        return
    if latest <= installed:
        return
    notice = (
        f"{_DIST_NAME} {latest} is available (you have {installed}).\n"
        f"Upgrade:  {_upgrade_command()}\n"
        f"(silence: {_OPT_OUT_ENV}=1)"
    )
    print(notice, file=sys.stderr)


__all__ = [
    "cache_path",
    "latest_pypi_version",
    "maybe_notify_update",
]
