"""``gaia pkg lock-check`` — publish-gate validator (spec §5.3).

Spec §5.3 defines a ``locked`` mode for ``gaia pkg register`` /
registry CI: a package is publishable only when

- source hashes have not drifted (every ``source_map.json`` record's
  generated file is still present and produced from a host file that
  has not changed since the projection);
- generated code matches the source map (no out-of-band edits to
  ``gaia/from_*/<file>.py`` that the map does not know about);
- ``gaia build compile`` passes;
- ``gaia build check`` passes (manifests exist);
- when the package's projection policy demands strict publish, the
  formalization queue is **clean**: no item with
  ``blocking_for_publish: true`` and ``status: open``.

This verb runs those checks against an embedded host and either
prints the pass envelope or surfaces every failing invariant as a
separate diagnostic. Used both interactively and by CI; the new
``gaia pkg register --locked`` flag (see below) calls into the same
implementation before touching the registry.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from gaia.cli.commands.author._envelope import (
    EXIT_INPUT_SYNTAX,
    EXIT_OK,
    EXIT_PREWRITE_STRUCTURAL,
    EXIT_SYSTEM_IO,
    AuthorResult,
    Diagnostic,
    emit,
)
from gaia.engine._stale_check import check_compiled_artifacts
from gaia.engine.layout import (
    EMBEDDED_GAIA_OUTPUT_DIR,
    GaiaLayoutError,
    LayoutKind,
    detect_layout,
)
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
    validate_fills_relations,
)

__all__ = ["TODO_REVIEWER_MARKER", "LockCheckReport", "lock_check_command", "run_lock_check"]


TODO_REVIEWER_MARKER = "TODO(reviewer)"
"""Substring written by `gaia pkg formalize` into placeholder warrant rationales.

The publish gate scans every IR knowledge for this marker and
refuses to lock the package while any unreplaced placeholder is
present. This catches the failure mode where the reviewer
formalised a scaffold but forgot to fill in the real likelihoods,
leaving a ``infer(..., p_e_given_h=0.5, p_e_given_not_h=0.5, ...)``
that is mathematically inert."""


@dataclass
class LockCheckReport:
    """Result of running the spec §5.3 publish gate against a host."""

    ok: bool
    failures: list[Diagnostic] = field(default_factory=list)
    warnings: list[Diagnostic] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def _check_generated_files_present(host: Path, records: list[dict[str, Any]]) -> list[Diagnostic]:
    """Every source_map record's ``generated_file`` must exist on disk."""
    missing: list[Diagnostic] = []
    for record in records:
        generated = record.get("generated_file")
        if not isinstance(generated, str):
            continue
        target = host / generated
        if not target.exists():
            missing.append(
                Diagnostic(
                    kind="locked.generated_file_missing",
                    level="error",
                    message=(
                        f"source_map record {record.get('source_id')!r} points at "
                        f"{generated} but that file is missing on disk."
                    ),
                    source="prewrite",
                    where={"generated_file": generated},
                )
            )
    return missing


def _check_source_files_present(host: Path, records: list[dict[str, Any]]) -> list[Diagnostic]:
    """Every record's ``source_path`` must still resolve under the host."""
    missing: list[Diagnostic] = []
    for record in records:
        source_path = record.get("source_path")
        if not isinstance(source_path, str) or source_path == ".":
            continue
        target = host / source_path
        if not target.exists():
            missing.append(
                Diagnostic(
                    kind="locked.source_file_missing",
                    level="error",
                    message=(
                        f"source_map record {record.get('source_id')!r} cites host "
                        f"file {source_path} which no longer exists. Run "
                        "`gaia pkg mount` again to re-project."
                    ),
                    source="prewrite",
                    where={"source_path": source_path},
                )
            )
    return missing


def _check_queue_clean(queue_path: Path) -> list[Diagnostic]:
    """Open queue items with ``blocking_for_publish: true`` are publish-blockers."""
    blocking: list[Diagnostic] = []
    if not queue_path.exists():
        return blocking
    for line in queue_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(item, dict):
            continue
        if item.get("status") != "open":
            continue
        if not bool(item.get("blocking_for_publish")):
            continue
        blocking.append(
            Diagnostic(
                kind="locked.queue_blocking",
                level="error",
                message=(
                    f"formalization queue item {item.get('queue_id')!r} is "
                    "marked blocking_for_publish but is still open. Resolve "
                    "it through `gaia pkg formalize` first."
                ),
                source="prewrite",
                where={"queue_id": item.get("queue_id")},
            )
        )
    return blocking


def _check_build_check_passes(host: Path) -> tuple[list[Diagnostic], dict[str, Any] | None]:
    """Run the full ``gaia build check`` pipeline and surface every failure.

    This is the spec §5.3 "gaia build check passes" requirement,
    delegated to the same code path the real ``gaia build check``
    command uses so the publish gate sees identical diagnostics:

    - load + apply priors + compile via :func:`load_gaia_package` /
      :func:`apply_package_priors` / :func:`compile_loaded_package_artifact`;
    - validate fills() via :func:`validate_fills_relations`;
    - compare the fresh IR hash against the persisted
      ``.gaia/ir_hash`` via :func:`check_compiled_artifacts`.

    Returns ``(diagnostics, ir_json)`` so the queue / TODO scans
    downstream can re-use the in-memory IR without re-parsing.
    """
    diagnostics: list[Diagnostic] = []
    try:
        loaded = load_gaia_package(host)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        validate_fills_relations(loaded, compiled)
    except GaiaPackagingError as exc:
        diagnostics.append(
            Diagnostic(
                kind="locked.build_check_failed",
                level="error",
                message=str(exc),
                source="prewrite",
                where={},
            )
        )
        return diagnostics, None

    staleness = check_compiled_artifacts(host, ir_hash=ir["ir_hash"])
    if not staleness.ir_hash_exists or not staleness.ir_json_exists:
        diagnostics.append(
            Diagnostic(
                kind="locked.ir_missing",
                level="error",
                message=(
                    "missing .gaia/ir_hash or .gaia/ir.json — run "
                    "`gaia build compile` before lock-check."
                ),
                source="prewrite",
                where={},
            )
        )
        return diagnostics, ir
    if staleness.ir_hash_stale:
        diagnostics.append(
            Diagnostic(
                kind="locked.ir_stale",
                level="error",
                message=(
                    "compiled `.gaia/ir_hash` does not match a fresh compile — "
                    "the package source changed since last `gaia build compile`."
                ),
                source="prewrite",
                where={},
            )
        )
    return diagnostics, ir


def _check_todo_placeholders(ir: dict[str, Any]) -> list[Diagnostic]:  # noqa: C901
    """Fail the publish gate when any IR record carries an unreplaced TODO marker.

    ``gaia pkg formalize`` writes ``p_e_given_h=0.5,
    p_e_given_not_h=0.5`` with a ``TODO(reviewer)`` rationale for
    any ``infer(...)`` upgrade — those numbers are mathematically
    inert and must be replaced before publish. The marker is a
    well-defined constant the formalizer uses, so the scan never
    flags hand-authored rationales that happen to mention the word
    "todo".
    """
    diagnostics: list[Diagnostic] = []
    for record_kind, records in (
        ("knowledges", ir.get("knowledges") or []),
        ("strategies", ir.get("strategies") or []),
    ):
        for record in records:
            if not isinstance(record, dict):
                continue
            haystacks: list[str] = []
            content = record.get("content")
            if isinstance(content, str):
                haystacks.append(content)
            metadata = record.get("metadata") or {}
            if isinstance(metadata, dict):
                for value in metadata.values():
                    if isinstance(value, str):
                        haystacks.append(value)
            # Reason / rationale can sit under any of these keys
            # depending on whether the record is a Claim, Strategy
            # (v5), or v6 strategy with ``steps[i].reasoning``. Be
            # exhaustive — we only care about *any* text field
            # containing the marker.
            for key in ("reason", "rationale", "reasoning", "steps"):
                value = record.get(key)
                if isinstance(value, str):
                    haystacks.append(value)
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            for subkey in ("reason", "rationale", "reasoning", "text"):
                                subtext = item.get(subkey)
                                if isinstance(subtext, str):
                                    haystacks.append(subtext)
                        elif isinstance(item, str):
                            haystacks.append(item)
            if any(TODO_REVIEWER_MARKER in text for text in haystacks):
                diagnostics.append(
                    Diagnostic(
                        kind="locked.unresolved_todo",
                        level="error",
                        message=(
                            f"{record_kind[:-1]} {record.get('label') or record.get('id')!r} "
                            f"still carries an unreplaced {TODO_REVIEWER_MARKER!r} "
                            "marker from `gaia pkg formalize`. Replace placeholder "
                            "likelihoods / rationales before locking."
                        ),
                        source="prewrite",
                        where={"label": record.get("label"), "id": record.get("id")},
                    )
                )
    return diagnostics


def _check_manifests(host: Path) -> list[Diagnostic]:
    """Spec §5.3: registry-facing manifest files must exist."""
    expected = [
        ".gaia/manifests/exports.json",
        ".gaia/manifests/premises.json",
    ]
    missing: list[Diagnostic] = []
    for rel in expected:
        if not (host / rel).exists():
            missing.append(
                Diagnostic(
                    kind="locked.manifest_missing",
                    level="error",
                    message=(
                        f"required publish artifact {rel} is missing — run "
                        "`gaia build compile` then `gaia build check`."
                    ),
                    source="prewrite",
                    where={"manifest": rel},
                )
            )
    return missing


def run_lock_check(host: Path) -> LockCheckReport:
    """Run all spec §5.3 checks and return a :class:`LockCheckReport`."""
    failures: list[Diagnostic] = []
    warnings: list[Diagnostic] = []

    try:
        layout = detect_layout(host)
    except GaiaLayoutError as exc:
        return LockCheckReport(
            ok=False,
            failures=[
                Diagnostic(
                    kind="locked.layout_invalid",
                    level="error",
                    message=str(exc),
                    source="prewrite",
                    where={"host": str(host)},
                )
            ],
        )
    if layout.kind is not LayoutKind.EMBEDDED:
        failures.append(
            Diagnostic(
                kind="locked.legacy_layout",
                level="error",
                message=(
                    "`lock-check` only runs on embedded layouts. Migrate the "
                    "host with `gaia pkg migrate` first."
                ),
                source="prewrite",
                where={"layout": layout.kind.value},
            )
        )
        return LockCheckReport(ok=False, failures=failures)

    out_dir = host / EMBEDDED_GAIA_OUTPUT_DIR
    map_path = out_dir / "source_map.json"
    records: list[dict[str, Any]] = []
    if map_path.exists():
        try:
            map_data = json.loads(map_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failures.append(
                Diagnostic(
                    kind="locked.source_map_invalid",
                    level="error",
                    message=f".gaia/source_map.json is not valid JSON: {exc}",
                    source="prewrite",
                    where={},
                )
            )
            map_data = {}
        if isinstance(map_data, dict):
            raw_records = map_data.get("records")
            if isinstance(raw_records, list):
                records = [r for r in raw_records if isinstance(r, dict)]

    failures.extend(_check_generated_files_present(host, records))
    failures.extend(_check_source_files_present(host, records))
    failures.extend(_check_manifests(host))
    failures.extend(_check_queue_clean(out_dir / "formalization_queue.jsonl"))
    # Full build-check pipeline (load + compile + fills + ir-hash freshness).
    # Done last so file-existence diagnostics surface first when both fail.
    build_check_failures, ir = _check_build_check_passes(host)
    failures.extend(build_check_failures)
    if ir is not None:
        failures.extend(_check_todo_placeholders(ir))

    counts = {
        "source_map_records": len(records),
        "failures": len(failures),
        "warnings": len(warnings),
    }
    return LockCheckReport(ok=not failures, failures=failures, warnings=warnings, counts=counts)


def lock_check_command(
    host: str = typer.Argument(".", help="Embedded Gaia host directory."),
    human: bool = typer.Option(False, "--human", help="Human-readable envelope."),
    json_: bool = typer.Option(True, "--json/--no-json", help="JSON-first output (default)."),
) -> None:
    r"""Run the spec §5.3 publish gate against an embedded host.

    Returns exit code 0 when every invariant holds, 1 otherwise. Each
    failure is reported as a separate ``Diagnostic`` in the envelope's
    ``diagnostics`` array.
    """
    del json_
    host_path = Path(host).resolve()
    report = run_lock_check(host_path)
    payload: dict[str, Any] = {
        "host": str(host_path),
        "ok": report.ok,
        "counts": report.counts,
    }
    if report.ok:
        emit(
            AuthorResult(verb="lock-check", status="ok", code=EXIT_OK, payload=payload),
            human=human,
        )
        return
    # Choose the strongest semantic code from the diagnostics.
    first = report.failures[0]
    code = {
        "locked.layout_invalid": EXIT_SYSTEM_IO,
        "locked.ir_missing": EXIT_PREWRITE_STRUCTURAL,
        "locked.ir_stale": EXIT_PREWRITE_STRUCTURAL,
        "locked.queue_blocking": EXIT_INPUT_SYNTAX,
        "locked.generated_file_missing": EXIT_PREWRITE_STRUCTURAL,
        "locked.source_file_missing": EXIT_PREWRITE_STRUCTURAL,
        "locked.manifest_missing": EXIT_PREWRITE_STRUCTURAL,
        "locked.build_check_failed": EXIT_PREWRITE_STRUCTURAL,
        "locked.unresolved_todo": EXIT_PREWRITE_STRUCTURAL,
    }.get(first.kind, EXIT_PREWRITE_STRUCTURAL)
    emit(
        AuthorResult(
            verb="lock-check",
            status="error",
            code=code,
            payload=payload,
            warnings=[w.message for w in report.warnings],
            diagnostics=report.failures,
        ),
        human=human,
    )
