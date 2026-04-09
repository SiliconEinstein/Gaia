"""Tests for gaia.lang.refs.loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.lang.refs import ReferenceError, load_references


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    """references.json is optional; missing file → empty dict."""
    assert load_references(tmp_path / "references.json") == {}


def test_load_valid_minimal_entry(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(
        json.dumps(
            {
                "Bell1964": {
                    "type": "article-journal",
                    "title": "On the Einstein Podolsky Rosen Paradox",
                }
            }
        )
    )
    refs = load_references(path)
    assert "Bell1964" in refs
    assert refs["Bell1964"]["title"].startswith("On the Einstein")


def test_load_valid_full_entry(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(
        json.dumps(
            {
                "EPR1935": {
                    "type": "article-journal",
                    "title": "Can Quantum-Mechanical Description of Physical Reality Be Considered Complete?",
                    "author": [
                        {"family": "Einstein", "given": "A."},
                        {"family": "Podolsky", "given": "B."},
                        {"family": "Rosen", "given": "N."},
                    ],
                    "container-title": "Physical Review",
                    "volume": "47",
                    "page": "777-780",
                    "issued": {"date-parts": [[1935, 5, 15]]},
                    "DOI": "10.1103/PhysRev.47.777",
                }
            }
        )
    )
    refs = load_references(path)
    assert len(refs) == 1
    assert refs["EPR1935"]["DOI"] == "10.1103/PhysRev.47.777"


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text("{not valid json")
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "invalid json" in str(exc.value).lower()


def test_load_top_level_not_dict_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps(["not", "a", "dict"]))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "must be a json object" in str(exc.value).lower()


def test_load_entry_missing_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"Bad": {"title": "No type field"}}))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "type" in str(exc.value)
    assert "Bad" in str(exc.value)


def test_load_entry_invalid_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"Bad": {"type": "not-a-real-csl-type", "title": "X"}}))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "not-a-real-csl-type" in str(exc.value)


def test_load_entry_missing_title_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"Bad": {"type": "book"}}))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "title" in str(exc.value)


def test_load_webpage_type(tmp_path: Path) -> None:
    """Webpages are first-class citizens (spec §4.4)."""
    path = tmp_path / "references.json"
    path.write_text(
        json.dumps(
            {
                "SomeBlog": {
                    "type": "post-weblog",
                    "title": "An explanation",
                    "URL": "https://example.com/post",
                }
            }
        )
    )
    refs = load_references(path)
    assert refs["SomeBlog"]["type"] == "post-weblog"


def test_load_software_type(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(
        json.dumps(
            {
                "NumPy": {
                    "type": "software",
                    "title": "NumPy",
                    "version": "1.26.0",
                }
            }
        )
    )
    refs = load_references(path)
    assert refs["NumPy"]["type"] == "software"


# ---------------------------------------------------------------------------
# Codex review P3: citation keys must match the Pandoc @-syntax grammar so
# that they are actually reachable by the extractor. Keys with spaces or
# trailing punctuation load silently today but can never be cited.
# ---------------------------------------------------------------------------


def test_load_rejects_key_with_whitespace(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"Bell 1964": {"type": "article-journal", "title": "On EPR"}}))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "Bell 1964" in str(exc.value)


def test_load_rejects_key_ending_with_period(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"Bell1964.": {"type": "article-journal", "title": "On EPR"}}))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "Bell1964." in str(exc.value)


def test_load_rejects_key_ending_with_exclamation(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"Bell1964!": {"type": "article-journal", "title": "On EPR"}}))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "Bell1964!" in str(exc.value)


def test_load_rejects_empty_key(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({"": {"type": "article-journal", "title": "X"}}))
    with pytest.raises(ReferenceError):
        load_references(path)


def test_load_accepts_valid_pandoc_keys(tmp_path: Path) -> None:
    """Keys that fully match the Pandoc @-syntax grammar should all load."""
    path = tmp_path / "references.json"
    path.write_text(
        json.dumps(
            {
                "Bell1964": {"type": "article-journal", "title": "A"},
                "smith_2004": {"type": "article-journal", "title": "B"},
                "arxiv:2401.12345": {"type": "article", "title": "C"},
                "doi:10.1103/PhysRev.47.777": {
                    "type": "article-journal",
                    "title": "D",
                },
                "X": {"type": "book", "title": "E"},  # single char
                "EPR1935": {"type": "article-journal", "title": "F"},
            }
        )
    )
    refs = load_references(path)
    assert len(refs) == 6
