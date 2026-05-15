"""Alpha 0 tombstone — gaia.lang relocated to gaia.engine.lang."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.lang", "gaia.engine.lang")
