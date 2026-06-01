"""Unit tests for the canonical ``authored/`` submodule helpers.

Focus: :func:`ensure_root_reexport` must compose the ``authored`` import block
into an existing root ``__init__.py`` *without* silently changing the
container kind of a pre-existing ``__all__`` — a ``tuple`` stays a tuple,
a ``list`` stays a list — and the fresh-package seed stays byte-identical
to ``ROOT_REEXPORT_BLOCK``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from gaia.cli.commands.author._authored import (
    AUTHORED_REEXPORT_IMPORTS,
    ROOT_REEXPORT_BLOCK,
    ensure_root_reexport,
    root_reexports_authored,
)

pytestmark = pytest.mark.pr_gate


def _all_node(source: str) -> ast.expr | None:
    """Return the value node of the *last* top-level ``__all__`` assignment."""
    tree = ast.parse(source)
    found: ast.expr | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            found = node.value
    return found


def test_root_reexport_block_is_imports_plus_list_merge() -> None:
    """The scaffolder seed is the imports plus the list-form merge line."""
    assert ROOT_REEXPORT_BLOCK == (
        AUTHORED_REEXPORT_IMPORTS + "\n__all__ = [*__all__, *_authored.__all__]\n"
    )


def test_ensure_root_reexport_preserves_tuple_all(tmp_path: Path) -> None:
    """A ``tuple[str, ...]`` root ``__all__`` keeps a tuple merge."""
    root = tmp_path / "__init__.py"
    root.write_text('__all__: tuple[str, ...] = ("alpha", "beta")\n')

    ensure_root_reexport(root)
    result = root.read_text()

    assert root_reexports_authored(result)
    assert "__all__ = (*__all__, *_authored.__all__)" in result
    assert "__all__ = [*__all__, *_authored.__all__]" not in result
    # The merge line is a real tuple, matching the annotation.
    merge = _all_node(result)
    assert isinstance(merge, ast.Tuple)


def test_ensure_root_reexport_preserves_list_all(tmp_path: Path) -> None:
    """A list root ``__all__`` keeps the list-form merge."""
    root = tmp_path / "__init__.py"
    root.write_text('__all__ = ["alpha"]\n')

    ensure_root_reexport(root)
    result = root.read_text()

    assert root_reexports_authored(result)
    assert "__all__ = [*__all__, *_authored.__all__]" in result
    merge = _all_node(result)
    assert isinstance(merge, ast.List)


def test_ensure_root_reexport_seeds_list_when_no_all(tmp_path: Path) -> None:
    """No pre-existing ``__all__`` seeds a list and appends the canonical block."""
    root = tmp_path / "__init__.py"
    root.write_text("x = 1\n")

    ensure_root_reexport(root)
    result = root.read_text()

    assert "__all__: list[str] = []" in result
    assert result.endswith(ROOT_REEXPORT_BLOCK)


def test_ensure_root_reexport_is_idempotent(tmp_path: Path) -> None:
    """A second call leaves an already-importing root untouched."""
    root = tmp_path / "__init__.py"
    root.write_text('__all__: tuple[str, ...] = ("alpha",)\n')

    ensure_root_reexport(root)
    once = root.read_text()
    ensure_root_reexport(root)
    twice = root.read_text()

    assert once == twice


def test_ensure_root_reexport_upgrades_legacy_star_block(tmp_path: Path) -> None:
    """Old scaffold blocks gain runtime binding import without duplicating __all__."""
    root = tmp_path / "__init__.py"
    root.write_text(
        "__all__: list[str] = []\n\n"
        "from .authored import *  # noqa: F403  (CLI-authored statements)\n"
        "from . import authored as _authored\n\n"
        "__all__ = [*__all__, *_authored.__all__]\n"
    )

    ensure_root_reexport(root)
    result = root.read_text()

    assert "for _gaia_name, _gaia_value in vars(_authored).items():" in result
    assert result.count("__all__ = [*__all__, *_authored.__all__]") == 1
