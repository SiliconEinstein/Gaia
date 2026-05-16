"""Phase 0 Layer 2 — engine facade contract.

Locks the 7-submodule public surface after the PR b engine reorg:

- `gaia.engine.bayes` (19)
- `gaia.engine.bp` (17)
- `gaia.engine.ir` (32)
- `gaia.engine.lang` (93)
- `gaia.engine.inquiry` (45)
- `gaia.engine.trace` (7)
- `gaia.engine.packaging` (9)

Total 222. Adding or removing a symbol from a facade `__all__` requires
updating both `docs/reference/engine/index.md` and these counts.
"""

from __future__ import annotations

import importlib

import pytest

EXPECTED = {
    "gaia.engine.bayes": 19,
    "gaia.engine.bp": 17,
    "gaia.engine.ir": 32,
    "gaia.engine.lang": 93,
    "gaia.engine.inquiry": 45,
    "gaia.engine.trace": 7,
    "gaia.engine.packaging": 9,
}


@pytest.mark.parametrize("module_name,expected", sorted(EXPECTED.items()))
def test_facade_surface(module_name: str, expected: int) -> None:
    mod = importlib.import_module(module_name)
    assert len(mod.__all__) == expected, (module_name, len(mod.__all__), expected)
    for name in mod.__all__:
        assert hasattr(mod, name), (module_name, name)


def test_grand_total() -> None:
    total = sum(len(importlib.import_module(m).__all__) for m in EXPECTED)
    assert total == 222
