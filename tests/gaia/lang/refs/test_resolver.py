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
    """If check_collisions passed, resolver must not see both. This test
    documents that resolver assumes disjoint inputs."""
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
