"""Extract Pandoc-style reference markers from text.

Supports two forms:
  - Bare:      @key                   (opportunistic)
  - Bracketed: [prefix @key suffix]   (strict, Pandoc subset)

The extractor is pure — it only parses text and has no knowledge of label
tables or references.json. Resolution is done by the resolver module.
"""

from __future__ import annotations

import re

from gaia.lang.refs.types import BracketGroup, ExtractionResult, RefMarker

# Pandoc-compatible citation key:
#   - starts with letter/digit/underscore
#   - inner chars may include `:.#$%&+?<>~/-` plus word chars
#   - cannot end with punctuation
#
# We build this as two alternatives: single-char keys (just word char) or
# multi-char keys (word char + middle + word char).
_KEY = (
    r"(?:[A-Za-z0-9_][A-Za-z0-9_:.#$%&+?<>~/\-]*[A-Za-z0-9_]"
    r"|[A-Za-z0-9_])"
)

_BARE_AT_RE = re.compile(
    rf"""
    (?<!\\)              # not preceded by a backslash (escape)
    (?<![A-Za-z0-9_])    # not preceded by a word char (excludes email @)
    @({_KEY})
    """,
    re.VERBOSE,
)

# Pandoc bracket group: starts with `[`, must contain at least one unescaped
# `@key`, cannot contain nested brackets.
_BRACKET_GROUP_RE = re.compile(
    r"""
    (?<!\\)              # opening `[` not escaped
    \[
    ([^\[\]]*            # group body, no nested brackets
     (?<!\\)@[A-Za-z0-9_]   # at least one unescaped @key start
     [^\[\]]*)
    \]
    """,
    re.VERBOSE,
)

# Inside a bracket group, extract all unescaped @keys. A `\@key` is a literal.
_INNER_KEY_RE = re.compile(rf"(?<!\\)@({_KEY})")


def extract(text: str) -> ExtractionResult:
    """Scan text for reference markers, returning bracket groups and bare markers.

    Args:
        text: The source text to scan for markers.

    Returns:
        ExtractionResult containing:
        - markers: All extracted markers in source order (both bare and strict)
        - groups: All bracket groups containing at least one marker
    """
    if not text:
        return ExtractionResult(markers=(), groups=())

    markers: list[RefMarker] = []
    groups: list[BracketGroup] = []
    # Character positions covered by bracket groups, so the bare scanner can
    # skip them.
    bracket_spans: list[tuple[int, int]] = []

    # Pass 1: bracket groups
    for group_match in _BRACKET_GROUP_RE.finditer(text):
        group_start = group_match.start()
        group_end = group_match.end()
        body = group_match.group(1)
        body_offset = group_match.start(1)

        marker_indices: list[int] = []
        group_index = len(groups)
        for key_match in _INNER_KEY_RE.finditer(body):
            marker_index = len(markers)
            markers.append(
                RefMarker(
                    key=key_match.group(1),
                    start=body_offset + key_match.start(1) - 1,  # include `@`
                    end=body_offset + key_match.end(1),
                    strict=True,
                    group_index=group_index,
                )
            )
            marker_indices.append(marker_index)

        if not marker_indices:
            continue

        groups.append(
            BracketGroup(
                raw=text[group_start:group_end],
                start=group_start,
                end=group_end,
                marker_indices=tuple(marker_indices),
            )
        )
        bracket_spans.append((group_start, group_end))

    def _inside_bracket(pos: int) -> bool:
        return any(start <= pos < end for start, end in bracket_spans)

    # Pass 2: bare markers (not inside bracket groups)
    for match in _BARE_AT_RE.finditer(text):
        if _inside_bracket(match.start()):
            continue
        markers.append(
            RefMarker(
                key=match.group(1),
                start=match.start(),
                end=match.end(),
                strict=False,
                group_index=None,
            )
        )

    markers.sort(key=lambda m: m.start)
    return ExtractionResult(markers=tuple(markers), groups=tuple(groups))
