"""Host-kind detection for the deterministic projector.

A "host" is whatever directory the user pointed Gaia at. Spec §6 and
§7 define two formal host kinds with structured contents Gaia knows
how to project — ARM bundles and ARA artifacts — plus an implicit
``generic`` bucket for everything else (plain Python projects, raw
paper repos, scratch dirs).

Detection is **purely structural**: we look at well-known files and
directories, not at the manifest's own claim of what it is. This
keeps the detector robust against truncated bundles where
``arm_manifest.json`` was renamed or moved, and lets users override
the detected kind by writing ``[package].host_kind`` explicitly in
``gaia.toml``.
"""

from __future__ import annotations

from enum import StrEnum
from pathlib import Path

__all__ = ["HostKind", "detect_host_kind"]


class HostKind(StrEnum):
    """Discriminator returned by :func:`detect_host_kind`.

    - ``ARM`` — an "agent-ready manuscript" / reproduction bundle.
      Identified by ``arm_manifest.json`` at the host root.
    - ``ARA`` — an "agent research artifact". Identified by the
      presence of ``PAPER.md`` plus a ``logic/`` directory at the
      host root.
    - ``PYTHON_PACKAGE`` — a plain Python project (``pyproject.toml``
      with no Gaia or ARM/ARA markers).
    - ``GENERIC`` — anything else (empty dir, scratch, paper repo with
      no structured logic folder).
    """

    ARM = "arm"
    ARA = "ara"
    PYTHON_PACKAGE = "python-package"
    GENERIC = "generic"


def detect_host_kind(host: Path) -> HostKind:
    """Return the structural host kind for *host*.

    Precedence:

    1. ARM (``arm_manifest.json`` exists) — strongest signal because
       the manifest is an explicit declaration.
    2. ARA (``PAPER.md`` AND ``logic/`` both present) — both markers
       required so that a paper repo with just a README does not get
       mis-classified.
    3. PYTHON_PACKAGE (``pyproject.toml`` present, no ARM/ARA
       markers).
    4. GENERIC (the fallback).
    """
    host = host.resolve()
    if (host / "arm_manifest.json").is_file():
        return HostKind.ARM
    if (host / "PAPER.md").is_file() and (host / "logic").is_dir():
        return HostKind.ARA
    if (host / "pyproject.toml").is_file():
        return HostKind.PYTHON_PACKAGE
    return HostKind.GENERIC
