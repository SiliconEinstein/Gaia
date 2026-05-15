"""Alpha 0 tombstone — gaia.bp relocated to gaia.engine.bp."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.bp", "gaia.engine.bp")
