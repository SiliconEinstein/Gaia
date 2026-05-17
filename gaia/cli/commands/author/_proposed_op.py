"""Proposed-author-operation dataclass shared by every ``gaia author`` verb.

The :class:`ProposedAuthorOp` value is the bridge between the CLI flag
surface (verb-specific argparse-shaped inputs) and the verb-agnostic
pre-write check pipeline (:mod:`._prewrite`). Each verb constructs one of
these from its parsed arguments, hands it to ``prewrite_check``, and on
pass appends ``generated_code`` to ``target_path / source_root /
__init__.py``.

The dataclass intentionally mirrors the v0.5 runtime taxonomy from
``gaia.engine.lang.runtime.action`` — ``Reasoning`` vs ``GaiaGraph`` —
because the pre-write checks need to know, for example, whether
``self`` references in the produced statement are even allowed (warrant-
bearing reasoning) or always invalid (scaffold-only graphs).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

# OpKind mirrors the runtime distinction at a level the pre-write checks
# can use without depending on the engine import surface. ``reasoning`` is
# for warrant-bearing verbs (claim / derive / observe / compute / equal /
# contradict / exclusive / etc.); ``scaffold`` is for graph-only verbs
# (depends_on / candidate_relation / materialize). R1's three verbs are
# all reasoning-shaped, but R2 will need both, so we lock the taxonomy in
# now.
OpKind = Literal["reasoning", "scaffold"]


@dataclass
class ProposedAuthorOp:
    """A pending author operation, ready to be validated and written.

    Attributes:
        verb: DSL verb name (``"claim"``, ``"equal"``, ``"derive"``, ...).
            Drives diagnostic ``verb`` field + human-readable rendering.
        kind: Runtime taxonomy slot — see :data:`OpKind`.
        label: Module-scope identifier the generated statement binds to.
            ``None`` is legal for some verbs (the helper Claim is unnamed),
            but R1 requires it for all three implemented verbs so the
            written statement is referenceable.
        references: Identifier names that must resolve in either the
            current package's module scope or a loaded dep. Empty list
            means "no references to check".
        generated_code: The Python snippet that will be appended to the
            target package's source file if pre-write passes. Must be a
            self-contained statement; the writer adds a trailing newline
            but does not otherwise rewrite the snippet.
        required_imports: Module-level imports the generated code depends
            on. ``("derive",)`` means ``from gaia.engine.lang import
            derive`` must exist (or be added) in the target module.
            R1 verifies they're present; R2 may add missing imports
            (escalated to a separate ❓ if needed).
    """

    verb: str
    kind: OpKind
    label: str | None
    references: list[str] = field(default_factory=list)
    generated_code: str = ""
    required_imports: tuple[str, ...] = ()
    # R3 prose mode: optional auto-generated supporting statement that
    # must be written **before** ``generated_code`` (e.g. an auto-claim
    # minted from ``--conclusion-content``). Each entry is a
    # ``(label, snippet)`` tuple: the label is treated as a binding that
    # already exists in module scope for the purposes of the (c)
    # reference-resolution invariant, and the snippet is appended to the
    # source file ahead of ``generated_code`` during the write step.
    prepended_statements: tuple[tuple[str, str], ...] = ()
    # R6 inline-prose mode: verb-specific keys to merge into the final
    # envelope ``payload`` (e.g. ``derive --conclusion-prose`` tags the
    # envelope with ``conclusion_kind: "inline_prose"`` so an agent
    # consumer can distinguish the three conclusion-arg shapes without
    # parsing the source snippet). Keys must not collide with the runner-
    # owned payload fields (``target``, ``written_to``, ``label``,
    # ``verb``, ``snippet``, ``auto_generated``, ``check``).
    extra_payload: dict[str, Any] = field(default_factory=dict)
    # R7 G1 multi-file target: the relative path under ``src/<import_name>/``
    # the verb writes to. ``None`` selects ``__init__.py`` (the historic
    # default). Path is resolved by the runner against the source root
    # discovered in pre-write invariant (a).
    target_file: str | None = None
    # R7 G1 multi-file target: when the statement lands in a sibling file
    # (e.g., ``priors.py``), pre-write needs to know the cross-file
    # ``from <import_name> import <label>`` import lines that must already
    # exist (or be auto-managed) so the references resolve at engine load
    # time. The writer post-step inserts any missing entries from this
    # tuple into the target sibling file. Each entry is a (label, source)
    # pair — typically ``source`` is the bare package import name and the
    # statement becomes ``from <pkg> import <label>``.
    sibling_imports: tuple[tuple[str, str], ...] = ()
