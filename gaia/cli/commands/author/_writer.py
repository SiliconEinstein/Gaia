"""File-append helper for ``gaia author`` verbs.

R7 G1 multi-file target — the writer now supports routing each authored
statement to an arbitrary ``src/<import_name>/<file>.py`` instead of the
historic always-``__init__.py``. The caller chooses the target file via
:attr:`ProposedAuthorOp.target_file`; the runner resolves the absolute
path and hands it here. Cross-file references are handled by inserting
``from <import_name> import <label>`` lines into the sibling file at
write time (see :func:`append_statement` ``sibling_imports`` arg).

R7 G10 ``__all__`` auto-management — when the target file declares a
module-level ``__all__ = [...]`` literal, the writer parses it and
inserts the newly-bound label alphabetically (if absent). Dynamically-
constructed ``__all__`` blocks emit a warning and are left untouched.

Returns the appended snippet plus a small location record so the verb's
JSON payload can carry the write target back to the caller.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WriteResult:
    """Where + what got written."""

    path: Path
    appended: str
    all_managed: bool = False
    all_warning: str | None = None
    sibling_imports_added: tuple[str, ...] = field(default_factory=tuple)


def append_statement(
    target_file_path: Path,
    generated_code: str,
    *,
    new_label: str | None = None,
    sibling_imports: tuple[tuple[str, str], ...] = (),
    import_package_name: str | None = None,
) -> WriteResult:
    """Append ``generated_code`` to ``target_file_path`` with a blank-line separator.

    The file is read and rewritten in one shot so partial writes don't
    leave the source half-broken. The blank-line separator is only added
    when the existing tail does not already end with one blank line.

    Args:
        target_file_path: The ``src/<pkg>/<file>.py`` (or
            ``__init__.py``) to mutate.
        generated_code: The Python snippet to append.
        new_label: When set, the writer attempts to insert ``new_label``
            into the module's ``__all__`` literal (R7 G10). A missing
            ``__all__`` is left absent (no synthesis); a dynamically-
            constructed one is left untouched and a warning is captured
            on :attr:`WriteResult.all_warning`.
        sibling_imports: A tuple of ``(symbol, package_name)`` pairs the
            writer should ensure are imported at the top of the file. Used
            when the statement lands in a sibling file (e.g.
            ``priors.py``) and references symbols defined in
            ``__init__.py``. Each missing entry is added via
            ``from <package_name> import <symbol>`` next to existing
            same-package imports (or below the leading docstring / future
            import block).
        import_package_name: The Python package import name for the
            target package (e.g. ``galileo_v0_5``). Used for the
            self-import shape ``from galileo_v0_5 import daily_observation``
            when ``sibling_imports`` entries omit a package and want the
            default.

    Returns:
        A :class:`WriteResult` capturing the appended snippet, whether
        ``__all__`` was mutated, any ``__all__`` warning, and the symbols
        for which sibling-import lines were newly added.
    """
    existing = target_file_path.read_text() if target_file_path.exists() else ""

    # ---- sibling import insertion -------------------------------------- #
    sibling_added: list[str] = []
    if sibling_imports:
        existing, sibling_added_list = _ensure_sibling_imports(
            existing,
            sibling_imports,
            default_package=import_package_name,
        )
        sibling_added = sibling_added_list

    if existing and not existing.endswith("\n"):
        existing += "\n"
    if existing and not existing.endswith("\n\n"):
        existing += "\n"
    snippet = generated_code.rstrip() + "\n"
    new_text = existing + snippet

    # ---- __all__ auto-management --------------------------------------- #
    all_managed = False
    all_warning: str | None = None
    if new_label is not None:
        new_text, all_managed, all_warning = _maybe_update_all_block(new_text, new_label)

    target_file_path.write_text(new_text)
    return WriteResult(
        path=target_file_path,
        appended=snippet,
        all_managed=all_managed,
        all_warning=all_warning,
        sibling_imports_added=tuple(sibling_added),
    )


# --------------------------------------------------------------------------- #
# Sibling import insertion                                                    #
# --------------------------------------------------------------------------- #


def _ensure_sibling_imports(
    source: str,
    needed: tuple[tuple[str, str], ...],
    *,
    default_package: str | None,
) -> tuple[str, list[str]]:
    """Insert ``from <pkg> import <symbol>`` for any missing ``needed`` entries.

    Cheap approach: parse the source to find existing top-level imports;
    group new entries by package; emit each group either by extending an
    existing ``from <pkg> import (...)`` line (merging members) or by
    appending a new ``from <pkg> import <symbol>`` line after the
    leading docstring + future-imports block. Order within a group is
    alphabetical.

    Returns ``(new_source, added_symbols)`` where ``added_symbols`` lists
    the symbols that were actually newly inserted (an entry already
    present in the source is skipped silently).
    """
    if not needed:
        return source, []
    try:
        tree = ast.parse(source) if source.strip() else ast.parse("")
    except SyntaxError:
        # Source has its own syntax error — don't compound it; let
        # pre-write surface the issue separately.
        return source, []

    # Map: package_name -> set of already-imported symbols (idempotency)
    already_imported: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            already_imported.setdefault(node.module, set()).update(
                alias.asname or alias.name for alias in node.names
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                already_imported.setdefault(alias.asname or alias.name, set())

    # Decide which entries we actually need to add.
    grouped_new: dict[str, list[str]] = {}
    added_symbols: list[str] = []
    for symbol, pkg_in in needed:
        pkg = pkg_in or default_package or ""
        if not pkg:
            continue
        if symbol in already_imported.get(pkg, set()):
            continue
        # Also skip if the symbol was already in this batch (idempotency
        # against duplicate sibling_imports entries from upstream).
        if symbol in grouped_new.get(pkg, []):
            continue
        grouped_new.setdefault(pkg, []).append(symbol)
        added_symbols.append(symbol)

    if not grouped_new:
        return source, []

    # Insertion point: after the leading module docstring + any
    # ``from __future__ ...`` imports. Past that, we drop the new
    # ``from <pkg> import ...`` lines (a blank line above + below).
    insertion_offset = _find_import_insertion_offset(source, tree)

    new_lines: list[str] = []
    for pkg in sorted(grouped_new):
        symbols = sorted(grouped_new[pkg])
        new_lines.append(f"from {pkg} import {', '.join(symbols)}")
    if not new_lines:
        return source, []

    insert_block = "\n".join(new_lines) + "\n"
    head = source[:insertion_offset]
    tail = source[insertion_offset:]
    # Make sure we don't smash an existing line — pad with newline if
    # the head doesn't already end with one.
    if head and not head.endswith("\n"):
        head += "\n"
    # Add a blank line above the new block if the head doesn't already
    # end with a blank line.
    if head and not head.endswith("\n\n"):
        head += "\n"
    # Tail will start with whatever was after the insertion point;
    # ensure separation.
    if tail and not tail.startswith("\n"):
        insert_block += "\n"
    return head + insert_block + tail, added_symbols


def _find_import_insertion_offset(source: str, tree: ast.Module) -> int:
    """Find a character offset to insert new ``from <pkg> import ...`` lines.

    Heuristic: after the module docstring (if any) and the trailing
    ``from __future__ import ...`` block, but before the first non-
    import statement. Falls back to the end of source if no anchor is
    found.
    """
    if not source:
        return 0
    # Walk top-level statements to find the last future import or
    # docstring; the next statement's lineno is the insertion line.
    last_anchor_end_line = 0
    saw_docstring = False
    for idx, node in enumerate(tree.body):
        if (
            idx == 0
            and isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            # Module docstring — skip past it.
            saw_docstring = True
            last_anchor_end_line = node.end_lineno or node.lineno
            continue
        if isinstance(node, ast.ImportFrom) and node.module == "__future__":
            last_anchor_end_line = node.end_lineno or node.lineno
            continue
        break

    if last_anchor_end_line == 0 and not saw_docstring:
        # No leading docstring / future imports; insert at the very top.
        return 0

    # Convert line number to character offset.
    lines = source.splitlines(keepends=True)
    offset = 0
    for line_idx, line in enumerate(lines):
        offset += len(line)
        if line_idx + 1 >= last_anchor_end_line:
            return offset
    return len(source)


# --------------------------------------------------------------------------- #
# __all__ auto-management (R7 G10)                                            #
# --------------------------------------------------------------------------- #


def _maybe_update_all_block(source: str, new_label: str) -> tuple[str, bool, str | None]:
    """Insert ``new_label`` into a module-level ``__all__ = [...]`` if present.

    Behavior:

    * No top-level ``__all__`` assignment present → return source
      unchanged. R7 G10 does **not** synthesize ``__all__``; that is
      package-author territory.
    * Top-level ``__all__`` present + list/tuple literal of strings →
      insert ``new_label`` in alphabetical position. Returns updated
      source with ``all_managed=True``.
    * Top-level ``__all__`` present + dynamic / non-literal RHS → leave
      source unchanged and return a warning string the caller can
      surface on the envelope.
    * ``new_label`` already present in the literal → leave source
      unchanged with ``all_managed=False, all_warning=None`` (idempotent).
    """
    if not source.strip():
        return source, False, None
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source, False, None

    target_assign: ast.Assign | None = None
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t for t in node.targets if isinstance(t, ast.Name) and t.id == "__all__"]
        if not targets:
            continue
        target_assign = node
        break

    if target_assign is None:
        return source, False, None

    rhs = target_assign.value
    if not isinstance(rhs, (ast.List, ast.Tuple)):
        return source, False, ("__all__ is not a literal list/tuple; cli-author left it untouched")
    entries: list[str] = []
    for elt in rhs.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            entries.append(elt.value)
        else:
            return (
                source,
                False,
                ("__all__ contains non-string-literal entries; cli-author left it untouched"),
            )

    if new_label in entries:
        return source, False, None

    # Insert alphabetically.
    insertion_idx = 0
    while insertion_idx < len(entries) and entries[insertion_idx] < new_label:
        insertion_idx += 1
    entries.insert(insertion_idx, new_label)

    # Render the new literal in the same bracket style as the original.
    open_bracket = "[" if isinstance(rhs, ast.List) else "("
    close_bracket = "]" if isinstance(rhs, ast.List) else ")"
    # Mendel-style: one entry per line, alphabetically sorted, trailing
    # comma. We force a multi-line shape regardless of how the source
    # originally rendered, so the diff stays clean for future appends.
    indent = "    "
    body_lines = "\n".join(f"{indent}{entry!r}," for entry in entries)
    new_literal = f"__all__ = {open_bracket}\n{body_lines}\n{close_bracket}"

    # Replace the original assignment's textual range with the new literal.
    start_line = target_assign.lineno
    end_line = target_assign.end_lineno or target_assign.lineno
    lines = source.splitlines(keepends=True)
    head = "".join(lines[: start_line - 1])
    tail = "".join(lines[end_line:])
    sep = "\n" if not new_literal.endswith("\n") else ""
    return head + new_literal + sep + tail, True, None


__all__ = ["WriteResult", "append_statement"]
