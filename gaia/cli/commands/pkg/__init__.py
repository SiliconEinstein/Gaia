"""``gaia pkg`` subcommand group — package-level operations.

The pkg group hosts package-level verbs that are not author-statement
authoring (those live in ``gaia.cli.commands.author``). ``gaia pkg
scaffold`` is the agent-facing package initialisation verb that
complements the existing legacy ``gaia init`` / ``gaia pkg add`` /
``gaia pkg register`` flow with structured JSON output, pre-validation,
and idempotent-by-default semantics. ``gaia pkg add-module`` scaffolds
sibling Python modules (e.g. ``priors.py``) so the
``gaia author <verb> --file <relative>`` multi-file path has a target.

See ``docs/reference/cli/pkg.md`` for the per-verb contract.
"""

from __future__ import annotations

from gaia.cli.commands.pkg.add_import import add_import_command
from gaia.cli.commands.pkg.add_module import add_module_command
from gaia.cli.commands.pkg.formalize import formalize_command
from gaia.cli.commands.pkg.lock_check import lock_check_command
from gaia.cli.commands.pkg.migrate import migrate_command
from gaia.cli.commands.pkg.mount import mount_command
from gaia.cli.commands.pkg.scaffold import scaffold_command

__all__ = [
    "add_import_command",
    "add_module_command",
    "formalize_command",
    "lock_check_command",
    "migrate_command",
    "mount_command",
    "scaffold_command",
]
