"""Deterministic host-to-Gaia projector (ARM/ARA spec §11).

The projector reads a host directory, classifies it as one of the
known host kinds (ARM bundle, ARA artifact, generic), and projects
each structured source into a stable Gaia DSL fragment plus an audit
record in ``.gaia/source_map.json`` and (when the warrant type is
ambiguous) a follow-up item in ``.gaia/formalization_queue.jsonl``.

The projector is **deterministic**: same input + same projection
policy ⇒ byte-stable generated files. It is also **conservative**:
without a high-confidence rule it emits ``note(...)`` rather than
``derive(...)`` / ``infer(...)`` / ``contradict(...)``. The spec
calls this scaffold mode (§5.1); upgrading scaffold records to
formal warrants is an explicit later step (§5.2 formalized mode).

This package is split across one module per host kind:

- :mod:`gaia.engine.projector.host_kind` — detection
- :mod:`gaia.engine.projector.ara` — spec §7 ARA rules
- :mod:`gaia.engine.projector.arm` — spec §6 ARM rules
- :mod:`gaia.engine.projector.api` — public entry point used by
  ``gaia pkg mount`` / ``gaia build init --embedded`` /
  ``gaia build compile``
"""

from __future__ import annotations

from gaia.engine.projector.api import (
    ProjectionResult,
    SourceMapRecord,
    project_host,
    render_source_map,
)
from gaia.engine.projector.host_kind import HostKind, detect_host_kind

__all__ = [
    "HostKind",
    "ProjectionResult",
    "SourceMapRecord",
    "detect_host_kind",
    "project_host",
    "render_source_map",
]
