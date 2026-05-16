"""Alpha 0 tombstone — gaia.engine.lang.types relocated to gaia.engine.lang.formula."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.engine.lang.types", "gaia.engine.lang.formula")
