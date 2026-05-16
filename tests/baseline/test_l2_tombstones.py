"""Phase 0 Layer 2 — alpha 0 import tombstones (negative contract).

Locks the namespace tombstones and per-symbol redirects defined in
``gaia/_legacy_imports.py``. Every old path raises ``ImportError`` whose
message names the canonical new path.
"""

from __future__ import annotations

import importlib
import sys
from collections.abc import Generator

import pytest

from gaia._legacy_imports import TOMBSTONED_NAMESPACES, TOMBSTONED_SYMBOLS


def _drop_tombstoned_modules() -> None:
    """Keep tombstone imports from poisoning later compatibility-import tests."""
    for old_ns in TOMBSTONED_NAMESPACES:
        for name in list(sys.modules):
            if name == old_ns or name.startswith(f"{old_ns}."):
                sys.modules.pop(name, None)
        parent_name, _, attr = old_ns.rpartition(".")
        parent = sys.modules.get(parent_name)
        if parent is not None:
            parent.__dict__.pop(attr, None)


@pytest.fixture(autouse=True)
def cleanup_tombstoned_modules() -> Generator[None, None, None]:
    yield
    _drop_tombstoned_modules()


@pytest.mark.parametrize("old_ns,new_ns", sorted(TOMBSTONED_NAMESPACES.items()))
def test_namespace_tombstone(old_ns: str, new_ns: str) -> None:
    mod = importlib.import_module(old_ns)
    with pytest.raises(ImportError, match=new_ns.replace(".", r"\.")):
        getattr(mod, "some_symbol_that_used_to_be_public")  # noqa: B009 — explicit attribute lookup to trigger ImportError


@pytest.mark.parametrize(
    "old_ns,symbol,new_path",
    sorted(
        (old_ns, symbol, new_path)
        for old_ns, mapping in TOMBSTONED_SYMBOLS.items()
        for symbol, new_path in mapping.items()
    ),
)
def test_symbol_tombstone(old_ns: str, symbol: str, new_path: str) -> None:
    mod = importlib.import_module(old_ns)
    with pytest.raises(ImportError, match=new_path.replace(".", r"\.")):
        getattr(mod, symbol)


def test_namespace_tombstones_have_engine_targets() -> None:
    """Every tombstone's destination must be importable."""
    for new_ns in TOMBSTONED_NAMESPACES.values():
        importlib.import_module(new_ns)


@pytest.mark.parametrize(
    "old_path,new_path",
    [
        ("gaia.bp.factor_graph", "gaia.engine.bp.factor_graph"),
        ("gaia.lang.runtime", "gaia.engine.lang.runtime"),
        ("gaia.ir.operator", "gaia.engine.ir.operator"),
        ("gaia.engine.lang.bayes.compiler", "gaia.engine.bayes.compiler"),
        ("gaia.engine.lang.types.primitives", "gaia.engine.lang.formula.primitives"),
        ("gaia.engine.logic.propositional", "gaia.engine.ir.logic.propositional"),
        ("gaia.logic.propositional", "gaia.engine.ir.logic.propositional"),
        ("gaia.trace.schema", "gaia.engine.trace.schema"),
    ],
)
def test_submodule_tombstones_raise_redirect_import_error(old_path: str, new_path: str) -> None:
    """Direct old submodule imports should fail with the same redirect contract."""
    with pytest.raises(ImportError, match=new_path.replace(".", r"\.")):
        importlib.import_module(old_path)


def test_top_level_logic_tombstone_targets_demoted_logic() -> None:
    """The historical gaia.logic tombstone should point at the demoted IR logic namespace."""
    mod = importlib.import_module("gaia.logic")
    with pytest.raises(ImportError, match=r"gaia\.engine\.ir\.logic\.some_symbol"):
        getattr(mod, "some_symbol")  # noqa: B009


def test_symbol_tombstones_resolve_to_real_symbols() -> None:
    """Every per-symbol redirect's destination must exist."""
    for mapping in TOMBSTONED_SYMBOLS.values():
        for new_path in mapping.values():
            module_path, _, name = new_path.rpartition(".")
            mod = importlib.import_module(module_path)
            assert hasattr(mod, name), new_path
