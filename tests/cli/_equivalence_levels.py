"""Multi-level equivalence-tolerance helper for cli-as-client demos.

R8·❓C — a single tolerance level (content-set) collapsed the post-R7
equivalence frontier into the lowest common denominator: with three of
the four original galileo divergences now byte-text-closed (R7 G6 / G8
/ G1), strict-reproducibility tests should be able to assert byte-text
on the closed axes while still tolerating intrinsic-by-design axes
(such as the cli's single-``--label`` rule, R7·❓A=A) at content-set
level.

This module provides:

* :class:`ToleranceLevel` — three tolerance levels per axis:

  * ``BYTE_TEXT`` — exact string equality (no ordering forgiveness; the
    multiset of strings on each side must match byte-for-byte).
  * ``AST_EQUIVALENT`` — for source-text axes: parse both sides as
    Python and compare the resulting AST modulo whitespace + label-
    kwarg rendering choice. Reserved for future use (R8 ships byte-text
    + content-set only; the third level documents the design space).
  * ``CONTENT_SET`` — compare the sorted set of values (de-dup + ignore
    multiset multiplicity, e.g. for label-bag axes where two source-
    text spellings collapse to the same IR slot).

* :class:`AxisResult` and :class:`EquivalenceReport` — per-axis
  pass/fail with a textual diff for failed axes.

* :func:`compare_axis` — single-axis comparison given a tolerance level
  and a pair of value sequences.

* :func:`compare_authored` — convenience: take a per-axis tolerance map
  and a per-axis ``(hand_values, cli_values)`` projection, return a
  full report.

Per-axis tolerance maps are chosen by the demo author. The R8 galileo
mapping pins all R7-closed axes to ``BYTE_TEXT`` and the intrinsic
``label-kwarg`` axis to ``CONTENT_SET``. Mendel inherits the same
backbone plus mendel-specific axes (bayes statement shape, variable
declarations, formula-claim emission).
"""

from __future__ import annotations

import difflib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ToleranceLevel(Enum):
    """Per-axis equivalence-tolerance level.

    Three levels (R8 ships two; AST_EQUIVALENT reserved as the
    intermediate slot so axis maps can be tightened in-place when a
    future closure surfaces a third byte-text vs content-set frontier).

    Attributes:
        BYTE_TEXT: Multiset of strings must match byte-for-byte. Use
            when the cli renders source-text identical to the hand-
            authored source (e.g. R7-closed divergences).
        AST_EQUIVALENT: Python-AST equivalence modulo whitespace +
            redundant kwarg rendering. Reserved for future use; not
            consumed by R8 demos.
        CONTENT_SET: Sorted set of unique values must match. Use when
            two source-text spellings legitimately compile to the same
            IR slot (e.g. multiple cli statements binding to identical
            labels collapse to a single content-set entry).
    """

    BYTE_TEXT = "byte_text"
    AST_EQUIVALENT = "ast_equivalent"
    CONTENT_SET = "content_set"


@dataclass(frozen=True)
class AxisResult:
    """Single-axis comparison outcome.

    Attributes:
        axis: Human-readable axis name (e.g. ``"user-authored-content"``).
        level: Tolerance level the axis was evaluated at.
        passed: Whether the two sides matched under that level.
        diff: Unified-diff-style text describing the mismatch (empty
            string on pass).
        hand_count: Number of values on the hand-authored side.
        cli_count: Number of values on the cli-authored side.
    """

    axis: str
    level: ToleranceLevel
    passed: bool
    diff: str
    hand_count: int
    cli_count: int


@dataclass(frozen=True)
class EquivalenceReport:
    """Aggregate report across all configured axes.

    Attributes:
        per_axis: Ordered list of per-axis results.
    """

    per_axis: tuple[AxisResult, ...] = field(default_factory=tuple)

    @property
    def passed(self) -> bool:
        """``True`` if every configured axis passed."""
        return all(axis.passed for axis in self.per_axis)

    @property
    def failures(self) -> tuple[AxisResult, ...]:
        """The subset of axes that failed (empty on full pass)."""
        return tuple(axis for axis in self.per_axis if not axis.passed)

    def format(self) -> str:
        """Render a human-readable summary suitable for assertion messages."""
        if self.passed:
            return "All axes passed."
        lines = ["Equivalence failures:"]
        for axis in self.failures:
            lines.append(
                f"\n  axis={axis.axis!r} level={axis.level.value} "
                f"hand_count={axis.hand_count} cli_count={axis.cli_count}"
            )
            lines.append(_indent(axis.diff, "    "))
        return "\n".join(lines)


def _indent(text: str, prefix: str) -> str:
    """Indent every non-empty line of ``text`` with ``prefix``."""
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def _format_unified_diff(
    *,
    hand: Sequence[str],
    cli: Sequence[str],
    hand_label: str = "hand",
    cli_label: str = "cli",
) -> str:
    """Render a sorted unified-diff snippet for two string sequences."""
    hand_sorted = sorted(hand)
    cli_sorted = sorted(cli)
    diff_lines = list(
        difflib.unified_diff(
            hand_sorted,
            cli_sorted,
            fromfile=hand_label,
            tofile=cli_label,
            lineterm="",
        )
    )
    return "\n".join(diff_lines) if diff_lines else ""


def _multiset(values: Iterable[Any]) -> dict[Any, int]:
    """Build a hashable multiset (dict count) over the values."""
    counts: dict[Any, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return counts


def _format_multiset_diff(
    *,
    hand: Sequence[Any],
    cli: Sequence[Any],
) -> str:
    """Render a diff snippet for a multiset (byte-text) mismatch."""
    hand_counts = _multiset(hand)
    cli_counts = _multiset(cli)
    only_hand: list[str] = []
    only_cli: list[str] = []
    diff_count: list[str] = []
    all_keys = set(hand_counts) | set(cli_counts)
    for key in sorted(all_keys, key=lambda x: repr(x)):
        h = hand_counts.get(key, 0)
        c = cli_counts.get(key, 0)
        if h == c:
            continue
        if h == 0:
            only_cli.append(f"  + {key!r} (×{c})")
        elif c == 0:
            only_hand.append(f"  - {key!r} (×{h})")
        else:
            diff_count.append(f"  ≠ {key!r}: hand×{h} vs cli×{c}")
    lines: list[str] = []
    if only_hand:
        lines.append("Only in hand:")
        lines.extend(only_hand)
    if only_cli:
        lines.append("Only in cli:")
        lines.extend(only_cli)
    if diff_count:
        lines.append("Multiplicity mismatches:")
        lines.extend(diff_count)
    return "\n".join(lines) if lines else ""


def compare_axis(
    *,
    axis: str,
    level: ToleranceLevel,
    hand_values: Sequence[Any],
    cli_values: Sequence[Any],
) -> AxisResult:
    """Compare a single axis under one tolerance level.

    Args:
        axis: Human-readable axis name (e.g. ``"strategy-count"``).
        level: One of :class:`ToleranceLevel`.
        hand_values: Values projected from the hand-authored IR.
        cli_values: Values projected from the cli-authored IR.

    Returns:
        An :class:`AxisResult` describing pass/fail + a diff text on
        failure.
    """
    hand_list = list(hand_values)
    cli_list = list(cli_values)
    hand_count = len(hand_list)
    cli_count = len(cli_list)

    if level is ToleranceLevel.BYTE_TEXT:
        passed = _multiset(hand_list) == _multiset(cli_list)
        diff = _format_multiset_diff(hand=hand_list, cli=cli_list) if not passed else ""
    elif level is ToleranceLevel.CONTENT_SET:
        hand_set = set(hand_list)
        cli_set = set(cli_list)
        passed = hand_set == cli_set
        diff = (
            _format_unified_diff(hand=[repr(x) for x in hand_set], cli=[repr(x) for x in cli_set])
            if not passed
            else ""
        )
    elif level is ToleranceLevel.AST_EQUIVALENT:
        # Reserved slot. R8 demos don't consume AST_EQUIVALENT; if a
        # future axis needs it, hook a per-axis parser+comparator here.
        # Until then, treat it as a strict-fail with an informative
        # message so the level isn't silently degraded.
        raise NotImplementedError(
            "ToleranceLevel.AST_EQUIVALENT is reserved (not implemented in R8). "
            "Pick BYTE_TEXT or CONTENT_SET, or extend compare_axis to dispatch."
        )
    else:  # pragma: no cover — Enum exhaustion
        raise ValueError(f"Unknown tolerance level: {level!r}")

    return AxisResult(
        axis=axis,
        level=level,
        passed=passed,
        diff=diff,
        hand_count=hand_count,
        cli_count=cli_count,
    )


def compare_authored(
    *,
    axis_tolerance_map: Mapping[str, ToleranceLevel],
    axis_projection: Mapping[str, tuple[Sequence[Any], Sequence[Any]]],
) -> EquivalenceReport:
    """Compare hand-authored vs cli-authored values across a set of axes.

    Args:
        axis_tolerance_map: Maps axis name → :class:`ToleranceLevel`.
            Every key in this map must also be in ``axis_projection``.
        axis_projection: Maps axis name → ``(hand_values, cli_values)``
            sequence pair. Both sequences are projected from the
            already-loaded IRs (the helper is IR-agnostic — caller owns
            the projection).

    Returns:
        An :class:`EquivalenceReport` with one :class:`AxisResult` per
        configured axis, in the iteration order of ``axis_tolerance_map``.

    Raises:
        KeyError: If ``axis_tolerance_map`` references an axis missing
            from ``axis_projection``.
    """
    results: list[AxisResult] = []
    for axis, level in axis_tolerance_map.items():
        if axis not in axis_projection:
            raise KeyError(f"axis {axis!r} listed in tolerance map but no projection supplied")
        hand_values, cli_values = axis_projection[axis]
        results.append(
            compare_axis(
                axis=axis,
                level=level,
                hand_values=hand_values,
                cli_values=cli_values,
            )
        )
    return EquivalenceReport(per_axis=tuple(results))


__all__ = [
    "AxisResult",
    "EquivalenceReport",
    "ToleranceLevel",
    "compare_authored",
    "compare_axis",
]
