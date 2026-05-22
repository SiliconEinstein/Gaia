"""Public AST-based source-generation primitives.

Used by both the deterministic ARM/ARA projector
(:mod:`gaia.engine.projector`) and — indirectly through
``gaia.cli.commands.author._writer`` — the agent-first author CLI. The
two consumers benefit from sharing one canonical set of helpers:

- generated and authored modules use the **same** ``from
  gaia.engine.lang import ...`` shape (the engine-lang import is
  alphabetically sorted, parenthesised over 88 columns, merged
  idempotently on rewrite);
- generated and authored modules use the **same** ``__all__`` layout
  (alphabetical literal at the end of the module, idempotently
  expanded);
- generated source is built through :func:`render_call_statement` /
  :func:`render_module` which rely on :func:`ast.unparse` for
  escaping, so projector-generated text never has to hand-escape
  quotes / backslashes / unicode in claim titles, source paths, or
  metadata values.

The three ``ensure_engine_lang_imports`` / ``maybe_update_all_block``
/ ``move_all_to_end`` helpers used to live as private symbols on
``gaia.cli.commands.author._writer``. They are pure string
transformations and the projector reuses them verbatim. Importing
from a private module would cross a privacy boundary, so this module
re-exports them under public names; the author CLI continues to call
its own internal aliases. Either path executes the exact same
implementation.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from typing import Any

from gaia.cli.commands.author._writer import (
    _ensure_engine_lang_imports as _impl_ensure_engine_lang_imports,
)
from gaia.cli.commands.author._writer import (
    _maybe_update_all_block as _impl_maybe_update_all_block,
)
from gaia.cli.commands.author._writer import (
    _move_all_to_end as _impl_move_all_to_end,
)

__all__ = [
    "Ref",
    "ensure_engine_lang_imports",
    "maybe_update_all_block",
    "move_all_to_end",
    "render_assignment",
    "render_call_statement",
    "render_module",
]


# --------------------------------------------------------------------------- #
# Public re-exports of the author-CLI writer helpers                          #
# --------------------------------------------------------------------------- #


def ensure_engine_lang_imports(source: str, required_imports: tuple[str, ...]) -> str:
    """Ensure ``from gaia.engine.lang import <names>`` covers every required name.

    Public re-export of the author-CLI writer's internal helper so the
    projector and the author CLI agree on one canonical import shape.
    Idempotent; sorts merged names alphabetically; switches to a
    parenthesised multi-line form when the rendered line exceeds 88
    columns.
    """
    return _impl_ensure_engine_lang_imports(source, required_imports)


def maybe_update_all_block(source: str, new_label: str) -> tuple[str, bool, str | None]:
    """Insert ``new_label`` into a module-level ``__all__`` literal if present.

    Public re-export. Returns ``(new_source, was_managed, warning)`` —
    a missing ``__all__`` is left absent (Gaia does not synthesise one);
    a dynamically-constructed ``__all__`` returns the source unchanged
    plus a warning string the caller can surface.
    """
    return _impl_maybe_update_all_block(source, new_label)


def move_all_to_end(source: str) -> str:
    """Move the module-level ``__all__`` literal to the end of the file.

    Public re-export. Idempotent: a tail ``__all__`` stays put.
    """
    return _impl_move_all_to_end(source)


# --------------------------------------------------------------------------- #
# AST-based statement / module builders                                       #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class Ref:
    """Sentinel: render as a bare Python name, not a string literal.

    Use this when an argument value must be an unquoted reference to
    a symbol declared elsewhere in the module (e.g. another
    projected ``claim`` label, or an import alias). Example::

        render_call_statement(
            target_label="link",
            func_name="depends_on",
            positional=[Ref("c01")],
            keywords={"given": [Ref("evidence_e01")]},
        )

    produces ``link = depends_on(c01, given=[evidence_e01])`` rather
    than ``link = depends_on('c01', given=['evidence_e01'])``.
    """

    name: str


def _literal(value: Any) -> ast.expr:
    """Return an :mod:`ast` expression representing ``value`` as a Python literal.

    Handles :class:`Ref` (bare-name reference), strings, numbers,
    bools, ``None``, lists, tuples, and dicts recursively. Falls back
    to ``ast.parse(repr(value)).body`` for anything ``ast.Constant``
    does not accept directly — this is the same trick
    :func:`ast.unparse` uses internally for constants and means we
    never have to hand-escape a string into Python source.
    """
    if isinstance(value, Ref):
        return ast.Name(id=value.name, ctx=ast.Load())
    if value is None or isinstance(value, (str, int, float, bool, bytes)):
        return ast.Constant(value=value)
    if isinstance(value, list):
        return ast.List(elts=[_literal(v) for v in value], ctx=ast.Load())
    if isinstance(value, tuple):
        return ast.Tuple(elts=[_literal(v) for v in value], ctx=ast.Load())
    if isinstance(value, dict):
        # ``ast.Dict.keys`` is typed ``list[expr | None]`` because
        # ``{**other}`` is encoded as a ``None`` key. We never emit
        # that shape, but mypy needs the variance hint.
        dict_keys: list[ast.expr | None] = [_literal(k) for k in value]
        dict_values: list[ast.expr] = [_literal(v) for v in value.values()]
        return ast.Dict(keys=dict_keys, values=dict_values)
    return ast.parse(repr(value), mode="eval").body


def render_call_statement(
    *,
    target_label: str | None,
    func_name: str,
    positional: list[Any] | None = None,
    keywords: dict[str, Any] | None = None,
) -> str:
    """Return Python source for one ``target = func_name(...)`` call.

    Examples:
        >>> render_call_statement(target_label="c01", func_name="claim",
        ...                       positional=["A claim."], keywords={"title": "C01"})
        "c01 = claim('A claim.', title='C01')"

    All values pass through :func:`_literal` and ``ast.unparse``, so
    embedded quotes, backslashes, and newlines are escaped by the
    parser — no manual handling required at the call site.
    """
    positional = positional or []
    keywords = keywords or {}
    call = ast.Call(
        func=ast.Name(id=func_name, ctx=ast.Load()),
        args=[_literal(v) for v in positional],
        keywords=[ast.keyword(arg=k, value=_literal(v)) for k, v in keywords.items()],
    )
    if target_label is None:
        node: ast.stmt = ast.Expr(value=call)
    else:
        node = ast.Assign(
            targets=[ast.Name(id=target_label, ctx=ast.Store())],
            value=call,
        )
    return ast.unparse(ast.fix_missing_locations(node))


def render_assignment(target_label: str, value: Any) -> str:
    """Return ``label = <literal>`` source for arbitrary Python-literal values."""
    node = ast.Assign(
        targets=[ast.Name(id=target_label, ctx=ast.Store())],
        value=_literal(value),
    )
    return ast.unparse(ast.fix_missing_locations(node))


def render_module(
    *,
    docstring: str,
    engine_imports: tuple[str, ...],
    extra_imports: tuple[str, ...] = (),
    statements: list[str],
    all_labels: list[str],
) -> str:
    """Assemble a Python module source string from typed pieces.

    Layout:

    .. code-block:: text

        \"\"\"<docstring>\"\"\"

        from gaia.engine.lang import <engine_imports>
        <extra_imports each on its own line>

        <statements joined by blank lines>

        __all__ = [<all_labels sorted alphabetically>]

    Engine-DSL imports flow through :func:`ensure_engine_lang_imports`
    and ``__all__`` flows through :func:`maybe_update_all_block` +
    :func:`move_all_to_end`, so the result is byte-shape-compatible
    with files the ``gaia author <verb>`` CLI writes.
    """
    pieces: list[str] = []
    if docstring:
        pieces.append(f'"""{docstring}"""')
    for stmt in statements:
        if stmt.strip():
            pieces.append(stmt.rstrip())
    pieces.append("__all__ = []")
    source = "\n\n".join(pieces) + "\n"

    if engine_imports:
        source = ensure_engine_lang_imports(source, tuple(engine_imports))
    for raw_import in extra_imports:
        source = _inject_extra_import(source, raw_import)

    for label in all_labels:
        source, _, _ = maybe_update_all_block(source, label)
    return move_all_to_end(source)


def _inject_extra_import(source: str, raw_import_line: str) -> str:
    """Insert *raw_import_line* after the existing import block.

    Reuses :mod:`ast` to find the last top-level ``Import`` /
    ``ImportFrom`` node and inserts the new line after it. If no
    imports exist, the line is placed right after the leading
    docstring (if any), or at the very top of the module otherwise.
    """
    raw_import_line = raw_import_line.rstrip()
    if raw_import_line in source:
        return source
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return source

    insertion_lineno = 1
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            insertion_lineno = (node.end_lineno or node.lineno) + 1
            continue
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and insertion_lineno == 1
        ):
            insertion_lineno = (node.end_lineno or node.lineno) + 1
            continue
        break

    lines = source.splitlines(keepends=True)
    head = "".join(lines[: insertion_lineno - 1])
    tail = "".join(lines[insertion_lineno - 1 :])
    if head and not head.endswith("\n\n"):
        head = head.rstrip("\n") + "\n\n"
    if tail and not tail.startswith("\n"):
        tail = "\n" + tail
    return f"{head}{raw_import_line}\n{tail}"
