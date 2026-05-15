"""Alpha 0 tombstone — symbols moved to ``gaia.engine.packaging``.

This module previously held the package loading + compilation surface
(``GaiaCliError`` plus 6 helpers). In alpha 0 they live at
``gaia.engine.packaging`` and ``GaiaCliError`` is renamed to
``GaiaPackagingError``. Attribute access on the old paths raises
``ImportError`` pointing to the new location.
"""

from gaia._legacy_imports import TOMBSTONED_SYMBOLS, _tombstoned_symbol_getattr

__getattr__ = _tombstoned_symbol_getattr(
    "gaia.cli._packages",
    TOMBSTONED_SYMBOLS["gaia.cli._packages"],
)
