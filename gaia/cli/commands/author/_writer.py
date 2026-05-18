"""File-append helper for ``gaia author`` verbs.

Multi-file target — the writer routes each authored statement to an
arbitrary ``src/<import_name>/<file>.py`` (or ``__init__.py`` by
default). The caller chooses the target file via
:attr:`ProposedAuthorOp.target_file`; the runner resolves the absolute
path and hands it here. Cross-file references are handled by inserting
``from <import_name> import <label>`` lines into the sibling file at
write time (see :func:`append_statement` ``sibling_imports`` arg).

``__all__`` auto-management — when the target file declares a
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
    required_imports: tuple[str, ...] = (),
    export: bool = True,
) -> WriteResult:
    """Append ``generated_code`` to ``target_file_path`` with a blank-line separator.

    The file is read and rewritten in one shot so partial writes don't
    leave the source half-broken. The blank-line separator is only added
    when the existing tail does not already end with one blank line.

    Args:
        target_file_path: The ``src/<pkg>/<file>.py`` (or
            ``__init__.py``) to mutate.
        generated_code: The Python snippet to append.
        new_label: When set AND ``export`` is True, the writer attempts to
            insert ``new_label`` into the module's ``__all__`` literal. A
            missing ``__all__`` is left absent (no synthesis); a
            dynamically-constructed one is left untouched and a warning is
            captured on :attr:`WriteResult.all_warning`.
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
        required_imports: Engine DSL names the proposed statement calls
            (e.g. ``("derive",)``). The writer ensures
            ``from gaia.engine.lang import <name>`` is present, adding each
            missing name to the existing import (sorted alphabetically) or
            synthesising a fresh import line near the top. Idempotent.
        export: Per-verb export gate (G5). When ``False``, the writer
            leaves ``__all__`` untouched even if ``new_label`` is supplied
            — used by verbs whose output is structural / scaffold / advisory
            (notes, scaffolds, register_prior) so the rendered package's
            public surface stays curated.

    Returns:
        A :class:`WriteResult` capturing the appended snippet, whether
        ``__all__`` was mutated, any ``__all__`` warning, and the symbols
        for which sibling-import lines were newly added.
    """
    existing = target_file_path.read_text() if target_file_path.exists() else ""

    # ---- engine-lang / engine.bayes import insertion (G1) ------------- #
    if required_imports:
        # ``bayes`` lives at ``gaia.engine.bayes`` — route it through a
        # dedicated helper so the engine-lang aggregate import stays narrow.
        lang_names = tuple(name for name in required_imports if name != "bayes")
        if "bayes" in required_imports:
            existing = _ensure_engine_bayes_import(existing)
        if lang_names:
            existing = _ensure_engine_lang_imports(existing, lang_names)

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
    if new_label is not None and export:
        new_text, all_managed, all_warning = _maybe_update_all_block(new_text, new_label)

    # ---- __all__ end-of-module placement (G12) ------------------------- #
    # Always run after the optional insert so an already-present ``__all__``
    # that lives between imports and statements migrates to the end on the
    # next write. Idempotent: a tail ``__all__`` stays put.
    new_text = _move_all_to_end(new_text)

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


def _collect_existing_imports(tree: ast.Module) -> dict[str, set[str]]:
    """Map ``package_name -> {imported symbols}`` from a parsed module's body."""
    already_imported: dict[str, set[str]] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module:
            already_imported.setdefault(node.module, set()).update(
                alias.asname or alias.name for alias in node.names
            )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                already_imported.setdefault(alias.asname or alias.name, set())
    return already_imported


def _select_new_imports(
    needed: tuple[tuple[str, str], ...],
    already_imported: dict[str, set[str]],
    default_package: str | None,
) -> tuple[dict[str, list[str]], list[str]]:
    """Filter ``needed`` against ``already_imported`` and group by package.

    Returns ``(grouped, added)`` where ``grouped`` is ``{pkg: [symbols]}`` for
    fresh entries and ``added`` is a flat list of newly-introduced symbols.
    """
    grouped_new: dict[str, list[str]] = {}
    added_symbols: list[str] = []
    for symbol, pkg_in in needed:
        pkg = pkg_in or default_package or ""
        if not pkg or symbol in already_imported.get(pkg, set()):
            continue
        if symbol in grouped_new.get(pkg, []):
            continue
        grouped_new.setdefault(pkg, []).append(symbol)
        added_symbols.append(symbol)
    return grouped_new, added_symbols


def _splice_imports(source: str, tree: ast.Module, grouped_new: dict[str, list[str]]) -> str:
    """Splice the ``from <pkg> import ...`` lines into ``source`` at the right spot."""
    insertion_offset = _find_import_insertion_offset(source, tree)
    new_lines = [
        f"from {pkg} import {', '.join(sorted(symbols))}"
        for pkg, symbols in sorted(grouped_new.items())
    ]
    insert_block = "\n".join(new_lines) + "\n"
    head = source[:insertion_offset]
    tail = source[insertion_offset:]
    if head and not head.endswith("\n"):
        head += "\n"
    if head and not head.endswith("\n\n"):
        head += "\n"
    if tail and not tail.startswith("\n"):
        insert_block += "\n"
    return head + insert_block + tail


def _ensure_sibling_imports(
    source: str,
    needed: tuple[tuple[str, str], ...],
    *,
    default_package: str | None,
) -> tuple[str, list[str]]:
    """Insert ``from <pkg> import <symbol>`` for any missing ``needed`` entries.

    Cheap approach: parse the source to find existing top-level imports;
    group new entries by package; append a single ``from <pkg> import
    <symbols>`` line per package after the leading docstring + future-
    imports block. Order within a group is alphabetical.

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

    already_imported = _collect_existing_imports(tree)
    grouped_new, added_symbols = _select_new_imports(needed, already_imported, default_package)
    if not grouped_new:
        return source, []
    return _splice_imports(source, tree, grouped_new), added_symbols


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
# __all__ auto-management                                                     #
# --------------------------------------------------------------------------- #


def _maybe_update_all_block(source: str, new_label: str) -> tuple[str, bool, str | None]:
    """Insert ``new_label`` into a module-level ``__all__ = [...]`` if present.

    Behavior:

    * No top-level ``__all__`` assignment present → return source
      unchanged. We do **not** synthesize ``__all__``; that is
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

    target_assign: ast.Assign | ast.AnnAssign | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            target_assign = node
            break
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
            and node.value is not None
        ):
            target_assign = node
            break

    if target_assign is None:
        return source, False, None

    rhs = target_assign.value
    if rhs is None or not isinstance(rhs, (ast.List, ast.Tuple)):
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


# --------------------------------------------------------------------------- #
# Engine-lang import injection (G1)                                           #
# --------------------------------------------------------------------------- #


_ENGINE_LANG_MODULE = "gaia.engine.lang"
_ENGINE_PACKAGE = "gaia.engine"
_ENGINE_BAYES_MODULE = "gaia.engine.bayes"


def _ensure_engine_bayes_import(source: str) -> str:
    """Ensure ``bayes`` is reachable as a top-level name.

    Recognised shapes (idempotent, any match short-circuits):

    * ``from gaia.engine import bayes``
    * ``from gaia.engine.bayes import ...`` (the ``bayes`` name itself is
      not bound, but the submodule's attributes are — fall through to
      adding ``from gaia.engine import bayes`` so ``bayes.Binomial(...)``
      resolves)
    * ``import gaia.engine.bayes as bayes``

    When none are present, the helper inserts
    ``from gaia.engine import bayes`` at the standard insertion offset.
    """
    if not source.strip():
        tree = ast.parse("")
    else:
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return source

    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == _ENGINE_PACKAGE:
            for alias in node.names:
                if (alias.asname or alias.name) == "bayes":
                    return source
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == _ENGINE_BAYES_MODULE and (alias.asname or "") == "bayes":
                    return source

    new_line = f"from {_ENGINE_PACKAGE} import bayes\n"
    insertion_offset = _find_import_insertion_offset(source, tree)
    head = source[:insertion_offset]
    tail = source[insertion_offset:]
    if head and not head.endswith("\n"):
        head += "\n"
    block = new_line
    if tail and not tail.startswith("\n"):
        block += "\n"
    return head + block + tail


def _ensure_engine_lang_imports(source: str, required_imports: tuple[str, ...]) -> str:
    """Ensure ``from gaia.engine.lang import <names>`` includes every name.

    Idempotent. When ``gaia.engine.lang`` is already imported, the helper
    extends the existing ``names`` clause with the missing entries
    (alphabetically sorted, parenthesised if the line exceeds 88 cols).
    When the module is not yet imported, the helper synthesises a fresh
    ``from gaia.engine.lang import <names>`` line at the standard
    insertion offset (after the module docstring + ``from __future__``
    block, before the first non-import statement).

    Names that are already present (whether under their canonical name or
    via ``asname``) are not duplicated. Names that appear on a separately
    declared ``from gaia.engine.lang.<sub> import ...`` line are ignored —
    we only manage the canonical ``gaia.engine.lang`` aggregate import.
    """
    if not required_imports:
        return source
    needed = sorted({name for name in required_imports if name})
    if not needed:
        return source

    try:
        tree = ast.parse(source) if source.strip() else ast.parse("")
    except SyntaxError:
        return source

    target_node: ast.ImportFrom | None = None
    already: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.ImportFrom) and node.module == _ENGINE_LANG_MODULE:
            target_node = node
            for alias in node.names:
                already.add(alias.asname or alias.name)
            break

    missing = [name for name in needed if name not in already]
    if not missing:
        return source

    if target_node is not None:
        return _extend_engine_lang_import(source, target_node, missing)
    return _insert_engine_lang_import(source, tree, missing)


def _extend_engine_lang_import(
    source: str,
    target_node: ast.ImportFrom,
    missing: list[str],
) -> str:
    """Replace ``target_node``'s text span with a new import line carrying
    the union of the existing names and ``missing``.
    """
    combined = sorted({alias.asname or alias.name for alias in target_node.names} | set(missing))
    new_line = _render_engine_lang_import(combined)
    start_line = target_node.lineno
    end_line = target_node.end_lineno or target_node.lineno
    lines = source.splitlines(keepends=True)
    head = "".join(lines[: start_line - 1])
    tail = "".join(lines[end_line:])
    sep = "\n" if not new_line.endswith("\n") else ""
    return head + new_line + sep + tail


def _insert_engine_lang_import(
    source: str,
    tree: ast.Module,
    missing: list[str],
) -> str:
    """Insert a fresh ``from gaia.engine.lang import ...`` line into source."""
    new_line = _render_engine_lang_import(sorted(set(missing))) + "\n"
    insertion_offset = _find_import_insertion_offset(source, tree)
    head = source[:insertion_offset]
    tail = source[insertion_offset:]
    if head and not head.endswith("\n"):
        head += "\n"
    block = new_line
    if tail and not tail.startswith("\n"):
        block += "\n"
    return head + block + tail


def _render_engine_lang_import(names: list[str]) -> str:
    """Render the ``from gaia.engine.lang import <names>`` line.

    Single-line shape when the rendered text fits within 88 columns;
    parenthesised multi-line shape otherwise (one name per line, sorted
    alphabetically, trailing comma — matches the hand-authored style in
    ``examples/galileo-v0-5-gaia``).
    """
    single = f"from {_ENGINE_LANG_MODULE} import {', '.join(names)}"
    if len(single) <= 88:
        return single
    body = "\n".join(f"    {name}," for name in names)
    return f"from {_ENGINE_LANG_MODULE} import (\n{body}\n)"


# --------------------------------------------------------------------------- #
# __all__ end-of-module placement (G12)                                       #
# --------------------------------------------------------------------------- #


def _move_all_to_end(source: str) -> str:
    """Migrate a top-level ``__all__`` assignment to the tail of the module.

    No-op when ``__all__`` is absent, when it already lives at the end of
    the module (no non-comment, non-blank statement after it), or when
    parsing the source fails. Otherwise the assignment's text span is
    excised and reappended at the bottom with a single blank-line
    separator from the preceding statement. Idempotent.
    """
    if not source.strip():
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    target_node: ast.Assign | ast.AnnAssign | None = None
    target_idx: int = -1
    for idx, node in enumerate(tree.body):
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            target_node = node
            target_idx = idx
            break
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            target_node = node
            target_idx = idx
            break

    if target_node is None:
        return source
    if target_idx == len(tree.body) - 1:
        # Already at the end.
        return source

    start_line = target_node.lineno
    end_line = target_node.end_lineno or target_node.lineno
    lines = source.splitlines(keepends=True)
    block_text = "".join(lines[start_line - 1 : end_line]).rstrip("\n")
    remainder = "".join(lines[: start_line - 1] + lines[end_line:])
    # Collapse multiple blank lines that the excision may have created.
    remainder_stripped = remainder.rstrip()
    if not remainder_stripped:
        return block_text + "\n"
    return remainder_stripped + "\n\n" + block_text + "\n"


__all__ = ["WriteResult", "append_statement"]
