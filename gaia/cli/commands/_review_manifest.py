"""Alpha 0 tombstone — ``load_or_generate_review_manifest`` moved to ``gaia.engine.inquiry``.

The full set of ReviewManifest helpers (merge / latest_reviews /
REVIEW_MANIFEST_REL_PATH) lives at ``gaia.engine.inquiry.review_manifest``
as engine-internal helpers; only ``load_or_generate_review_manifest`` is
in the public ``gaia.engine.inquiry.__all__`` surface.
"""

from gaia._legacy_imports import TOMBSTONED_SYMBOLS, _tombstoned_symbol_getattr

__getattr__ = _tombstoned_symbol_getattr(
    "gaia.cli.commands._review_manifest",
    TOMBSTONED_SYMBOLS["gaia.cli.commands._review_manifest"],
)
