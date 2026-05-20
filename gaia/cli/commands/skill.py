"""``gaia skill`` — materialise the bundled Gaia skill registry into cwd.

Two verbs:

* ``register`` — copy the shipped ``SKILL.md`` set from the installed
  gaia-lang package into ``.gaia-skills/`` and symlink each skill into
  ``.claude/skills/`` and/or ``.agent/skills/``. Idempotent — safe to
  re-run after ``pip install --upgrade gaia-lang``.
* ``list`` — compare the shipped skill set against what is currently
  installed at cwd and print a status table.

Write scope is bounded: only ``.gaia-skills/`` and the per-skill entry
points under ``.claude/skills/<gaia-...>`` / ``.agent/skills/<gaia-...>``
are ever created / modified / removed. Real files, real directories,
and foreign-target symlinks at those entry points are reported as
``COLLISION`` and skipped — never overwritten.

POSIX-only: the design relies on ``os.symlink``, which on Windows needs
Developer Mode or admin and produces semantically different filesystem
objects. Both verbs exit with code 3 on Windows.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from enum import StrEnum
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any

import typer

# Importable name of the package under which the shipped skills live.
_SKILLS_PACKAGE = "gaia._skills"

# Per-cwd registry directory — our source of truth for "what gaia owns".
_REGISTRY_DIRNAME = ".gaia-skills"

# Agent surfaces we link skills into. Order is canonical for printing.
_AGENT_SURFACES = ("claude", "agent")


class TargetSurface(StrEnum):
    """Where ``gaia skill register`` materialises consumer-side symlinks."""

    AUTO = "auto"
    CLAUDE = "claude"
    AGENT = "agent"
    BOTH = "both"


_TARGET_OPTION: Any = typer.Option(
    TargetSurface.AUTO,
    "--target",
    help=(
        "Where to materialise consumer-side symlinks. "
        "'auto' links only into surfaces whose parent dir "
        "(.claude/ or .agent/) already exists; 'claude', 'agent', "
        "and 'both' opt in to creating the parent dir."
    ),
    case_sensitive=False,
    show_default=True,
)


# --------------------------------------------------------------------------- #
# Data shapes                                                                 #
# --------------------------------------------------------------------------- #


@dataclass
class SkillEntry:
    """One skill's payload — relative-path → bytes."""

    name: str  # e.g. "gaia-formalization" or "_shared"
    files: dict[str, bytes] = field(default_factory=dict)


@dataclass
class SymlinkOp:
    """A symlink operation under a single agent surface."""

    surface: str  # "claude" or "agent"
    skill: str  # e.g. "gaia-formalization"
    action: str  # "ADD" | "OK" | "COLLISION"
    detail: str = ""  # reason / target path for COLLISION


@dataclass
class Plan:
    """Structured plan returned by ``_plan_diff``.

    ``register`` consumes this in past-tense (apply) form; ``--dry-run``
    prints it in future-tense without touching disk.
    """

    shipped: dict[str, SkillEntry]
    installed: dict[str, SkillEntry]
    # Registry-level ops, keyed by skill / shared name.
    adds: list[str] = field(default_factory=list)
    refreshes: list[str] = field(default_factory=list)
    stales: list[str] = field(default_factory=list)
    # Surface-level ops.
    symlink_ops: list[SymlinkOp] = field(default_factory=list)
    # Surfaces we are NOT operating on this run and why (e.g. parent missing).
    skipped_surfaces: list[tuple[str, str]] = field(default_factory=list)
    # Whether `.gaia-skills/` does not exist yet at planning time.
    fresh_registry: bool = False


# --------------------------------------------------------------------------- #
# Loaders                                                                     #
# --------------------------------------------------------------------------- #


def _read_traversable_tree(node: Traversable, prefix: str = "") -> dict[str, bytes]:
    """Recursively read a Traversable directory into a {relpath: bytes} map.

    ``__pycache__`` and any dotfile children are skipped — they exist
    only when the source tree is editable-installed and are never part
    of the shipped data.
    """
    out: dict[str, bytes] = {}
    for child in node.iterdir():
        name = child.name
        if name == "__pycache__" or name.startswith("."):
            continue
        rel = f"{prefix}{name}" if not prefix else f"{prefix}/{name}"
        if child.is_dir():
            out.update(_read_traversable_tree(child, rel))
        else:
            out[rel] = child.read_bytes()
    return out


def _load_shipped() -> dict[str, SkillEntry]:
    """Walk the shipped ``gaia._skills`` tree via importlib.resources.

    Top-level entries whose name does not start with ``_`` are skills
    (each becomes one ``SkillEntry`` keyed by directory name). The
    ``_shared`` subtree is also returned as a single entry under the
    key ``_shared``; it is replicated wholesale to the registry but is
    never symlinked into any agent-surface skills directory.
    """
    root = files(_SKILLS_PACKAGE)
    entries: dict[str, SkillEntry] = {}
    for child in root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if name == "__pycache__":
            continue
        if name.startswith("_") and name != "_shared":
            continue
        entries[name] = SkillEntry(name=name, files=_read_traversable_tree(child))
    return entries


def _load_installed(registry_root: Path) -> dict[str, SkillEntry]:
    """Walk ``.gaia-skills/`` on disk if present; return same shape as shipped."""
    if not registry_root.is_dir():
        return {}
    entries: dict[str, SkillEntry] = {}
    for child in sorted(registry_root.iterdir()):
        if not child.is_dir():
            continue
        name = child.name
        if name.startswith("_") and name != "_shared":
            continue
        files_map: dict[str, bytes] = {}
        for path in sorted(child.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(child).as_posix()
            files_map[rel] = path.read_bytes()
        entries[name] = SkillEntry(name=name, files=files_map)
    return entries


# --------------------------------------------------------------------------- #
# Pure planners                                                               #
# --------------------------------------------------------------------------- #


def _is_owned_symlink(path: Path, registry_root: Path) -> bool:
    """True iff ``path`` is a symlink whose target resolves inside ``registry_root``.

    Resolution is relative to the symlink's parent (POSIX semantics).
    Used as the gate before any deletion of a consumer-surface entry:
    only links that point into our own registry are ever removed.
    """
    if not path.is_symlink():
        return False
    try:
        target = (path.parent / os.readlink(path)).resolve(strict=False)
    except OSError:
        return False
    try:
        target.relative_to(registry_root.resolve(strict=False))
    except ValueError:
        return False
    return True


def _resolve_targets(target: str, cwd: Path) -> tuple[list[str], list[tuple[str, str]]]:
    """Resolve ``--target`` against cwd.

    Returns ``(active_surfaces, skipped_with_reason)``. Under
    ``--target auto`` we link only into surfaces whose parent dir
    already exists; the explicit ``claude`` / ``agent`` / ``both``
    forms opt in to creating the parent dir.
    """
    active: list[str] = []
    skipped: list[tuple[str, str]] = []
    if target == "auto":
        for surface in _AGENT_SURFACES:
            parent = cwd / f".{surface}"
            if parent.exists():
                active.append(surface)
            else:
                skipped.append(
                    (
                        surface,
                        f"parent .{surface}/ not present; pass --target {surface} to force",
                    )
                )
    elif target == "claude":
        active = ["claude"]
    elif target == "agent":
        active = ["agent"]
    elif target == "both":
        active = list(_AGENT_SURFACES)
    else:
        # Typer's Choice should prevent this, but be defensive.
        raise typer.BadParameter(
            f"Invalid --target {target!r}; choose claude / agent / both / auto."
        )
    return active, skipped


def _plan_diff(
    shipped: dict[str, SkillEntry],
    installed: dict[str, SkillEntry],
    cwd: Path,
    active_surfaces: list[str],
    skipped_surfaces: list[tuple[str, str]],
    registry_root: Path,
) -> Plan:
    """Compute the structured plan. Pure — no filesystem mutation."""
    plan = Plan(shipped=shipped, installed=installed, skipped_surfaces=skipped_surfaces)
    plan.fresh_registry = not registry_root.exists()

    shipped_names = set(shipped)
    installed_names = set(installed)

    for name in sorted(shipped_names - installed_names):
        plan.adds.append(name)

    for name in sorted(shipped_names & installed_names):
        if shipped[name].files != installed[name].files:
            plan.refreshes.append(name)
        # Byte-equal entries are intentionally omitted — registry already current.

    for name in sorted(installed_names - shipped_names):
        plan.stales.append(name)

    # Symlink ops: one per (active surface, shipped non-shared skill).
    shipped_skills = sorted(n for n in shipped_names if not n.startswith("_"))
    for surface in active_surfaces:
        surface_dir = cwd / f".{surface}" / "skills"
        for skill in shipped_skills:
            entry_path = surface_dir / skill
            if not entry_path.exists() and not entry_path.is_symlink():
                plan.symlink_ops.append(SymlinkOp(surface, skill, "ADD"))
                continue
            if _is_owned_symlink(entry_path, registry_root):
                plan.symlink_ops.append(SymlinkOp(surface, skill, "OK"))
                continue
            # Anything else — real file, real dir, foreign-target symlink —
            # is a collision we will skip and warn about.
            if entry_path.is_symlink():
                detail = f"symlink → {os.readlink(entry_path)} (not into {_REGISTRY_DIRNAME}/)"
            elif entry_path.is_dir():
                detail = "real directory at target path"
            else:
                detail = "real file at target path"
            plan.symlink_ops.append(SymlinkOp(surface, skill, "COLLISION", detail))

    return plan


# --------------------------------------------------------------------------- #
# Plan rendering                                                              #
# --------------------------------------------------------------------------- #


def _dry_run_header(plan: Plan) -> list[str]:
    """Build the header lines (shipped + installed summary) for dry-run."""
    n_skills = sum(1 for n in plan.shipped if not n.startswith("_"))
    n_shared = sum(1 for n in plan.shipped if n.startswith("_"))
    n_inst_skills = sum(1 for n in plan.installed if not n.startswith("_"))
    n_inst_shared = sum(1 for n in plan.installed if n.startswith("_"))
    lines = [f"Shipped: {n_skills} skills + {n_shared} shared ref"]
    if plan.installed:
        lines.append(
            f"Installed: {n_inst_skills} skills + {n_inst_shared} shared ref ({_REGISTRY_DIRNAME}/)"
        )
    else:
        lines.append(f"Installed: none ({_REGISTRY_DIRNAME}/ does not exist)")
    return lines


def _dry_run_registry_section(plan: Plan) -> list[str]:
    """Build the ``Plan:`` registry-op section for dry-run."""
    lines = ["Plan:"]
    if plan.fresh_registry:
        lines.append(f"  CREATE  {_REGISTRY_DIRNAME}/")
    for name in plan.adds:
        lines.append(f"  ADD     {_REGISTRY_DIRNAME}/{name}/")
    for name in plan.refreshes:
        lines.append(f"  REFRESH {_REGISTRY_DIRNAME}/{name}/")
    for name in plan.stales:
        lines.append(
            f"  STALE   {_REGISTRY_DIRNAME}/{name}/   (will be removed; owned symlinks pruned)"
        )
    if not (plan.adds or plan.refreshes or plan.stales or plan.fresh_registry):
        lines.append("  (registry already up to date)")
    return lines


def _dry_run_symlink_section(plan: Plan, target: str) -> list[str]:
    """Build the symlink-op section for dry-run."""
    surfaces_active = sorted({op.surface for op in plan.symlink_ops})
    surface_summary = ", ".join(surfaces_active) if surfaces_active else "none"
    lines = [f"Symlinks (target={target} — active: {surface_summary}):"]
    for op in plan.symlink_ops:
        path = f".{op.surface}/skills/{op.skill}"
        if op.action == "ADD":
            target_rel = f"../../{_REGISTRY_DIRNAME}/{op.skill}"
            lines.append(f"  ADD     {path} → {target_rel}")
        elif op.action == "OK":
            lines.append(f"  OK      {path}")
        elif op.action == "COLLISION":
            lines.append(f"  SKIP    {path}  (collision: {op.detail})")
    for surface, reason in plan.skipped_surfaces:
        lines.append(f"  SKIP    .{surface}/skills/  ({reason})")
    return lines


def _render_plan_dry_run(plan: Plan, target: str) -> list[str]:
    """Render the planned operations in future tense (no disk mutation)."""
    lines: list[str] = []
    lines.extend(_dry_run_header(plan))
    lines.append("")
    lines.extend(_dry_run_registry_section(plan))
    lines.append("")
    lines.extend(_dry_run_symlink_section(plan, target))
    lines.append("")
    collisions = [op for op in plan.symlink_ops if op.action == "COLLISION"]
    if collisions:
        lines.append(f"{len(collisions)} collision(s) would be skipped.")
    else:
        lines.append("No collisions. Re-run without --dry-run to apply.")
    return lines


def _render_plan_applied(
    plan: Plan,
    *,
    target: str,
    applied_adds: list[str],
    applied_refreshes: list[str],
    applied_stales: list[str],
    applied_link_adds: list[tuple[str, str]],
    ok_links: list[tuple[str, str]],
    collisions: list[SymlinkOp],
) -> list[str]:
    """Render the applied operations in past tense."""
    lines: list[str] = []
    if plan.fresh_registry:
        lines.append(f"CREATED {_REGISTRY_DIRNAME}/")
    for name in applied_adds:
        lines.append(f"ADDED     {_REGISTRY_DIRNAME}/{name}/")
    for name in applied_refreshes:
        lines.append(f"REFRESHED {_REGISTRY_DIRNAME}/{name}/")
    for name in applied_stales:
        lines.append(f"REMOVED   {_REGISTRY_DIRNAME}/{name}/")
    for surface, skill in applied_link_adds:
        target_rel = f"../../{_REGISTRY_DIRNAME}/{skill}"
        lines.append(f"LINKED    .{surface}/skills/{skill} → {target_rel}")
    for surface, skill in ok_links:
        lines.append(f"OK        .{surface}/skills/{skill}")
    for surface, reason in plan.skipped_surfaces:
        lines.append(f"SKIPPED   .{surface}/skills/  ({reason})")
    for op in collisions:
        lines.append(f"SKIPPED   .{op.surface}/skills/{op.skill}  (COLLISION: {op.detail})")
    if not lines:
        lines.append(f"Registry already up to date (target={target}); nothing to do.")
    return lines


# --------------------------------------------------------------------------- #
# Mutators                                                                    #
# --------------------------------------------------------------------------- #


def _write_skill_tree(entry: SkillEntry, dest_root: Path) -> None:
    """Wipe ``dest_root/<name>`` and rewrite from ``entry.files``.

    We own this directory — refresh is "overwrite", no per-file merge.
    """
    dest = dest_root / entry.name
    if dest.exists() or dest.is_symlink():
        shutil.rmtree(dest) if dest.is_dir() and not dest.is_symlink() else dest.unlink()
    dest.mkdir(parents=True, exist_ok=True)
    for rel, payload in entry.files.items():
        target = dest / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)


def _remove_stale_registry_dir(registry_root: Path, name: str) -> None:
    """Remove a stale ``.gaia-skills/<name>/`` directory."""
    path = registry_root / name
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)


def _prune_stale_surface_links(
    cwd: Path,
    registry_root: Path,
    stale_skill_names: list[str],
    active_surfaces: list[str],
) -> list[tuple[str, str]]:
    """Remove agent-surface symlinks for stale skills iff we own them.

    Returns the list of ``(surface, skill)`` pairs that were skipped
    because the path was a real file / dir / foreign symlink (caller
    surfaces these as warnings).
    """
    skipped: list[tuple[str, str]] = []
    for skill in stale_skill_names:
        if skill.startswith("_"):
            continue  # _shared is never linked anyway
        for surface in active_surfaces:
            link_path = cwd / f".{surface}" / "skills" / skill
            if not link_path.exists() and not link_path.is_symlink():
                continue
            if _is_owned_symlink(link_path, registry_root):
                link_path.unlink()
            else:
                skipped.append((surface, skill))
    return skipped


@dataclass
class _ApplyAccumulator:
    """Mutable bookkeeping that ``_apply_plan`` and its helpers share."""

    applied_adds: list[str] = field(default_factory=list)
    applied_refreshes: list[str] = field(default_factory=list)
    applied_stales: list[str] = field(default_factory=list)
    applied_link_adds: list[tuple[str, str]] = field(default_factory=list)
    ok_links: list[tuple[str, str]] = field(default_factory=list)
    collisions: list[SymlinkOp] = field(default_factory=list)


def _prepare_apply_dirs(plan: Plan, cwd: Path, registry_root: Path) -> tuple[int, list[str]] | None:
    """Create the registry root and any required ``.<surface>/skills/`` parents.

    Returns ``None`` on success, or a ``(exit_code, lines)`` failure tuple
    matching the contract of ``_apply_plan``.
    """
    if registry_root.exists() and not registry_root.is_dir():
        return (
            2,
            [
                f"Error: {_REGISTRY_DIRNAME} exists but is not a directory "
                f"({registry_root}). Move or remove it and re-run.",
            ],
        )
    try:
        registry_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return 2, [f"Error: could not create {_REGISTRY_DIRNAME}/: {exc}"]

    for surface in {op.surface for op in plan.symlink_ops}:
        skills_dir = cwd / f".{surface}" / "skills"
        try:
            skills_dir.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return 2, [f"Error: could not create .{surface}/skills/: {exc}"]
    return None


def _apply_registry_ops(
    plan: Plan, cwd: Path, registry_root: Path, accum: _ApplyAccumulator
) -> None:
    """Apply ADD / REFRESH / STALE registry ops and prune stale surface links."""
    for name in plan.adds:
        _write_skill_tree(plan.shipped[name], registry_root)
        accum.applied_adds.append(name)
    for name in plan.refreshes:
        _write_skill_tree(plan.shipped[name], registry_root)
        accum.applied_refreshes.append(name)

    # Prune stale surface links BEFORE deleting registry entries — once
    # the registry dir is gone, ``_is_owned_symlink`` can no longer
    # confirm ownership and we would skip cleanup as a collision.
    surfaces = list({op.surface for op in plan.symlink_ops})
    for surface, skill in _prune_stale_surface_links(cwd, registry_root, plan.stales, surfaces):
        accum.collisions.append(
            SymlinkOp(
                surface=surface,
                skill=skill,
                action="COLLISION",
                detail="stale-link cleanup blocked (not an owned symlink)",
            )
        )

    for name in plan.stales:
        _remove_stale_registry_dir(registry_root, name)
        accum.applied_stales.append(name)


def _apply_symlink_ops(
    plan: Plan, cwd: Path, accum: _ApplyAccumulator
) -> tuple[int, list[str]] | None:
    """Apply per-skill symlink ops; return a fatal-error tuple or ``None``."""
    for op in plan.symlink_ops:
        link_path = cwd / f".{op.surface}" / "skills" / op.skill
        if op.action == "COLLISION":
            accum.collisions.append(op)
            continue
        if op.action == "OK":
            accum.ok_links.append((op.surface, op.skill))
            continue
        target_rel = Path("..") / ".." / _REGISTRY_DIRNAME / op.skill
        try:
            os.symlink(target_rel, link_path)
        except FileExistsError:
            accum.collisions.append(
                SymlinkOp(
                    surface=op.surface,
                    skill=op.skill,
                    action="COLLISION",
                    detail="path appeared between planning and apply",
                )
            )
            continue
        except OSError as exc:
            return 2, [f"Error: could not create symlink {link_path}: {exc}"]
        accum.applied_link_adds.append((op.surface, op.skill))
    return None


def _apply_plan(
    plan: Plan,
    cwd: Path,
    registry_root: Path,
    target: str,
) -> tuple[int, list[str]]:
    """Execute ``plan`` against the filesystem.

    Returns ``(exit_code, lines_to_print)``. Exit codes follow the CLI
    surface contract:

    * ``0`` — plan applied cleanly.
    * ``1`` — at least one collision was skipped; rest of plan applied.
    * ``2`` — unrecoverable error.
    """
    prep_error = _prepare_apply_dirs(plan, cwd, registry_root)
    if prep_error is not None:
        return prep_error

    accum = _ApplyAccumulator()
    _apply_registry_ops(plan, cwd, registry_root, accum)
    link_error = _apply_symlink_ops(plan, cwd, accum)
    if link_error is not None:
        return link_error

    lines = _render_plan_applied(
        plan,
        target=target,
        applied_adds=accum.applied_adds,
        applied_refreshes=accum.applied_refreshes,
        applied_stales=accum.applied_stales,
        applied_link_adds=accum.applied_link_adds,
        ok_links=accum.ok_links,
        collisions=accum.collisions,
    )
    exit_code = 1 if any(op.action == "COLLISION" for op in accum.collisions) else 0
    return exit_code, lines


# --------------------------------------------------------------------------- #
# Platform gate                                                               #
# --------------------------------------------------------------------------- #


def _posix_or_exit() -> None:
    """Exit with code 3 on Windows; ``register`` and ``list`` are POSIX-only."""
    if os.name == "nt":
        typer.echo(
            "Error: `gaia skill` is POSIX-only; Windows support is not implemented. "
            "The design relies on os.symlink semantics that differ on Windows.",
            err=True,
        )
        raise typer.Exit(3)


# --------------------------------------------------------------------------- #
# CLI verbs                                                                   #
# --------------------------------------------------------------------------- #


def register_command(
    target: TargetSurface = _TARGET_OPTION,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help=(
            "Print the plan (additions / refreshes / stale removals / "
            "collisions) without touching disk. Exits 0 if the plan is "
            "clean, 1 if any collision would be skipped."
        ),
    ),
) -> None:
    """Materialise the Gaia skill registry in the current directory.

    Copies the shipped SKILL.md set from the installed gaia-lang
    package into ``.gaia-skills/``, then symlinks each skill into
    ``.claude/skills/`` and/or ``.agent/skills/`` (whichever are
    present in cwd, unless ``--target`` opts in explicitly).
    Idempotent — safe to re-run after ``pip install --upgrade
    gaia-lang``.
    """
    _posix_or_exit()

    target_norm = target.value
    cwd = Path.cwd()
    registry_root = cwd / _REGISTRY_DIRNAME

    if registry_root.exists() and not registry_root.is_dir():
        typer.echo(
            f"Error: {_REGISTRY_DIRNAME} exists but is not a directory "
            f"({registry_root}). Move or remove it and re-run.",
            err=True,
        )
        raise typer.Exit(2)

    try:
        shipped = _load_shipped()
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        typer.echo(
            f"Error: shipped skill package data is unavailable ({exc!r}). Reinstall gaia-lang.",
            err=True,
        )
        raise typer.Exit(2) from exc

    installed = _load_installed(registry_root)
    active_surfaces, skipped_surfaces = _resolve_targets(target_norm, cwd)
    plan = _plan_diff(shipped, installed, cwd, active_surfaces, skipped_surfaces, registry_root)

    if dry_run:
        for line in _render_plan_dry_run(plan, target_norm):
            typer.echo(line)
        # Dry-run exit code matches what apply would return on collisions.
        would_collide = any(op.action == "COLLISION" for op in plan.symlink_ops)
        if would_collide:
            raise typer.Exit(1)
        return

    exit_code, lines = _apply_plan(plan, cwd, registry_root, target_norm)
    stream_err = exit_code != 0
    for line in lines:
        if stream_err and line.startswith("Error:"):
            typer.echo(line, err=True)
        else:
            typer.echo(line)
    if exit_code != 0:
        raise typer.Exit(exit_code)


def _status_for(name: str, shipped: dict[str, SkillEntry], installed: dict[str, SkillEntry]) -> str:
    """Return one of NEW / OK / DRIFT / STALE for the registry-level diff."""
    in_ship = name in shipped
    in_inst = name in installed
    if in_ship and not in_inst:
        return "NEW"
    if not in_ship and in_inst:
        return "STALE"
    # in both
    if shipped[name].files == installed[name].files:
        return "OK"
    return "DRIFT"


def _detect_collision_for(name: str, cwd: Path, registry_root: Path) -> str | None:
    """Return a collision description if any agent surface conflicts on ``name``.

    A collision is a path at ``.claude/skills/<name>`` or
    ``.agent/skills/<name>`` that exists and is *not* a symlink
    pointing into ``.gaia-skills/``.
    """
    for surface in _AGENT_SURFACES:
        entry = cwd / f".{surface}" / "skills" / name
        if not entry.exists() and not entry.is_symlink():
            continue
        if _is_owned_symlink(entry, registry_root):
            continue
        kind = (
            "real-dir"
            if entry.is_dir() and not entry.is_symlink()
            else ("symlink-foreign" if entry.is_symlink() else "real-file")
        )
        return f".{surface}/skills/{name}: {kind}"
    return None


def list_command() -> None:
    """Compare the shipped skill set against what is installed at cwd.

    Prints one row per top-level entry (skills + ``_shared``) with one
    of the statuses NEW / OK / STALE / DRIFT / COLLISION. The shipped
    column carries the installed gaia-lang version; the installed
    column is ``yes`` / ``no`` (registry presence). No ``--json``
    flag — add one only when a real consumer asks.
    """
    _posix_or_exit()

    cwd = Path.cwd()
    registry_root = cwd / _REGISTRY_DIRNAME

    try:
        shipped = _load_shipped()
    except (ModuleNotFoundError, FileNotFoundError) as exc:
        typer.echo(
            f"Error: shipped skill package data is unavailable ({exc!r}). Reinstall gaia-lang.",
            err=True,
        )
        raise typer.Exit(2) from exc

    if registry_root.exists() and not registry_root.is_dir():
        typer.echo(
            f"Error: {_REGISTRY_DIRNAME} exists but is not a directory ({registry_root}).",
            err=True,
        )
        raise typer.Exit(2)
    installed = _load_installed(registry_root)

    try:
        from gaia._meta import get_library_version  # local import — cheap, avoids cycle.

        shipped_version = get_library_version()
    except Exception:  # pragma: no cover - version probe is best-effort.
        shipped_version = "—"

    names = sorted(set(shipped) | set(installed))
    # Move ``_shared`` to the bottom for readability.
    names.sort(key=lambda n: (n.startswith("_"), n))

    rows: list[tuple[str, str, str, str, str]] = []
    for name in names:
        status = _status_for(name, shipped, installed)
        collision = (
            _detect_collision_for(name, cwd, registry_root) if not name.startswith("_") else None
        )
        ship_col = shipped_version if name in shipped else "—"
        inst_col = "yes" if name in installed else "—"
        note = ""
        if collision is not None:
            status = "COLLISION"
            note = collision
        elif status == "DRIFT":
            note = f"local edits in {_REGISTRY_DIRNAME}/{name}/"
        elif status == "STALE":
            note = "removed on next register"
        rows.append((name, ship_col, inst_col, status, note))

    # Pretty-aligned columns.
    headers = ("NAME", "SHIPPED", "INSTALLED", "STATUS", "NOTE")
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]

    def fmt(row: tuple[str, str, str, str, str]) -> str:
        # Last column (note) does not need padding.
        return "  ".join(
            row[i].ljust(widths[i]) if i < len(headers) - 1 else row[i] for i in range(len(headers))
        ).rstrip()

    typer.echo(fmt(headers))
    for row in rows:
        typer.echo(fmt(row))

    # Exit code: 1 if any COLLISION shown so scripts can spot trouble.
    if any(r[3] == "COLLISION" for r in rows):
        raise typer.Exit(1)


__all__ = ["list_command", "register_command"]
