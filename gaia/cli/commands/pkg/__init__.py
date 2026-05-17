"""``gaia pkg`` subcommand group — package-level operations.

The pkg group hosts package-level verbs that are not author-statement
authoring (those live in ``gaia.cli.commands.author``). R2 introduces
``gaia pkg scaffold``, the agent-facing package initialisation verb
that complements the existing legacy ``gaia init`` / ``gaia pkg add``
/ ``gaia pkg register`` flow with structured JSON output, pre-validation,
and idempotent-by-default semantics. R7 G1 adds ``gaia pkg add-module``
for scaffolding sibling Python modules (e.g. ``priors.py``) so the
``gaia author <verb> --file <relative>`` multi-file path has a target.

See 协作单 BOmHwyFRCixqy0k7gR3cCNMInId §五 (R2 + R7 rows) for the contract.
"""

from __future__ import annotations

from gaia.cli.commands.pkg.add_module import add_module_command
from gaia.cli.commands.pkg.scaffold import scaffold_command

__all__ = ["add_module_command", "scaffold_command"]
