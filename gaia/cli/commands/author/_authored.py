"""Canonical ``authored/`` submodule helpers shared across the CLI.

Everything ``gaia author`` writes lands in a dedicated re-exported
submodule ``src/<import_name>/authored/`` — never the package-root
``__init__.py``. This module owns the single source of truth for that
convention so the writer (:mod:`._prewrite` / :mod:`._writer`), the
snapshot reader (:mod:`.list`), and the scaffolders
(:mod:`gaia.cli.commands.pkg.scaffold` / :mod:`gaia.cli.commands.init`)
all agree on:

* the submodule directory name (``authored``),
* the freshly-minted ``authored/__init__.py`` body (a literal
  ``__all__: list[str] = []``),
* the root-``__init__.py`` re-export line (``from .authored import *``)
  plus the ``__all__`` merge that composes CLI-authored statements back
  into the complete DSL by import.

The model: hand-authored DSL lives in the package root (and the author's
own modules); CLI-authored DSL lives in ``authored/``; the two compose
via the re-export, never by interleaving in one file. There is no
migration / legacy detection — CLI-authored and hand-authored ``.py`` are
byte-identical, so detection would false-positive. ``gaia author`` simply
writes to ``authored/`` going forward.
"""

from __future__ import annotations

import ast
from pathlib import Path

#: Name of the re-exported submodule that holds all CLI-authored output.
AUTHORED_PACKAGE = "authored"

#: The literal re-export line the package-root ``__init__.py`` carries so
#: ``authored/`` statements compose into the complete DSL by import.
AUTHORED_REEXPORT_LINE = "from .authored import *"

#: Fresh ``authored/__init__.py`` body: a literal empty ``__all__`` that
#: the writer extends as statements are appended.
AUTHORED_INIT_BODY = "__all__: list[str] = []\n"

#: The two import lines a re-exporting root ``__init__.py`` carries: a
#: star-import of ``authored`` plus a bound alias used by the ``__all__``
#: merge line. Shared by :data:`ROOT_REEXPORT_BLOCK` (the scaffolder seed)
#: and :func:`ensure_root_reexport` (the on-the-fly merge into an existing
#: root), so both stay byte-identical on the import portion.
AUTHORED_REEXPORT_IMPORTS = (
    "from .authored import *  # noqa: F403  (CLI-authored statements)\n"
    "from . import authored as _authored\n"
)


def _reexport_merge_line(container: str) -> str:
    """Return the ``__all__`` merge line preserving the container kind.

    The merge composes ``authored.__all__`` into the root ``__all__``. We
    emit a tuple-form merge (``(*__all__, *_authored.__all__)``) when the
    existing root ``__all__`` is a tuple so we don't silently rebind a
    ``tuple[str, ...]``-annotated name to a list; otherwise the list form.

    Args:
        container: ``"tuple"`` to emit the tuple form; any other value
            (``"list"`` / ``"none"``) emits the list form.

    Returns:
        The single merge line, newline-terminated.
    """
    if container == "tuple":
        return "__all__ = (*__all__, *_authored.__all__)\n"
    return "__all__ = [*__all__, *_authored.__all__]\n"


#: Tail block appended to a freshly-scaffolded package root ``__init__.py``
#: so it re-exports the ``authored/`` submodule and merges its ``__all__``.
#: Fresh packages always seed a list ``__all__``, so this is the list-form
#: block (byte-identical to the pre-refactor literal).
ROOT_REEXPORT_BLOCK = AUTHORED_REEXPORT_IMPORTS + "\n" + _reexport_merge_line("list")


def authored_dir(source_root: Path) -> Path:
    """Return the ``authored/`` directory under a package source root."""
    return source_root / AUTHORED_PACKAGE


def authored_init(source_root: Path) -> Path:
    """Return the ``authored/__init__.py`` path under a package source root."""
    return source_root / AUTHORED_PACKAGE / "__init__.py"


def ensure_authored_submodule(source_root: Path, root_init: Path) -> Path:
    """Ensure the ``authored/`` submodule exists and the root re-exports it.

    Idempotent. Creates ``authored/__init__.py`` (with an empty literal
    ``__all__``) when missing, and inserts the ``from .authored import *``
    re-export + ``__all__`` merge into the package-root ``__init__.py``
    when not already present.

    Args:
        source_root: ``src/<import_name>/`` (the package source root).
        root_init: The package-root ``__init__.py`` path.

    Returns:
        The path to ``authored/__init__.py``.
    """
    init_path = authored_init(source_root)
    if not init_path.exists():
        init_path.parent.mkdir(parents=True, exist_ok=True)
        init_path.write_text(AUTHORED_INIT_BODY)
    ensure_root_reexport(root_init)
    return init_path


def root_reexports_authored(source: str) -> bool:
    """Return True when ``source`` already imports ``*`` from ``.authored``.

    Recognises the canonical ``from .authored import *`` shape (the only
    form the scaffolders emit). A relative import of the ``authored``
    submodule that binds ``*`` counts; anything else returns False.
    """
    try:
        tree = ast.parse(source) if source.strip() else ast.parse("")
    except SyntaxError:
        return False
    for node in tree.body:
        if (
            isinstance(node, ast.ImportFrom)
            and node.level == 1
            and node.module == AUTHORED_PACKAGE
            and any(alias.name == "*" for alias in node.names)
        ):
            return True
    return False


def ensure_root_reexport(root_init: Path) -> None:
    """Insert the ``authored`` re-export block into the root ``__init__.py``.

    Idempotent: a root init that already re-exports ``authored`` is left
    untouched. When the root init has no ``__all__`` of its own we still
    append the block — the merge line ``__all__ = [*__all__, ...]`` would
    fail without a pre-existing ``__all__``, so we seed one defensively.
    """
    existing = root_init.read_text() if root_init.exists() else ""
    if root_reexports_authored(existing):
        return
    has_all = _has_module_all(existing)
    block = ""
    if existing and not existing.endswith("\n"):
        block += "\n"
    if existing.strip():
        block += "\n"
    if has_all:
        # Preserve the existing container kind for the merge so a
        # ``tuple[str, ...]``-declared ``__all__`` stays a tuple.
        block += (
            AUTHORED_REEXPORT_IMPORTS + "\n" + _reexport_merge_line(_all_container_kind(existing))
        )
    else:
        # No existing ``__all__`` — seed a list and append the list-form
        # block (== ROOT_REEXPORT_BLOCK).
        block += "__all__: list[str] = []\n\n"
        block += ROOT_REEXPORT_BLOCK
    root_init.write_text(existing + block)


def _all_container_kind(source: str) -> str:
    """Classify the container of a module-level ``__all__`` in ``source``.

    Returns ``"tuple"`` when ``__all__`` is annotated ``tuple[...]`` or its
    value is an ``ast.Tuple``; ``"list"`` when its value is an ``ast.List``
    or it is annotated ``list[...]``; ``"none"`` when there is no top-level
    ``__all__`` (or the source does not parse).
    """
    try:
        tree = ast.parse(source) if source.strip() else ast.parse("")
    except SyntaxError:
        return "none"
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            if isinstance(node.value, ast.Tuple):
                return "tuple"
            if isinstance(node.value, ast.List):
                return "list"
            return "none"
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            if _annotation_base(node.annotation) == "tuple" or isinstance(node.value, ast.Tuple):
                return "tuple"
            if _annotation_base(node.annotation) == "list" or isinstance(node.value, ast.List):
                return "list"
            return "none"
    return "none"


def _annotation_base(annotation: ast.expr | None) -> str | None:
    """Return the base name of an annotation like ``tuple[...]`` / ``list[...]``."""
    if annotation is None:
        return None
    target = annotation.value if isinstance(annotation, ast.Subscript) else annotation
    if isinstance(target, ast.Name):
        return target.id
    return None


def _has_module_all(source: str) -> bool:
    """Return True when ``source`` declares a module-level ``__all__``."""
    try:
        tree = ast.parse(source) if source.strip() else ast.parse("")
    except SyntaxError:
        return False
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            return True
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
        ):
            return True
    return False


__all__ = [
    "AUTHORED_INIT_BODY",
    "AUTHORED_PACKAGE",
    "AUTHORED_REEXPORT_IMPORTS",
    "AUTHORED_REEXPORT_LINE",
    "ROOT_REEXPORT_BLOCK",
    "authored_dir",
    "authored_init",
    "ensure_authored_submodule",
    "ensure_root_reexport",
    "root_reexports_authored",
]
