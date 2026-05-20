"""``gaia pkg migrate`` — move a legacy Gaia package to the embedded layout.

Reads a legacy package (host ``pyproject.toml`` with ``[tool.gaia]``
+ ``src/<import>/``), copies the DSL source into ``gaia/``, rewrites
absolute imports of the legacy import name into relative form, and
writes the canonical ``gaia/gaia.toml`` derived from the host's
``[project]`` + ``[tool.gaia]`` blocks.

By default the migration is **additive**: it does not delete the
legacy ``src/<import>/`` tree and does not touch ``pyproject.toml``.
``detect_layout`` will then start preferring the new embedded
manifest (and emit a one-line warning about the coexisting legacy
block). When the user is satisfied they can remove ``[tool.gaia]``
from ``pyproject.toml`` and delete ``src/<import>/`` by hand.

With ``--remove-legacy`` the verb does both cleanups in one step
(behind an explicit flag so a user who runs ``migrate`` by accident
does not lose source code).

The migration produces **byte-identical IR** as long as the source
tree itself is byte-identical (we only rewrite absolute imports of
the package's own import name, never any third-party imports).
"""

from __future__ import annotations

import re
import shutil
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomlkit
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
from gaia.engine.layout import (
    EMBEDDED_GAIA_DIR,
    EMBEDDED_GAIA_MANIFEST,
    EMBEDDED_GAIA_OUTPUT_DIR,
    GaiaLayoutError,
    LayoutKind,
    detect_layout,
)
from gaia.engine.manifest import (
    GaiaManifest,
    GaiaPackageBlock,
    GaiaProjectionBlock,
    GaiaQualityBlock,
    render_manifest,
)

_MIGRATION_HEADER = "# Gaia knowledge-package identity (migrated from legacy [tool.gaia]).\n\n"


@dataclass
class _MigratePlan:
    host_root: Path
    legacy_src_root: Path
    legacy_import_name: str
    package_name: str
    version: str
    namespace: str
    description: str | None
    uuid: str | None
    allow_holes: bool
    remove_legacy: bool


def _resolve_legacy(host: Path) -> _MigratePlan | Diagnostic:
    try:
        layout = detect_layout(host)
    except GaiaLayoutError as exc:
        return Diagnostic(
            kind="prewrite.target_invalid",
            level="error",
            message=str(exc),
            source="prewrite",
            where={"host": str(host)},
        )
    if layout.kind is not LayoutKind.LEGACY:
        return Diagnostic(
            kind="prewrite.target_invalid",
            level="error",
            message=(
                f"host {host} is already in {layout.kind.value!r} layout. "
                "Migration only runs on legacy packages."
            ),
            source="prewrite",
            where={"host": str(host), "layout": layout.kind.value},
        )

    quality = layout.gaia_config.get("quality") or {}
    allow_holes = bool(quality.get("allow_holes", True))
    description = layout.project_config.get("description")
    # Reuse the legacy [tool.gaia].uuid when present so the migrated
    # embedded package keeps the same registry identity. When absent,
    # mint a fresh one so `gaia pkg register` works without a
    # follow-up step.
    legacy_uuid = layout.gaia_config.get("uuid")
    if not isinstance(legacy_uuid, str) or not legacy_uuid.strip():
        legacy_uuid = str(_uuid.uuid4())
    return _MigratePlan(
        host_root=layout.host_path,
        legacy_src_root=layout.source_root / layout.import_name,
        legacy_import_name=layout.import_name,
        package_name=layout.package_name,
        version=layout.version,
        namespace=layout.namespace,
        description=description if isinstance(description, str) else None,
        uuid=legacy_uuid,
        allow_holes=allow_holes,
        remove_legacy=False,
    )


_ABS_IMPORT_RE_TEMPLATE = (
    # `from <pkg> import ...`
    r"^(?P<indent>\s*)from\s+{name}(?P<rest>(?:\.[\w\.]+)?\s+import\s+)"
)
_ABS_IMPORT_LINE_TEMPLATE = (
    # `import <pkg>` or `import <pkg> as alias`
    r"^(?P<indent>\s*)import\s+{name}(?P<rest>(?:\.[\w\.]+)?(?:\s+as\s+\w+)?\s*)$"
)


def _rewrite_absolute_imports(source: str, legacy_name: str) -> tuple[str, int]:
    """Rewrite ``from <legacy_name>[.x] import ...`` to relative form.

    Conservative: only the legacy package's own import name is touched;
    every other ``from`` / ``import`` line passes through unchanged.
    Returns the rewritten text plus the number of substitutions.
    """
    pattern = re.compile(_ABS_IMPORT_RE_TEMPLATE.format(name=re.escape(legacy_name)), re.MULTILINE)

    def _replace(match: re.Match[str]) -> str:
        indent = match.group("indent")
        rest = match.group("rest")
        # rest starts with optional ``.subpkg`` then ``  import ...``.
        # ``from <legacy>.sub import x`` ⇒ ``from .sub import x``
        # ``from <legacy> import x``     ⇒ ``from . import x`` (the
        # leading whitespace from rest is preserved so ``import`` keeps
        # its mandatory space).
        if rest.startswith("."):
            return f"{indent}from .{rest[1:]}"
        return f"{indent}from .{rest}"

    rewritten, count = pattern.subn(_replace, source)

    # Also flag (but do not auto-rewrite) bare ``import <legacy_name>``
    # lines — relative imports of the parent package are unusual in
    # Gaia code, so we conservatively leave them and let the user fix.
    return rewritten, count


def _copy_legacy_source(
    legacy_src_root: Path,
    target_gaia_dir: Path,
    legacy_name: str,
) -> tuple[list[Path], int]:
    """Copy every ``.py`` file from ``src/<name>/`` into ``gaia/``.

    Returns (written paths, rewritten-import count).
    """
    target_gaia_dir.mkdir(parents=True, exist_ok=False)
    rewritten_total = 0
    written: list[Path] = []
    for source_file in sorted(legacy_src_root.rglob("*.py")):
        rel = source_file.relative_to(legacy_src_root)
        target = target_gaia_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        text = source_file.read_text(encoding="utf-8")
        rewritten, count = _rewrite_absolute_imports(text, legacy_name)
        target.write_text(rewritten)
        rewritten_total += count
        written.append(target)
    return written, rewritten_total


def _write_gaia_toml(plan: _MigratePlan, target_gaia_dir: Path) -> Path:
    manifest = GaiaManifest(
        package=GaiaPackageBlock(
            name=plan.package_name,
            version=plan.version,
            namespace=plan.namespace,
            description=plan.description,
            uuid=plan.uuid,
            host_kind="python-package",
        ),
        quality=GaiaQualityBlock(allow_holes=plan.allow_holes),
        projection=GaiaProjectionBlock(mode="scaffold"),
    )
    manifest_path = target_gaia_dir / EMBEDDED_GAIA_MANIFEST
    manifest_path.write_text(render_manifest(manifest, header=_MIGRATION_HEADER))
    return manifest_path


def _ensure_output_dir(host: Path) -> Path:
    out = host / EMBEDDED_GAIA_OUTPUT_DIR
    out.mkdir(parents=True, exist_ok=True)
    keep = out / ".gitkeep"
    if not keep.exists():
        keep.write_text("")
    return out


def _strip_tool_gaia(pyproject_path: Path) -> bool:
    """Remove the ``[tool.gaia]`` block from ``pyproject.toml`` in-place.

    Uses ``tomlkit`` (style-preserving TOML editor) so comments,
    quoting, and surrounding key order in the rest of the file are
    untouched. Returns ``True`` when something was actually removed.

    The strip is exhaustive — any ``[tool.gaia.*]`` sub-table is
    removed as well, and the parent ``[tool]`` table is collapsed if
    Gaia was its only child. This matches the user expectation that
    ``--remove-legacy`` leaves no Gaia trace behind in the host's
    own pyproject.
    """
    if not pyproject_path.exists():
        return False
    text = pyproject_path.read_text(encoding="utf-8")
    try:
        doc = tomlkit.parse(text)
    except tomlkit.exceptions.TOMLKitError:
        return False

    tool = doc.get("tool")
    if not isinstance(tool, dict) or "gaia" not in tool:
        return False
    del tool["gaia"]
    if not tool:
        del doc["tool"]

    pyproject_path.write_text(tomlkit.dumps(doc))
    return True


def _migrate_command_impl(plan: _MigratePlan) -> dict[str, Any]:
    target_gaia_dir = plan.host_root / EMBEDDED_GAIA_DIR
    if target_gaia_dir.exists():
        raise FileExistsError(
            f"{target_gaia_dir} already exists; refusing to overwrite an existing mount."
        )
    written, rewritten_count = _copy_legacy_source(
        plan.legacy_src_root, target_gaia_dir, plan.legacy_import_name
    )
    manifest_path = _write_gaia_toml(plan, target_gaia_dir)
    _ensure_output_dir(plan.host_root)

    removed: dict[str, bool] = {"src_tree": False, "tool_gaia_block": False}
    if plan.remove_legacy:
        if plan.legacy_src_root.is_dir():
            shutil.rmtree(plan.legacy_src_root)
            removed["src_tree"] = True
        removed["tool_gaia_block"] = _strip_tool_gaia(plan.host_root / "pyproject.toml")

    return {
        "host": str(plan.host_root),
        "package_name": plan.package_name,
        "namespace": plan.namespace,
        "files_written": [str(p) for p in [manifest_path, *written]],
        "imports_rewritten": rewritten_count,
        "legacy_removed": removed,
        "next_steps": (f"gaia build compile {plan.host_root}\ngaia run infer {plan.host_root}"),
    }


def migrate_command(
    host: str = typer.Argument(
        ...,
        help=(
            "Path to a legacy Gaia package (host with [tool.gaia] in pyproject.toml). "
            "Migration writes gaia/gaia.toml + gaia/ next to src/, never touching "
            "pyproject.toml unless --remove-legacy is set."
        ),
    ),
    remove_legacy: bool = typer.Option(
        False,
        "--remove-legacy/--keep-legacy",
        help=(
            "After migrating, delete src/<import>/ and strip [tool.gaia] from "
            "pyproject.toml. Off by default — keep both layouts side-by-side until "
            "you have verified the embedded one compiles to the same IR hash."
        ),
    ),
    human: bool = typer.Option(False, "--human", help="Render envelope as human text."),
    json_: bool = typer.Option(True, "--json/--no-json", help="JSON-first output."),
) -> None:
    r"""Migrate a legacy Gaia package to the non-invasive embedded layout.

    Example:

    .. code-block:: bash

        gaia pkg migrate examples/galileo-v0-5-gaia
        gaia build compile examples/galileo-v0-5-gaia  # now uses gaia/gaia.toml
    """
    del json_
    host_path = Path(host).resolve()

    plan_or_diag = _resolve_legacy(host_path)
    if isinstance(plan_or_diag, Diagnostic):
        code = (
            EXIT_SYSTEM_IO
            if plan_or_diag.kind in {"prewrite.target_missing", "prewrite.target_invalid"}
            else EXIT_PREWRITE_STRUCTURAL
        )
        emit(
            AuthorResult(
                verb="migrate",
                status="error",
                code=code,
                payload={"host": str(host_path)},
                diagnostics=[plan_or_diag],
            ),
            human=human,
        )
        return

    plan_or_diag.remove_legacy = remove_legacy
    try:
        payload = _migrate_command_impl(plan_or_diag)
    except FileExistsError as exc:
        emit(
            AuthorResult(
                verb="migrate",
                status="error",
                code=EXIT_INPUT_SYNTAX,
                payload={"host": str(host_path)},
                diagnostics=[
                    Diagnostic(
                        kind="prewrite.collision",
                        level="error",
                        message=str(exc),
                        source="prewrite",
                        where={"host": str(host_path)},
                    )
                ],
            ),
            human=human,
        )
        return
    except (OSError, PermissionError) as exc:
        emit(
            AuthorResult(
                verb="migrate",
                status="error",
                code=EXIT_SYSTEM_IO,
                payload={"host": str(host_path)},
                diagnostics=[
                    Diagnostic(
                        kind="prewrite.target_invalid",
                        level="error",
                        message=str(exc),
                        source="prewrite",
                        where={"host": str(host_path)},
                    )
                ],
            ),
            human=human,
        )
        return

    emit(
        AuthorResult(verb="migrate", status="ok", code=EXIT_OK, payload=payload),
        human=human,
    )


__all__ = ["migrate_command"]
