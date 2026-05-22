"""Public projector API consumed by the CLI.

Spec §9 / §10 define the on-disk audit shapes (``source_map.json``
and ``formalization_queue.jsonl``). This module owns the in-memory
equivalents (``SourceMapRecord`` / ``QueueItem``) plus the
:func:`project_host` dispatcher that picks an ARM / ARA / generic
implementation and returns a :class:`ProjectionResult` describing
all generated Gaia source files and audit entries.

The dispatcher itself never touches the filesystem — it produces a
pure value the caller writes out. The CLI verbs (``gaia pkg mount``,
``gaia build init --embedded``) own the actual writes so the
projector is trivially unit-testable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia.engine.projector.host_kind import HostKind, detect_host_kind

__all__ = [
    "SOURCE_MAP_SCHEMA_VERSION",
    "GeneratedFile",
    "ProjectionResult",
    "QueueItem",
    "SourceMapRecord",
    "project_host",
    "render_source_map",
]


SOURCE_MAP_SCHEMA_VERSION = 1
"""Current schema version emitted by :func:`render_source_map`."""


@dataclass
class SourceMapRecord:
    """One row of ``.gaia/source_map.json`` (spec §9).

    Records the binding from a host source span (file + optional
    anchor) to a generated Gaia DSL label. ``requires_review`` is
    True when the projector emitted a scaffold record that a human
    or agent should later upgrade through the formalization queue.
    """

    source_id: str
    source_path: str
    gaia_label: str
    gaia_record_kind: str
    projection_rule: str
    confidence: str = "programmatic"
    requires_review: bool = False
    source_anchor: str | None = None
    generated_file: str | None = None
    queue_id: str | None = None
    extras: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-ready dict (keys sorted by :func:`render_source_map`)."""
        payload: dict[str, Any] = {
            "source_id": self.source_id,
            "source_path": self.source_path,
            "source_anchor": self.source_anchor,
            "gaia_label": self.gaia_label,
            "gaia_record_kind": self.gaia_record_kind,
            "generated_file": self.generated_file,
            "projection_rule": self.projection_rule,
            "confidence": self.confidence,
            "requires_review": self.requires_review,
        }
        if self.queue_id is not None:
            payload["queue_id"] = self.queue_id
        payload.update(self.extras)
        return payload


@dataclass
class QueueItem:
    """One line of ``.gaia/formalization_queue.jsonl`` (spec §10).

    Records a scaffold projection that needs review before publish.
    The ``candidate_actions`` list constrains the agent / user
    choices to spec-defined upgrade paths (``depends_on → derive``,
    ``candidate_relation → equal/contradict``, etc).
    """

    queue_id: str
    source_id: str
    source_refs: list[str]
    current_gaia_record: str
    current_action: str
    candidate_actions: list[str]
    reason_review_needed: str
    blocking_for_publish: bool = False
    status: str = "open"

    def to_json(self) -> dict[str, Any]:
        """Return a JSON-ready dict matching the spec §10 wire shape."""
        return {
            "queue_id": self.queue_id,
            "source_id": self.source_id,
            "source_refs": list(self.source_refs),
            "current_gaia_record": self.current_gaia_record,
            "current_action": self.current_action,
            "candidate_actions": list(self.candidate_actions),
            "reason_review_needed": self.reason_review_needed,
            "blocking_for_publish": self.blocking_for_publish,
            "status": self.status,
        }


@dataclass
class GeneratedFile:
    """A Gaia DSL file the projector wants the caller to write.

    Paths are **host-relative POSIX** strings (e.g.
    ``"gaia/from_ara/c01.py"``) so the same generated file shape
    flows through unit tests and the CLI without filesystem coupling.
    """

    path: str
    body: str


@dataclass
class ProjectionResult:
    """The full output of :func:`project_host`.

    Combines the host-kind discriminator (so the caller can stamp
    it into ``gaia.toml [package].host_kind``), the generated Gaia
    source files, the source map rows, and the formalization queue
    items.
    """

    host_kind: HostKind
    files: list[GeneratedFile] = field(default_factory=list)
    source_map: list[SourceMapRecord] = field(default_factory=list)
    queue: list[QueueItem] = field(default_factory=list)


def _utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def render_source_map(
    result: ProjectionResult,
    *,
    host: Path | None = None,
    projection_mode: str = "scaffold",
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Render a :class:`ProjectionResult` into the on-disk source-map shape.

    Spec §9 fields kept verbatim:

    - ``schema_version``
    - ``host_kind``
    - ``host_root`` (always ``"."`` because the file lives at
      ``.gaia/source_map.json``)
    - ``projection_mode``
    - ``records`` (one per :class:`SourceMapRecord`)

    The optional ``generated_at`` argument is used by the tests for
    deterministic output; the CLI passes ``None`` and gets a fresh
    UTC timestamp.
    """
    del host  # only the host_root="." convention is recorded; the rest is implicit
    return {
        "schema_version": SOURCE_MAP_SCHEMA_VERSION,
        "host_kind": result.host_kind.value,
        "host_root": ".",
        "projection_mode": projection_mode,
        "generated_at": generated_at or _utc_now_iso(),
        "records": [record.to_json() for record in result.source_map],
    }


def project_host(
    host: Path,
    *,
    seeds: list[Path] | None = None,
    host_kind: HostKind | None = None,
) -> ProjectionResult:
    """Run the deterministic projector over *host*.

    Dispatches by host kind:

    - ARM: :func:`gaia.engine.projector.arm.project_arm` consumes
      ``arm_manifest.json``, ``knowledge/claims.json``, and any
      explicit ``seeds`` (rare for ARM bundles).
    - ARA: :func:`gaia.engine.projector.ara.project_ara` consumes
      ``logic/claims.md`` Cxx blocks, ``evidence/tables/*``, and the
      explicit seeds.
    - PYTHON_PACKAGE / GENERIC: fall back to the seed-only
      ``note(...)`` projector — the same path mount used in alpha.

    When *host_kind* is ``None`` the dispatcher calls
    :func:`detect_host_kind`. Passing it explicitly lets the CLI
    honour a user override.
    """
    resolved_kind = host_kind or detect_host_kind(host)
    seeds_resolved = [s for s in (seeds or []) if s.exists()]

    if resolved_kind is HostKind.ARA:
        from gaia.engine.projector.ara import project_ara

        return project_ara(host, seeds=seeds_resolved)
    if resolved_kind is HostKind.ARM:
        from gaia.engine.projector.arm import project_arm

        return project_arm(host, seeds=seeds_resolved)
    from gaia.engine.projector.generic import project_generic

    return project_generic(host, kind=resolved_kind, seeds=seeds_resolved)
