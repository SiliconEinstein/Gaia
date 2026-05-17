"""``gaia pkg`` subcommand group — package-level operations.

The pkg group hosts package-level verbs that are not author-statement
authoring (those live in ``gaia.cli.commands.author``). R2 introduces
``gaia pkg scaffold``, the agent-facing package initialisation verb
that complements the existing legacy ``gaia init`` / ``gaia pkg add``
/ ``gaia pkg register`` flow with structured JSON output, pre-validation,
and idempotent-by-default semantics.

See 协作单 BOmHwyFRCixqy0k7gR3cCNMInId §五 (R2 row) for the contract.
"""

from __future__ import annotations

from gaia.cli.commands.pkg.scaffold import scaffold_command

__all__ = ["scaffold_command"]
