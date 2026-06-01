"""``gaia author`` subcommand group — optional authoring convenience.

This module exposes the ``gaia author <verb>`` namespace, where ``<verb>``
matches one of the DSL surface verbs (``claim`` / ``artifact`` /
``figure`` / ``equal`` / ``derive`` / ``note`` / ``question`` /
``contradict`` / ``exclusive`` / ``decompose`` / ``observe`` /
``compute`` / ``infer`` / ``associate`` / ``parameter`` /
``register_prior`` / ``depends_on`` / ``candidate_relation`` /
``materialize`` / ``variable`` / ``compose`` / ``composition``). Direct
SDK authoring (``gaia sdk`` + writing the DSL in Python) is the primary
path; this CLI is an OPTIONAL convenience for humans and agents alike.
When used, it owns identifier collision checks, reference resolution,
pre-write defensive validation, file appending into the package's
composed ``authored/`` submodule (never the package-root
``__init__.py``), and (by default) a post-write ``gaia build check`` to
make sure the package still compiles. Output is JSON-by-default through a
uniform envelope (see :mod:`._envelope`); ``--human`` opts into a
human-readable rendering of the same payload.

The author surface ships 22 verbs end-to-end against a uniform pre-write
envelope skeleton: 20 statement-emitting verbs (``claim`` /
``artifact`` / ``figure`` / ``equal`` / ``derive`` / ``note`` /
``question`` / ``contradict`` / ``exclusive`` / ``decompose`` /
``observe`` / ``compute`` / ``infer`` / ``associate`` / ``parameter`` /
``register_prior`` / ``depends_on`` / ``candidate_relation`` /
``materialize`` / ``variable``) plus the two file-based ``compose`` /
``composition``
validate-and-register verbs (see :mod:`.compose`). Prose-mode
``--<arg>-content`` flags, two pre-write warning kinds, and a
restricted-globals formula sandbox round out the authoring surface; the
engine's deprecation catalog is discovered via an AST scan over the DSL
source (see :mod:`._deprecation_scan`).

See ``docs/reference/cli/author.md`` for the per-verb contract.
"""

from __future__ import annotations

from gaia.cli.commands.author.artifact import artifact_command, figure_command
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
from gaia.cli.commands.author.list import list_command
from gaia.cli.commands.author.materialize import materialize_command
from gaia.cli.commands.author.note import note_command
from gaia.cli.commands.author.observe import observe_command
from gaia.cli.commands.author.parameter import parameter_command
from gaia.cli.commands.author.question import question_command
from gaia.cli.commands.author.register_prior import register_prior_command
from gaia.cli.commands.author.variable import variable_command

__all__ = [
    "artifact_command",
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
    "figure_command",
    "infer_command",
    "list_command",
    "materialize_command",
    "note_command",
    "observe_command",
    "parameter_command",
    "question_command",
    "register_prior_command",
    "variable_command",
]
