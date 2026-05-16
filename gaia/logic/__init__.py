"""Alpha 0 tombstone — gaia.logic relocated to gaia.engine.ir.logic."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.logic", "gaia.engine.ir.logic")
