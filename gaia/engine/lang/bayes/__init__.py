"""Alpha 0 tombstone — gaia.engine.lang.bayes relocated to gaia.engine.bayes."""

from gaia._legacy_imports import _tombstoned_namespace_getattr

__getattr__ = _tombstoned_namespace_getattr("gaia.engine.lang.bayes", "gaia.engine.bayes")
