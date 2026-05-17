"""``gaia author`` subcommand group — agent-first authoring CLI.

This module exposes the ``gaia author <verb>`` namespace, where ``<verb>``
matches one of the DSL surface verbs (``claim`` / ``equal`` / ``derive`` and
so on). The CLI is the primary consumer surface for an LLM agent doing
end-to-end authoring on a Gaia knowledge package: it owns identifier
collision checks, reference resolution, pre-write defensive validation,
file appending, and (by default) a post-write ``gaia build check`` to make
sure the package still compiles. Output is JSON-by-default through a
uniform envelope (see :mod:`._envelope`); ``--human`` opts into a
human-readable rendering of the same payload.

R1 milestone ships 3 representative verbs end-to-end (``claim`` / ``equal``
/ ``derive``) plus two stubs (``compose`` / ``composition`` — deferred to
R2+ because their content is fundamentally an arbitrary-Python function
body, not a CLI-flag-shaped operation). R2 fills in the remaining 14
statement-level verbs against the same pre-write + envelope skeleton.

See ``docs/specs`` / 协作单 BOmHwyFRCixqy0k7gR3cCNMInId for the full
contract and rationale.
"""

from __future__ import annotations

from gaia.cli.commands.author._stubs import compose_command, composition_command
from gaia.cli.commands.author.claim import claim_command
from gaia.cli.commands.author.derive import derive_command
from gaia.cli.commands.author.equal import equal_command

__all__ = [
    "claim_command",
    "compose_command",
    "composition_command",
    "derive_command",
    "equal_command",
]
