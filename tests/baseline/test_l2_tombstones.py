"""Phase 0 Layer 2 — alpha 0 import tombstones (negative contract).

Locks the 6 namespace tombstones and 12 per-symbol redirects defined in
``gaia/_legacy_imports.py``. Every old path raises ``ImportError`` whose
message names the canonical new path.
"""

from __future__ import annotations

import importlib

import pytest

from gaia._legacy_imports import TOMBSTONED_NAMESPACES, TOMBSTONED_SYMBOLS


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


def test_symbol_tombstones_resolve_to_real_symbols() -> None:
    """Every per-symbol redirect's destination must exist."""
    for mapping in TOMBSTONED_SYMBOLS.values():
        for new_path in mapping.values():
            module_path, _, name = new_path.rpartition(".")
            mod = importlib.import_module(module_path)
            assert hasattr(mod, name), new_path
