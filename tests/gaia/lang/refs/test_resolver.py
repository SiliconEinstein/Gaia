"""Tests for gaia.lang.refs.resolver."""

from __future__ import annotations

import pytest

from gaia.lang.refs import (
    ReferenceError,
    check_collisions,
    extract,
    resolve,
    validate_groups,
)


def test_resolve_knowledge() -> None:
    label_table = {"lemma_a": "github:pkg::lemma_a"}
    references: dict[str, dict] = {}
    assert resolve("lemma_a", label_table, references) == "knowledge"


def test_resolve_citation() -> None:
    label_table: dict[str, str] = {}
    references = {"Bell1964": {"type": "article-journal", "title": "On EPR"}}
    assert resolve("Bell1964", label_table, references) == "citation"


def test_resolve_unknown() -> None:
    label_table: dict[str, str] = {}
    references: dict[str, dict] = {}
    assert resolve("nothing_here", label_table, references) == "unknown"


def test_resolve_citation_precedence_not_applicable_after_collision_check() -> None:
    """Verify resolve citation precedence not applicable after collision check.

    If check_collisions passed, resolver must not see both. This test documents that resolver
    assumes disjoint inputs.
    """
    label_table = {"only_local": "qid"}
    references = {"only_remote": {"type": "book", "title": "X"}}
    assert resolve("only_local", label_table, references) == "knowledge"
    assert resolve("only_remote", label_table, references) == "citation"


def test_check_collisions_no_collision() -> None:
    label_table = {"lemma_a": "q1", "lemma_b": "q2"}
    references = {"Bell1964": {"type": "book", "title": "X"}}
    check_collisions(label_table, references)  # should not raise


def test_check_collisions_single_collision_raises() -> None:
    label_table = {"bell_lemma": "q1"}
    references = {"bell_lemma": {"type": "article-journal", "title": "X"}}
    with pytest.raises(ReferenceError) as exc:
        check_collisions(label_table, references)
    assert "bell_lemma" in str(exc.value)
    assert "ambiguous" in str(exc.value).lower()


def test_check_collisions_multiple_collisions_all_listed() -> None:
    label_table = {"a": "q1", "b": "q2", "c": "q3"}
    references = {
        "a": {"type": "book", "title": "A"},
        "c": {"type": "book", "title": "C"},
        "d": {"type": "book", "title": "D"},
    }
    with pytest.raises(ReferenceError) as exc:
        check_collisions(label_table, references)
    msg = str(exc.value)
    assert "'a'" in msg
    assert "'c'" in msg
    assert "'b'" not in msg
    assert "'d'" not in msg


def test_validate_groups_pure_citation_group_ok() -> None:
    text = "[@Bell1964; @CHSH1969]"
    result = extract(text)
    label_table: dict[str, str] = {}
    references = {
        "Bell1964": {"type": "article-journal", "title": "On EPR"},
        "CHSH1969": {"type": "article-journal", "title": "Proposed experiment"},
    }
    validate_groups(result.groups, result.markers, label_table, references)


def test_validate_groups_pure_knowledge_group_ok() -> None:
    text = "[@lemma_a; @lemma_b]"
    result = extract(text)
    label_table = {"lemma_a": "q1", "lemma_b": "q2"}
    references: dict[str, dict] = {}
    validate_groups(result.groups, result.markers, label_table, references)


def test_validate_groups_mixed_group_raises() -> None:
    text = "[see @lemma_a; @Bell1964, p. 5]"
    result = extract(text)
    label_table = {"lemma_a": "q1"}
    references = {"Bell1964": {"type": "article-journal", "title": "X"}}
    with pytest.raises(ReferenceError) as exc:
        validate_groups(result.groups, result.markers, label_table, references)
    msg = str(exc.value)
    assert "mixed" in msg.lower()
    assert "lemma_a" in msg
    assert "Bell1964" in msg


def test_validate_groups_unknown_in_group_not_flagged_as_mixed() -> None:
    """A group with one knowledge ref + one unknown key is NOT mixed."""
    text = "[@lemma_a; @nothing]"
    result = extract(text)
    label_table = {"lemma_a": "q1"}
    references: dict[str, dict] = {}
    validate_groups(result.groups, result.markers, label_table, references)


# ---------------------------------------------------------------------------
# Codex adversarial review: bracket-group member indexing must survive the
# post-extract marker sort. Prior to the fix, extract() recorded group member
# indices in Pass 1 (bracket scan), then appended bare markers in Pass 2, then
# sorted `markers` by source position — which invalidated every group index
# whenever a bare marker appeared before or between bracket groups.
# ---------------------------------------------------------------------------


def test_validate_groups_bare_before_pure_citation_group_ok() -> None:
    """Verify validate groups bare before pure citation group ok.

    A bare knowledge ref appearing BEFORE a pure-citation bracket group must not corrupt the
    group's member indices. Before the fix, this raised a false-positive mixed-group error.
    """
    text = "First @lemma_a then see [@Bell1964; @CHSH1969]"
    result = extract(text)
    label_table = {"lemma_a": "q1"}
    references = {
        "Bell1964": {"type": "article-journal", "title": "X"},
        "CHSH1969": {"type": "article-journal", "title": "Y"},
    }
    # Should not raise — the group is pure citation.
    validate_groups(result.groups, result.markers, label_table, references)


def test_validate_groups_bare_before_pure_knowledge_group_ok() -> None:
    """Symmetric case: bare citation ref before a pure-knowledge group."""
    text = "First @Bell1964 then see [@lemma_a; @lemma_b]"
    result = extract(text)
    label_table = {"lemma_a": "q1", "lemma_b": "q2"}
    references = {"Bell1964": {"type": "article-journal", "title": "X"}}
    validate_groups(result.groups, result.markers, label_table, references)


def test_validate_groups_bare_before_mixed_group_still_detected() -> None:
    """Verify validate groups bare before mixed group still detected.

    False-negative guard: a bare marker must NOT mask a genuine mixed group. Before the fix, the
    index shift could point group indices at two like-typed markers and let a real mixed group
    through.
    """
    text = "As @helper shows, see [@lemma_a; @Bell1964] for details"
    result = extract(text)
    label_table = {"helper": "q1", "lemma_a": "q2"}
    references = {"Bell1964": {"type": "article-journal", "title": "X"}}
    with pytest.raises(ReferenceError) as exc:
        validate_groups(result.groups, result.markers, label_table, references)
    assert "mixed" in str(exc.value).lower()
    assert "lemma_a" in str(exc.value)
    assert "Bell1964" in str(exc.value)


def test_validate_groups_multiple_bare_and_groups_interleaved() -> None:
    """Stress test: interleaved bare markers and multiple groups."""
    text = "@lemma_a then [@Bell1964] and @lemma_b then [@CHSH1969] and @lemma_c"
    result = extract(text)
    label_table = {"lemma_a": "q1", "lemma_b": "q2", "lemma_c": "q3"}
    references = {
        "Bell1964": {"type": "article-journal", "title": "X"},
        "CHSH1969": {"type": "article-journal", "title": "Y"},
    }
    # Both groups are pure citation — neither should raise.
    validate_groups(result.groups, result.markers, label_table, references)

    # Additionally verify each group's marker_indices actually point to the
    # right keys after sorting.
    assert len(result.groups) == 2
    for group in result.groups:
        group_keys = {result.markers[i].key for i in group.marker_indices}
        assert group_keys in ({"Bell1964"}, {"CHSH1969"}), (
            f"Group {group.raw!r} has corrupt marker_indices — resolves to {group_keys}"
        )
