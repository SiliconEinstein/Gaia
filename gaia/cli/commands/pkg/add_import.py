"""``gaia pkg add-import`` — inject ``from <module> import <names>`` into a target file.

Plain-Python imports between sibling modules of a Gaia knowledge package
are a precondition the author verbs can't handle on their own. When
``gaia author variable --value DOMINANT_COUNT`` is invoked against
``__init__.py``, the cli has no way to know ``DOMINANT_COUNT`` lives in
``./probabilities.py`` — the per-verb ``sibling_imports`` machinery
short-circuits whenever the target file is ``__init__.py`` since a
package can't re-import from itself.

This verb closes that gap with a small, explicit utility: it inserts
``from .<module> import <names>`` (or ``from <dotted.module> import
<names>``) into the target file, idempotently. Each name that already
appears in any matching ``from`` line is silently skipped; everything
new is folded into a single import line, alphabetically sorted, placed
after the docstring + ``from __future__`` block.

The verb covers the "plain Python data plumbing" gap surfaced when
reproducing example packages whose sibling modules carry plain numeric
constants (``probabilities.py``) or NamedTuple helpers — content that
isn't DSL and so isn't author-verb material, yet still needs to be
referenced from ``__init__.py``.
"""

from __future__ import annotations

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
from gaia.cli.commands.author._writer import _ensure_sibling_imports

_IDENT_OK = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"


def _is_valid_identifier(s: str) -> bool:
    if not s or s[0].isdigit():
        return False
    return all(ch in _IDENT_OK for ch in s)


def _validate_dotted_segments(name: str) -> str | None:
    """Validate every dotted segment of ``name`` as a Python identifier.

    Returns an error message naming the first bad segment, or ``None``
    when every segment is a valid identifier.
    """
    for part in name.split("."):
        if not _is_valid_identifier(part):
            return (
                f"--from contains invalid module segment {part!r}; "
                "each dotted segment must be a Python identifier"
            )
    return None


def _resolve_relative_from(
    cleaned: str, default_package: str | None
) -> tuple[str | None, str | None]:
    """Resolve the leading-dot relative shape (``.probabilities``).

    Strips leading dots and prepends ``default_package`` so the output is
    the absolute form ``<pkg>.probabilities``.
    """
    bare = cleaned.lstrip(".")
    if not bare:
        return None, "--from must include a module name (saw only leading dots)"
    seg_err = _validate_dotted_segments(bare)
    if seg_err is not None:
        return None, seg_err
    if default_package is None:
        return None, "--from used relative form but target package import name is unavailable"
    return f"{default_package}.{bare}", None


def _resolve_bare_from(cleaned: str, default_package: str | None) -> tuple[str | None, str | None]:
    """Resolve a bare identifier against ``default_package``."""
    if not _is_valid_identifier(cleaned):
        return None, f"--from {cleaned!r} is not a valid Python identifier"
    if default_package is None:
        return None, (
            "--from used bare-identifier form but target package import name is unavailable"
        )
    return f"{default_package}.{cleaned}", None


def _resolve_module(from_: str, default_package: str | None) -> tuple[str | None, str | None]:
    """Resolve ``--from`` into a fully-qualified module string.

    A bare identifier (``probabilities``) becomes ``<default_package>.<name>``
    — the relative sibling-module shape. A dotted name
    (``mypkg.probabilities``) is left verbatim. ``None``-default packages
    are an error for bare names (no way to disambiguate).

    Returns ``(resolved, error)``.
    """
    cleaned = from_.strip()
    if not cleaned:
        return None, "--from must be a non-empty module name"
    if cleaned.startswith("."):
        return _resolve_relative_from(cleaned, default_package)
    if "." in cleaned:
        # Dotted absolute form — accept verbatim after segment validation.
        seg_err = _validate_dotted_segments(cleaned)
        if seg_err is not None:
            return None, seg_err
        return cleaned, None
    return _resolve_bare_from(cleaned, default_package)


def add_import_command(
    from_: str = typer.Option(
        ...,
        "--from",
        help=(
            "Module to import from. A bare identifier (`probabilities`) or "
            "leading-dot form (`.probabilities`) resolves against the target "
            "package's import name as `<import_name>.probabilities`. A dotted "
            "absolute form (`other_pkg.helpers`) is used verbatim."
        ),
    ),
    names: str = typer.Option(
        ...,
        "--names",
        help=(
            "Comma-separated Python identifiers to import. Each must be a "
            "valid identifier; duplicates and entries already imported are "
            "silently skipped."
        ),
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str = typer.Option(
        "__init__.py",
        "--file",
        help=(
            "Relative path under src/<import_name>/ to write into. Default: "
            "`__init__.py`. The file must already exist; use `gaia pkg "
            "add-module` first if you need to seed a fresh sibling."
        ),
    ),
    human: bool = typer.Option(
        False, "--human", help="Render the envelope in human-readable form instead of JSON."
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Inject ``from <module> import <names>`` into a Gaia package file.

    Example:

    .. code-block:: bash

        gaia pkg add-import --from probabilities \
            --names DOMINANT_COUNT,RECESSIVE_COUNT,TOTAL_COUNT
    """
    del json_

    target_root = Path(target).resolve()

    # Validate the names CSV before structural checks so syntax errors
    # short-circuit on the cheap path.
    raw_names = [item.strip() for item in names.split(",") if item.strip()]
    if not raw_names:
        emit(
            AuthorResult(
                verb="add_import",
                status="error",
                code=EXIT_INPUT_SYNTAX,
                payload={"target": str(target_root)},
                diagnostics=[
                    Diagnostic(
                        kind="prewrite.syntax",
                        level="error",
                        message="--names must list at least one identifier",
                        source="prewrite",
                    )
                ],
            ),
            human=human,
        )
        return
    for n in raw_names:
        if not _is_valid_identifier(n):
            emit(
                AuthorResult(
                    verb="add_import",
                    status="error",
                    code=EXIT_INPUT_SYNTAX,
                    payload={"target": str(target_root)},
                    diagnostics=[
                        Diagnostic(
                            kind="prewrite.syntax",
                            level="error",
                            message=(f"--names entry {n!r} is not a valid Python identifier"),
                            source="prewrite",
                        )
                    ],
                ),
                human=human,
            )
            return

    # Pre-write target-structure invariant (a) — reuse the prewrite_check
    # probe so we share the toml validation + source-root discovery with
    # the rest of the family.
    probe_op = ProposedAuthorOp(
        verb="add_import",
        kind="scaffold",
        label=None,
        references=[],
        generated_code="pass\n",
        required_imports=(),
    )
    pre = prewrite_check(target_root, probe_op)
    if not pre.ok:
        emit(
            AuthorResult(
                verb="add_import",
                status="error",
                code=pre.exit_code,
                payload={"target": str(target_root)},
                diagnostics=pre.diagnostics,
            ),
            human=human,
        )
        return

    assert pre.source_root is not None
    source_root = pre.source_root
    import_name = pre.import_name or ""

    resolved_module, resolve_err = _resolve_module(from_, default_package=import_name or None)
    if resolve_err is not None:
        emit(
            AuthorResult(
                verb="add_import",
                status="error",
                code=EXIT_INPUT_SYNTAX,
                payload={"target": str(target_root)},
                diagnostics=[
                    Diagnostic(
                        kind="prewrite.syntax",
                        level="error",
                        message=resolve_err,
                        source="prewrite",
                    )
                ],
            ),
            human=human,
        )
        return
    assert resolved_module is not None

    target_file_rel = file.strip().lstrip("./")
    if not target_file_rel:
        target_file_rel = "__init__.py"
    if not target_file_rel.endswith(".py"):
        target_file_rel = f"{target_file_rel}.py"
    target_path = source_root / target_file_rel
    if not target_path.exists():
        emit(
            AuthorResult(
                verb="add_import",
                status="error",
                code=EXIT_PREWRITE_STRUCTURAL,
                payload={
                    "target": str(target_root),
                    "file": str(target_path),
                },
                diagnostics=[
                    Diagnostic(
                        kind="prewrite.target_invalid",
                        level="error",
                        message=(
                            f"target file {target_path} does not exist; run "
                            "`gaia pkg add-module --name <name>` first to "
                            "scaffold a sibling module"
                        ),
                        source="prewrite",
                    )
                ],
            ),
            human=human,
        )
        return

    needed: tuple[tuple[str, str], ...] = tuple((n, resolved_module) for n in raw_names)
    try:
        source = target_path.read_text()
    except OSError as exc:
        emit(
            AuthorResult(
                verb="add_import",
                status="error",
                code=EXIT_SYSTEM_IO,
                payload={"target": str(target_root), "file": str(target_path)},
                diagnostics=[
                    Diagnostic(
                        kind="prewrite.target_invalid",
                        level="error",
                        message=f"failed to read target file {target_path}: {exc}",
                        source="prewrite",
                    )
                ],
            ),
            human=human,
        )
        return

    new_source, added = _ensure_sibling_imports(
        source,
        needed,
        default_package=None,  # all entries carry a non-empty package explicitly
    )
    if added:
        try:
            target_path.write_text(new_source)
        except OSError as exc:
            emit(
                AuthorResult(
                    verb="add_import",
                    status="error",
                    code=EXIT_SYSTEM_IO,
                    payload={"target": str(target_root), "file": str(target_path)},
                    diagnostics=[
                        Diagnostic(
                            kind="prewrite.target_invalid",
                            level="error",
                            message=f"failed to write target file {target_path}: {exc}",
                            source="prewrite",
                        )
                    ],
                ),
                human=human,
            )
            return

    payload: dict[str, Any] = {
        "target": str(target_root),
        "file": str(target_path),
        "import_name": import_name,
        "from": resolved_module,
        "names_requested": list(raw_names),
        "names_added": list(added),
        "names_already_present": [n for n in raw_names if n not in added],
    }
    emit(
        AuthorResult(
            verb="add_import",
            status="ok",
            code=EXIT_OK,
            payload=payload,
        ),
        human=human,
    )


__all__ = ["add_import_command"]
