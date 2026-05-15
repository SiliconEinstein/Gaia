"""Extract Pandoc-style reference markers from text.

Supports two forms:
  - Bare:      @key                   (opportunistic)
  - Bracketed: [prefix @key suffix]   (strict, Pandoc subset)

The extractor is pure — it only parses text and has no knowledge of label
tables or references.json. Resolution is done by the resolver module.
"""

from __future__ import annotations

import re

from gaia.engine.lang.refs.types import BracketGroup, ExtractionResult, RefMarker

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

# Anchored form of _KEY, for validating standalone identifiers
# (e.g. top-level citation keys in references.json). The loader imports this
# to ensure every declared key is actually reachable via the @-syntax.
CITATION_KEY_RE = re.compile(rf"^{_KEY}$")

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

    Group membership is tracked by marker identity during Pass 1, then
    converted to final list indices AFTER the markers list is sorted. This
    makes the group indices robust to the sort step even when bare markers
    appear before or between bracket groups.
    """
    if not text:
        return ExtractionResult(markers=(), groups=())

    markers: list[RefMarker] = []
    # During Pass 1, groups are recorded with the actual RefMarker objects
    # that belong to them (not list indices), so we can rebuild indices
    # after sort. Each tuple: (raw_text, start, end, group_markers).
    group_records: list[tuple[str, int, int, list[RefMarker]]] = []
    # Character positions covered by bracket groups, so the bare scanner can
    # skip them.
    bracket_spans: list[tuple[int, int]] = []

    # Pass 1: bracket groups
    for group_match in _BRACKET_GROUP_RE.finditer(text):
        group_start = group_match.start()
        group_end = group_match.end()
        body = group_match.group(1)
        body_offset = group_match.start(1)

        group_markers: list[RefMarker] = []
        group_index = len(group_records)
        for key_match in _INNER_KEY_RE.finditer(body):
            marker = RefMarker(
                key=key_match.group(1),
                start=body_offset + key_match.start(1) - 1,  # include `@`
                end=body_offset + key_match.end(1),
                strict=True,
                group_index=group_index,
            )
            markers.append(marker)
            group_markers.append(marker)

        if not group_markers:
            continue

        group_records.append((text[group_start:group_end], group_start, group_end, group_markers))
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

    # Sort markers by source position AFTER all Pass 1 and Pass 2 markers
    # are collected. Group membership still points at the original RefMarker
    # objects, so we rebuild marker_indices by identity lookup against the
    # sorted list.
    markers.sort(key=lambda m: m.start)
    new_index_of: dict[int, int] = {id(m): i for i, m in enumerate(markers)}

    groups = tuple(
        BracketGroup(
            raw=raw,
            start=start,
            end=end,
            marker_indices=tuple(new_index_of[id(m)] for m in group_markers),
        )
        for raw, start, end, group_markers in group_records
    )

    return ExtractionResult(markers=tuple(markers), groups=groups)
