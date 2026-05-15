"""Alpha 0 tombstone — analyzers moved to ``gaia.engine.inquiry``.

``KnowledgeBreakdown``, ``analyze_knowledge_breakdown``,
``find_possible_duplicate_claims``, and ``HoleEntry`` now live at
``gaia.engine.inquiry`` (re-exported from
``gaia.engine.inquiry.check_core``). Attribute access on the old path
raises ``ImportError`` pointing to the new location.
"""

from gaia._legacy_imports import TOMBSTONED_SYMBOLS, _tombstoned_symbol_getattr

__getattr__ = _tombstoned_symbol_getattr(
    "gaia.cli.commands.check_core",
    TOMBSTONED_SYMBOLS["gaia.cli.commands.check_core"],
)
