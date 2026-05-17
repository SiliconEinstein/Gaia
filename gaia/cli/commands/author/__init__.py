"""``gaia author`` subcommand group — agent-first authoring CLI.

This module exposes the ``gaia author <verb>`` namespace, where ``<verb>``
matches one of the DSL surface verbs (``claim`` / ``equal`` / ``derive``
/ ``note`` / ``question`` / ``contradict`` / ``exclusive`` / ``decompose``
/ ``observe`` / ``compute`` / ``infer`` / ``associate`` / ``parameter`` /
``register_prior`` / ``depends_on`` / ``candidate_relation`` /
``materialize``). The CLI is the primary consumer surface for an LLM
agent doing end-to-end authoring on a Gaia knowledge package: it owns
identifier collision checks, reference resolution, pre-write defensive
validation, file appending, and (by default) a post-write
``gaia build check`` to make sure the package still compiles. Output is
JSON-by-default through a uniform envelope (see :mod:`._envelope`);
``--human`` opts into a human-readable rendering of the same payload.

R1 shipped 3 representative verbs end-to-end (``claim`` / ``equal`` /
``derive``) plus two stubs (``compose`` / ``composition`` — deferred
because their content is fundamentally an arbitrary-Python function
body, not a CLI-flag-shaped op). R2 fills in the remaining 14
statement-level verbs against the same pre-write + envelope skeleton,
activates ``--interactive`` uniformly, and adds the ``gaia pkg
scaffold`` package-initialisation verb in a sibling module. R3 lifts
``compose`` / ``composition`` from stub to live via a file-based
validate-and-register shape (see :mod:`.compose`), plus adds prose-mode
``--<arg>-content`` flags, 2 pre-write warning kinds, and a restricted-
globals formula sandbox.

See ``docs/specs`` / 协作单 BOmHwyFRCixqy0k7gR3cCNMInId for the full
contract and rationale.
"""

from __future__ import annotations

from gaia.cli.commands.author.associate import associate_command
from gaia.cli.commands.author.candidate_relation import candidate_relation_command
from gaia.cli.commands.author.claim import claim_command
from gaia.cli.commands.author.compose import compose_command, composition_command
from gaia.cli.commands.author.compute import compute_command
from gaia.cli.commands.author.contradict import contradict_command
from gaia.cli.commands.author.decompose import decompose_command
from gaia.cli.commands.author.depends_on import depends_on_command
from gaia.cli.commands.author.derive import derive_command
from gaia.cli.commands.author.equal import equal_command
from gaia.cli.commands.author.exclusive import exclusive_command
from gaia.cli.commands.author.infer import infer_command
from gaia.cli.commands.author.materialize import materialize_command
from gaia.cli.commands.author.note import note_command
from gaia.cli.commands.author.observe import observe_command
from gaia.cli.commands.author.parameter import parameter_command
from gaia.cli.commands.author.question import question_command
from gaia.cli.commands.author.register_prior import register_prior_command

__all__ = [
    "associate_command",
    "candidate_relation_command",
    "claim_command",
    "compose_command",
    "composition_command",
    "compute_command",
    "contradict_command",
    "decompose_command",
    "depends_on_command",
    "derive_command",
    "equal_command",
    "exclusive_command",
    "infer_command",
    "materialize_command",
    "note_command",
    "observe_command",
    "parameter_command",
    "question_command",
    "register_prior_command",
]
