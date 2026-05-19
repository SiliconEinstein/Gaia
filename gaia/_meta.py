"""Build-time + runtime metadata for gaia-lang.

`gaia --version` reads from here. Channel + commit come from build-time
injection (a `gaia/_build_info.py` written by release workflows; absent
in dev) with sensible fallback. ir_schema is "ir-vN+<hash>" — version
is manually bumped on IR field changes; hash auto-tracks any IR-model
serialization change.

Spec ref: PR #620 §6 (version output) + §9 Q5 (ir_schema design,
resolved to "double-write ir-vN+hash" per 协作单 R2 dispatch).
"""

from __future__ import annotations

import hashlib
import importlib
import inspect
import json
import pkgutil
import subprocess
from typing import TYPE_CHECKING

from pydantic import BaseModel

if TYPE_CHECKING:
    pass


# --- Versioned IR schema slot — bump on IR field add/remove/rename --------- #
IR_SCHEMA_VERSION: str = "ir-v1"

# --- Snapshot of computed hash at time of last bump (refresh when bumping) - #
# Pre-push hook (`scripts/check_ir_schema_bump.py`) fires if current
# hash drifts from this. To repair: bump IR_SCHEMA_VERSION + update snapshot.
IR_SCHEMA_SNAPSHOT_HASH: str = "ec83f1ad757a"

# --- Set of IR versions this gaia build accepts (used by gaia-lkm) -------- #
ALLOWED_IR_VERSIONS: frozenset[str] = frozenset({"ir-v1"})


class IncompatibleIRError(Exception):
    """Raised when an IR schema version is outside ALLOWED_IR_VERSIONS."""


def _collect_ir_models() -> list[type[BaseModel]]:
    """Discover Pydantic ``BaseModel`` subclasses defined under ``gaia.engine.ir``.

    Only classes whose ``__module__`` matches the importing module are kept;
    re-exports from elsewhere are skipped. The result is sorted by
    ``<module>.<qualname>`` for deterministic hashing.
    """
    import gaia.engine.ir as ir_pkg

    found: list[type[BaseModel]] = []
    for _finder, name, _ispkg in pkgutil.iter_modules(ir_pkg.__path__):
        module = importlib.import_module(f"gaia.engine.ir.{name}")
        for _attr, obj in inspect.getmembers(module, inspect.isclass):
            if not issubclass(obj, BaseModel) or obj is BaseModel:
                continue
            if obj.__module__ != module.__name__:
                continue
            found.append(obj)

    found.sort(key=lambda c: f"{c.__module__}.{c.__qualname__}")
    return found


def compute_current_ir_hash() -> str:
    """Hash all IR Pydantic models' JSON schemas; 12 hex chars of sha256.

    Deterministic across runs — gathers BaseModel subclasses defined in
    ``gaia/engine/ir/``, sorts by qualified name, concatenates their
    ``model_json_schema()`` outputs (sorted-keys + compact JSON), and hashes.
    """
    parts: list[str] = []
    for cls in _collect_ir_models():
        parts.append(f"{cls.__module__}.{cls.__qualname__}")
        parts.append(json.dumps(cls.model_json_schema(), sort_keys=True, separators=(",", ":")))
    blob = "\0".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:12]


IR_SCHEMA: str = f"{IR_SCHEMA_VERSION}+{compute_current_ir_hash()}"


def check_ir_compat(ir_schema: str) -> None:
    """Raise ``IncompatibleIRError`` if version prefix is not allowed.

    Used by gaia-lkm (and other downstream IR consumers) to gate ingest.
    Hash portion is informational; only the ``ir-vN`` prefix is the
    compatibility contract.
    """
    version = ir_schema.split("+", 1)[0]
    if version not in ALLOWED_IR_VERSIONS:
        raise IncompatibleIRError(
            f"IR schema version {version!r} not in allowed set {sorted(ALLOWED_IR_VERSIONS)}"
        )


def get_channel() -> str:
    """Release channel from build-time injection; 'dev' if not built."""
    try:
        from gaia._build_info import CHANNEL  # type: ignore[import-not-found]
    except ImportError:
        return "dev"
    return str(CHANNEL)


def get_commit() -> str:
    """Build-time commit sha; local git rev or 'unknown' if neither."""
    try:
        from gaia._build_info import COMMIT
    except ImportError:
        pass
    else:
        return str(COMMIT)
    # Fallback to local git
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return "unknown"
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    return "unknown"


def get_library_version() -> str:
    """Library version from package metadata."""
    from importlib.metadata import version

    return version("gaia-lang")
