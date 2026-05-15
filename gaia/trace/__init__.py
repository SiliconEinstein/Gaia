"""Alpha 0 tombstone — gaia.trace relocated to gaia.engine.trace."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.trace", "gaia.engine.trace")
