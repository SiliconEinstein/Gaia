"""Alpha 0 tombstone — gaia.inquiry relocated to gaia.engine.inquiry."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.inquiry", "gaia.engine.inquiry")
