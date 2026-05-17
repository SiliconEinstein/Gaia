"""Prose-mode helpers for ``gaia author <verb>`` commands.

R3·❓A=A — uniform ``--<arg>-content`` flags. Several DSL verbs accept a
``Claim`` identifier as input (e.g. ``derive(conclusion=...)``); when the
agent does not yet have a labelled Claim for that slot, the cli can mint
a fresh one inline from prose, using a slug derived from the prose for
the label. The auto-generated claim is appended to the target file
*before* the verb's own statement, so the resulting source remains
loadable.

This module owns two narrow concerns:

1. :func:`slugify_label` — cli-derives a snake-case identifier from a
   prose string. The slug is short by design (4 leading tokens) and
   collision-suffixed against an existing-symbol set when needed.

2. :func:`build_auto_claim_statement` — render the ``label = claim(prose)``
   statement the cli will prepend to the target file when a verb's
   ``--<arg>-content`` flag is used.

The R3 scope is two named call sites: ``derive --conclusion-content`` and
``claim --predicate``. The pattern is parameterised so R4+ can extend
other verbs (``observe --conclusion-content``, ``contradict --a-content``,
etc.) by reusing this helper rather than mass-rewriting per-verb files.
"""

from __future__ import annotations

import re

_WORD_RE = re.compile(r"[A-Za-z0-9]+")


def slugify_label(
    prose: str,
    *,
    existing: set[str] | frozenset[str] | None = None,
    max_words: int = 4,
) -> str:
    """Cli-derive a snake-case identifier from prose.

    Algorithm:

    1. Lower-case + extract word tokens (``[A-Za-z0-9]+``). The first
       ``max_words`` are joined with ``_``.
    2. If the first character is a digit, prepend ``c_`` so the result is
       a valid Python identifier.
    3. If the slug is empty (e.g. prose was punctuation only), fall back
       to ``auto_claim``.
    4. If the slug collides with ``existing``, append ``_2`` / ``_3`` /
       ... until a fresh name is found.

    Args:
        prose: The natural-language content the agent passed.
        existing: Optional set of already-bound identifiers to avoid.
        max_words: Number of leading word tokens to glue together.

    Returns:
        A valid Python identifier suitable for use as a Claim label.
    """
    tokens = _WORD_RE.findall(prose.lower())[: max(1, max_words)]
    slug = "_".join(tokens) if tokens else ""
    if not slug:
        slug = "auto_claim"
    if slug[0].isdigit():
        slug = f"c_{slug}"
    # Defensive: dunder collision was already locked out by the prefix
    # rule, but if max_words is large enough the slug could still hit a
    # reserved Python keyword. The prewrite (c) collision check will
    # also catch this — keeping it terse here.
    seen = set(existing or ())
    if slug not in seen:
        return slug
    counter = 2
    while f"{slug}_{counter}" in seen:
        counter += 1
    return f"{slug}_{counter}"


def build_auto_claim_statement(label: str, prose: str) -> str:
    """Render the ``label = claim(<prose>)`` statement to prepend.

    Used by verbs that accept a ``--<arg>-content`` flag to mint a fresh
    Claim before the verb's own statement. Keeping the rendering here
    means every prose-mode verb produces the same shape: a single line
    binding a slug to ``claim(<prose>)`` with no extra kwargs.
    """
    return f"{label} = claim({prose!r})"


__all__ = ["build_auto_claim_statement", "slugify_label"]
