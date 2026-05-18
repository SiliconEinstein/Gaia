"""Tests for the multi-level equivalence-tolerance helper.

The helper module ``tests/cli/_equivalence_levels.py`` underwrites the
galileo + mendel strict-reproducibility demos. These tests cover each
tolerance level + per-axis dispatch + the report-format path.
"""

from __future__ import annotations

import pytest

from tests.cli._equivalence_levels import (
    AxisResult,
    EquivalenceReport,
    ToleranceLevel,
    compare_authored,
    compare_axis,
)

pytestmark = pytest.mark.pr_gate


# --------------------------------------------------------------------------- #
# BYTE_TEXT — exact multiset                                                  #
# --------------------------------------------------------------------------- #


def test_byte_text_passes_on_identical_multiset() -> None:
    """Two sequences with identical multisets pass byte-text equality."""
    result = compare_axis(
        axis="user-content",
        level=ToleranceLevel.BYTE_TEXT,
        hand_values=["a", "b", "c"],
        cli_values=["c", "a", "b"],  # order irrelevant for multiset
    )
    assert result.passed is True
    assert result.diff == ""
    assert result.hand_count == 3
    assert result.cli_count == 3


def test_byte_text_fails_when_one_side_missing_value() -> None:
    """A value present on only one side fails byte-text comparison."""
    result = compare_axis(
        axis="user-content",
        level=ToleranceLevel.BYTE_TEXT,
        hand_values=["a", "b", "c"],
        cli_values=["a", "b"],
    )
    assert result.passed is False
    assert "Only in hand" in result.diff
    assert "'c'" in result.diff


def test_byte_text_fails_on_multiplicity_mismatch() -> None:
    """A multiset entry's count must match on both sides."""
    result = compare_axis(
        axis="duplicates",
        level=ToleranceLevel.BYTE_TEXT,
        hand_values=["a", "a", "b"],
        cli_values=["a", "b", "b"],
    )
    assert result.passed is False
    assert "Multiplicity" in result.diff
    assert "hand×2" in result.diff or "hand×1" in result.diff


# --------------------------------------------------------------------------- #
# CONTENT_SET — sorted unique                                                 #
# --------------------------------------------------------------------------- #


def test_content_set_ignores_multiplicity() -> None:
    """Multiplicity differences don't break content-set equality."""
    result = compare_axis(
        axis="label-bag",
        level=ToleranceLevel.CONTENT_SET,
        hand_values=["a", "a", "b"],
        cli_values=["a", "b", "b"],
    )
    assert result.passed is True
    assert result.diff == ""


def test_content_set_fails_on_missing_unique_value() -> None:
    """A unique value missing from one side still fails content-set."""
    result = compare_axis(
        axis="label-bag",
        level=ToleranceLevel.CONTENT_SET,
        hand_values=["a", "b", "c"],
        cli_values=["a", "b"],
    )
    assert result.passed is False
    assert "'c'" in result.diff


# --------------------------------------------------------------------------- #
# AST_EQUIVALENT — reserved slot                                              #
# --------------------------------------------------------------------------- #


def test_ast_equivalent_raises_not_implemented() -> None:
    """The reserved level errors loudly until a real impl lands."""
    with pytest.raises(NotImplementedError, match="reserved"):
        compare_axis(
            axis="x",
            level=ToleranceLevel.AST_EQUIVALENT,
            hand_values=["a"],
            cli_values=["a"],
        )


# --------------------------------------------------------------------------- #
# compare_authored — per-axis dispatch                                        #
# --------------------------------------------------------------------------- #


def test_compare_authored_dispatches_per_axis_tolerance() -> None:
    """A mixed byte-text / content-set map produces axis-specific results."""
    report = compare_authored(
        axis_tolerance_map={
            "strict": ToleranceLevel.BYTE_TEXT,
            "loose": ToleranceLevel.CONTENT_SET,
        },
        axis_projection={
            "strict": (["a", "b"], ["a", "b"]),
            "loose": (["x", "x", "y"], ["x", "y", "y"]),
        },
    )
    assert report.passed is True
    assert tuple(axis.axis for axis in report.per_axis) == ("strict", "loose")
    assert report.per_axis[0].level is ToleranceLevel.BYTE_TEXT
    assert report.per_axis[1].level is ToleranceLevel.CONTENT_SET


def test_compare_authored_collects_failures() -> None:
    """A failure on one axis is surfaced through ``failures``."""
    report = compare_authored(
        axis_tolerance_map={
            "strict": ToleranceLevel.BYTE_TEXT,
            "loose": ToleranceLevel.CONTENT_SET,
        },
        axis_projection={
            "strict": (["a", "b"], ["a", "c"]),
            "loose": (["x"], ["x"]),
        },
    )
    assert report.passed is False
    assert len(report.failures) == 1
    assert report.failures[0].axis == "strict"


def test_compare_authored_format_includes_failed_axes() -> None:
    """The textual report carries axis name + diff text for failures."""
    report = compare_authored(
        axis_tolerance_map={"strict": ToleranceLevel.BYTE_TEXT},
        axis_projection={"strict": (["a"], ["b"])},
    )
    text = report.format()
    assert "Equivalence failures" in text
    assert "strict" in text
    assert "level=byte_text" in text


def test_compare_authored_format_on_pass() -> None:
    """The summary on full pass is short + positive."""
    report = compare_authored(
        axis_tolerance_map={"x": ToleranceLevel.BYTE_TEXT},
        axis_projection={"x": (["a"], ["a"])},
    )
    assert report.format() == "All axes passed."


def test_compare_authored_raises_on_missing_projection() -> None:
    """A tolerance map entry without a matching projection trips KeyError."""
    with pytest.raises(KeyError, match="axis 'x'"):
        compare_authored(
            axis_tolerance_map={"x": ToleranceLevel.BYTE_TEXT},
            axis_projection={"y": (["a"], ["a"])},
        )


def test_equivalence_report_is_hashable_dataclass() -> None:
    """The report and per-axis results are frozen dataclasses (immutable)."""
    result = AxisResult(
        axis="x",
        level=ToleranceLevel.BYTE_TEXT,
        passed=True,
        diff="",
        hand_count=1,
        cli_count=1,
    )
    report = EquivalenceReport(per_axis=(result,))
    assert report.passed is True
    # Frozen dataclasses raise FrozenInstanceError on attribute assignment.
    with pytest.raises(Exception, match="cannot assign"):
        result.passed = False  # type: ignore[misc]
