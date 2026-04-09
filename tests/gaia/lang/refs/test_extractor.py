"""Tests for gaia.lang.refs.extractor."""

from __future__ import annotations

from gaia.lang.refs import extract


def test_extract_empty_string() -> None:
    result = extract("")
    assert result.markers == ()
    assert result.groups == ()


def test_extract_plain_text_no_markers() -> None:
    result = extract("This is plain text with no references.")
    assert result.markers == ()
    assert result.groups == ()


def test_extract_single_bare_marker() -> None:
    result = extract("As @lemma_a shows, the claim holds.")
    assert len(result.markers) == 1
    marker = result.markers[0]
    assert marker.key == "lemma_a"
    assert marker.strict is False
    assert marker.group_index is None
    assert marker.start == 3
    assert marker.end == 11


def test_extract_bare_marker_with_citation_key() -> None:
    result = extract("See @Bell1964 for details.")
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"
    assert result.markers[0].strict is False


def test_extract_bare_marker_with_punctuation_in_key() -> None:
    result = extract("Reference @arxiv:2401.12345 here.")
    assert len(result.markers) == 1
    assert result.markers[0].key == "arxiv:2401.12345"


def test_extract_bare_marker_followed_by_punctuation() -> None:
    """Key cannot end with punctuation — trailing `.` is not part of key."""
    result = extract("See @Bell1964.")
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"


def test_extract_email_not_matched() -> None:
    """`@bar` inside `foo@bar.com` must NOT match (email safety)."""
    result = extract("Email me at foo@bar.com for questions.")
    assert result.markers == ()


def test_extract_escaped_at_not_matched() -> None:
    """`\\@foo` is literal — extractor skips it."""
    result = extract("Use the \\@dataclass decorator.")
    assert result.markers == ()


def test_extract_multiple_bare_markers() -> None:
    result = extract("Combine @lemma_a with @Bell1964 for the proof.")
    assert len(result.markers) == 2
    assert [m.key for m in result.markers] == ["lemma_a", "Bell1964"]


def test_extract_single_bracket_group_one_key() -> None:
    result = extract("The result [@Bell1964] is foundational.")
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.raw == "[@Bell1964]"
    assert len(group.marker_indices) == 1

    assert len(result.markers) == 1
    marker = result.markers[0]
    assert marker.key == "Bell1964"
    assert marker.strict is True
    assert marker.group_index == 0


def test_extract_bracket_group_multiple_keys() -> None:
    result = extract("[@Bell1964; @CHSH1969; @EPR1935]")
    assert len(result.groups) == 1
    group = result.groups[0]
    assert len(group.marker_indices) == 3

    assert len(result.markers) == 3
    assert [m.key for m in result.markers] == ["Bell1964", "CHSH1969", "EPR1935"]
    assert all(m.strict for m in result.markers)
    assert all(m.group_index == 0 for m in result.markers)


def test_extract_bracket_group_with_prefix_locator() -> None:
    """Pandoc prefix + locator + suffix — extractor only finds the @keys."""
    result = extract("[see @Bell1964, pp. 33-35 and passim]")
    assert len(result.groups) == 1
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"
    assert result.markers[0].strict is True


def test_extract_suppress_author_form() -> None:
    result = extract("Bell [-@Bell1964] showed this.")
    assert len(result.groups) == 1
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"


def test_extract_mixed_bare_and_bracket() -> None:
    text = "First @lemma_a shows this, then [@Bell1964] confirms it."
    result = extract(text)
    assert len(result.groups) == 1
    assert len(result.markers) == 2
    bare = [m for m in result.markers if not m.strict]
    bracketed = [m for m in result.markers if m.strict]
    assert len(bare) == 1 and bare[0].key == "lemma_a"
    assert len(bracketed) == 1 and bracketed[0].key == "Bell1964"


def test_extract_empty_brackets_not_group() -> None:
    """`[foo]` without any @ is not a reference group."""
    result = extract("This is [regular] bracketed text.")
    assert result.groups == ()
    assert result.markers == ()


def test_extract_bracket_no_at_not_group() -> None:
    result = extract("The range is [1, 10] here.")
    assert result.groups == ()
    assert result.markers == ()


def test_extract_escaped_at_inside_brackets() -> None:
    """Regression for Codex review P2: `\\@` escape must work inside
    bracketed groups too, not just bare form. This lets authors write
    literal `[@key]` examples in documentation without triggering the
    strict-form error."""
    result = extract("Literal example: [\\@Bell1964] is a strict ref.")
    assert result.groups == ()
    assert result.markers == ()


def test_extract_mixed_escaped_and_real_inside_brackets() -> None:
    """Only unescaped keys are extracted from a group."""
    result = extract("[see @Bell1964 and \\@footnote for details]")
    assert len(result.groups) == 1
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"
    assert result.markers[0].strict is True


def test_extract_escaped_bracket_opens_not_group() -> None:
    """An escaped opening bracket prevents group matching."""
    result = extract("Literal \\[@Bell1964] here.")
    assert result.groups == ()
