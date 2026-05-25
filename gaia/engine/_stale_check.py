"""Engine-side helper: detect stale compiled artifacts.

Both ``gaia run infer`` and ``gaia build check`` need to compare a freshly compiled
``LocalCanonicalGraph`` against the persisted ``.gaia/ir_hash`` and
``.gaia/ir.json`` files. The detection logic is identical; only the
reporting style differs (``infer`` exits hard, ``check`` accumulates
diagnostics). This module owns the detection; callers own the reporting.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ArtifactStaleness:
    """Result of comparing persisted artifacts against a freshly compiled graph."""

    ir_hash_path: Path
    ir_json_path: Path
    ir_hash_exists: bool
    ir_json_exists: bool
    ir_hash_stale: bool = False
    ir_json_invalid_reason: str | None = None
    ir_json_hash_mismatch: bool = False
    ir_json_payload_mismatch: bool = False
    stored_ir: dict[str, Any] | None = field(default=None, repr=False)

    @property
    def any_artifact_present(self) -> bool:
        return self.ir_hash_exists or self.ir_json_exists

    @property
    def is_stale(self) -> bool:
        """True if any persisted artifact disagrees with the fresh compile."""
        return (
            self.ir_hash_stale
            or self.ir_json_invalid_reason is not None
            or self.ir_json_hash_mismatch
            or self.ir_json_payload_mismatch
        )


def check_compiled_artifacts(
    pkg_path: Path,
    *,
    ir_hash: str,
    compiled_payload: dict[str, Any] | None = None,
    retries: int = 3,
    retry_delay_s: float = 0.05,
) -> ArtifactStaleness:
    """Compare persisted ``.gaia/ir_hash`` / ``.gaia/ir.json`` against a fresh compile.

    ``compiled_payload`` is optional: when provided, the helper also
    compares the persisted ``ir.json`` byte-payload against it (the
    ``infer`` flow needs this; ``check`` does not).
    """
    for attempt in range(retries + 1):
        result = _check_compiled_artifacts_once(
            pkg_path,
            ir_hash=ir_hash,
            compiled_payload=compiled_payload,
        )
        if not result.is_stale or attempt == retries:
            return result
        time.sleep(retry_delay_s)
    raise AssertionError("unreachable")


def _check_compiled_artifacts_once(
    pkg_path: Path,
    *,
    ir_hash: str,
    compiled_payload: dict[str, Any] | None = None,
) -> ArtifactStaleness:
    """Single-read implementation for :func:`check_compiled_artifacts`."""
    ir_hash_path = pkg_path / ".gaia" / "ir_hash"
    ir_json_path = pkg_path / ".gaia" / "ir.json"
    result = ArtifactStaleness(
        ir_hash_path=ir_hash_path,
        ir_json_path=ir_json_path,
        ir_hash_exists=ir_hash_path.exists(),
        ir_json_exists=ir_json_path.exists(),
    )

    if result.ir_hash_exists:
        stored_hash = ir_hash_path.read_text().strip()
        if stored_hash != ir_hash:
            result.ir_hash_stale = True

    if result.ir_json_exists:
        try:
            stored_ir = json.loads(ir_json_path.read_text())
        except json.JSONDecodeError as exc:
            result.ir_json_invalid_reason = str(exc)
        else:
            result.stored_ir = stored_ir
            if stored_ir.get("ir_hash") != ir_hash:
                result.ir_json_hash_mismatch = True
            if compiled_payload is not None and stored_ir != compiled_payload:
                result.ir_json_payload_mismatch = True

    return result


__all__ = ["ArtifactStaleness", "check_compiled_artifacts"]
