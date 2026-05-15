"""Alpha 0 tombstone — gaia.ir relocated to gaia.engine.ir."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.ir", "gaia.engine.ir")
