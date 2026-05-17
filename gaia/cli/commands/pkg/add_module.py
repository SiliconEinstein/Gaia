"""``gaia pkg add-module`` — scaffold a fresh sibling Python module.

R7 G1 — sibling files in a Gaia knowledge package (e.g. ``priors.py``,
``probabilities.py``) need a precondition step before
``gaia author <verb> --file <relative>`` can write into them. This verb
fills the gap by:

1. Validating the target package is a Gaia knowledge package (via the
   existing pre-write invariant (a) machinery).
2. Creating ``src/<import_name>/<module>.py`` with a minimal header and
   an empty ``__all__`` list.
3. Optionally seeding ``from gaia.engine.lang import <verbs>`` based on
   the ``--imports`` flag (CSV).

The verb emits the same uniform JSON envelope as the rest of the
``gaia author`` / ``gaia pkg scaffold`` family so an agent consumer can
chain it into authoring pipelines.

Why a separate sub-verb instead of letting the author verbs auto-create
their target file? Two reasons:

* **Pre-write hygiene.** Author verbs assume the target file already
  exists so the (c) collision-and-reference scan has stable inputs;
  letting them silently mint a fresh file would diverge their pre-write
  invariants.

* **Explicit intent.** Adding a sibling module is a structural choice
  about package organisation. Splitting it from the per-statement verb
  keeps the agent's actions auditable.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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
from gaia.cli.commands.author._prewrite import prewrite_check
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp

_MODULE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass
class _AddModulePlan:
    """Resolved parameters after argument validation."""

    target_root: Path
    source_root: Path
    import_name: str
    module_name: str
    module_path: Path
    imports: tuple[str, ...]


def _validate_inputs(
    *,
    target: Path,
    module_name: str,
) -> tuple[Diagnostic, ...] | None:
    """Sanity-check the module name (target package validity is done elsewhere)."""
    del target
    if not module_name:
        return (
            Diagnostic(
                kind="prewrite.syntax",
                level="error",
                message="--name must be a non-empty module identifier",
                source="prewrite",
            ),
        )
    if module_name.endswith(".py"):
        # User passed a filename; strip the suffix so the module-name
        # check below makes sense.
        module_name = module_name[:-3]
    if module_name.startswith("__"):
        return (
            Diagnostic(
                kind="prewrite.syntax",
                level="error",
                message=(
                    f"--name {module_name!r} starts with '__'; that namespace is "
                    "reserved for dunder modules"
                ),
                source="prewrite",
            ),
        )
    if not _MODULE_NAME_RE.match(module_name):
        return (
            Diagnostic(
                kind="prewrite.syntax",
                level="error",
                message=(
                    f"--name {module_name!r} is not a valid Python module "
                    "identifier (must match [A-Za-z_][A-Za-z0-9_]*)"
                ),
                source="prewrite",
            ),
        )
    return None


def _build_module_text(*, imports: tuple[str, ...]) -> str:
    """Render the sibling module's seed text."""
    lines = ['"""Sibling module created via `gaia pkg add-module`."""', ""]
    if imports:
        lines.append("from __future__ import annotations")
        lines.append("")
        lines.append(f"from gaia.engine.lang import {', '.join(sorted(imports))}")
        lines.append("")
    lines.append("__all__: list[str] = []")
    lines.append("")
    return "\n".join(lines)


def add_module_command(
    name: str = typer.Option(
        ...,
        "--name",
        help=(
            "Module name relative to the package source root. Accepts a bare "
            "identifier (`priors`) or a filename (`priors.py`). Required."
        ),
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    imports: str | None = typer.Option(
        None,
        "--imports",
        help=(
            "Comma-separated DSL verbs to seed the module's imports "
            "(e.g. `register_prior,note`). Default: no imports beyond "
            "`from __future__ import annotations`."
        ),
    ),
    human: bool = typer.Option(
        False, "--human", help="Render the envelope in human-readable form instead of JSON."
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Scaffold a sibling Python module under ``src/<import_name>/``.

    Example:

    .. code-block:: bash

        gaia pkg add-module --name priors --imports register_prior \
            --target ./my-domain-gaia
    """
    del json_

    target_root = Path(target).resolve()
    module_name = name[:-3] if name.endswith(".py") else name
    pre_errors = _validate_inputs(target=target_root, module_name=module_name)
    if pre_errors:
        first = pre_errors[0]
        result = AuthorResult(
            verb="add_module",
            status="error",
            code=EXIT_INPUT_SYNTAX,
            payload={"target": str(target_root), "module_name": module_name},
            diagnostics=list(pre_errors),
        )
        del first
        emit(result, human=human)
        return

    # Run the pre-write target-structure invariant (a) by constructing a
    # throwaway no-op proposed op against the entrypoint. The
    # ``prewrite_check`` already encapsulates the toml validation +
    # source-root discovery; reusing it avoids drift.
    probe_op = ProposedAuthorOp(
        verb="add_module",
        kind="scaffold",
        label=None,
        references=[],
        generated_code="pass\n",
        required_imports=(),
    )
    pre = prewrite_check(target_root, probe_op)
    if not pre.ok:
        # Hand-pick the structural errors (we know the probe statement
        # itself is syntactically clean).
        result = AuthorResult(
            verb="add_module",
            status="error",
            code=pre.exit_code,
            payload={"target": str(target_root)},
            diagnostics=pre.diagnostics,
        )
        emit(result, human=human)
        return

    assert pre.source_root is not None
    source_root = pre.source_root
    import_name = pre.import_name or ""

    module_path = source_root / f"{module_name}.py"
    if module_path.exists():
        result = AuthorResult(
            verb="add_module",
            status="error",
            code=EXIT_PREWRITE_STRUCTURAL,
            payload={
                "target": str(target_root),
                "module_path": str(module_path),
            },
            diagnostics=[
                Diagnostic(
                    kind="prewrite.collision",
                    level="error",
                    message=(
                        f"module {module_name!r} already exists at {module_path}; "
                        "delete it or pick a different --name"
                    ),
                    source="prewrite",
                )
            ],
        )
        emit(result, human=human)
        return

    imports_tuple: tuple[str, ...] = tuple(
        item.strip() for item in (imports or "").split(",") if item.strip()
    )

    try:
        module_path.write_text(_build_module_text(imports=imports_tuple))
    except (OSError, PermissionError) as exc:
        result = AuthorResult(
            verb="add_module",
            status="error",
            code=EXIT_SYSTEM_IO,
            payload={"target": str(target_root)},
            diagnostics=[
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=f"failed to write module {module_path}: {exc}",
                    source="prewrite",
                )
            ],
        )
        emit(result, human=human)
        return

    payload: dict[str, Any] = {
        "target": str(target_root),
        "module_name": module_name,
        "module_path": str(module_path),
        "relative_path": f"{module_name}.py",
        "import_name": import_name,
        "imports": list(imports_tuple),
    }
    result = AuthorResult(
        verb="add_module",
        status="ok",
        code=EXIT_OK,
        payload=payload,
    )
    emit(result, human=human)


__all__ = ["add_module_command"]
