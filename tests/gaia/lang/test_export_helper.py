"""Tests for Gaia Lang package export helper."""

from __future__ import annotations

import pytest

from gaia.engine.lang import claim, export


def test_export_accepts_literal_names() -> None:
    assert export("main", "secondary") == ["main", "secondary"]


def test_export_resolves_knowledge_object_to_caller_name() -> None:
    main = claim("Main result.")

    assert export(main) == ["main"]


def test_export_rejects_ambiguous_object_names() -> None:
    main = claim("Main result.")
    alias = main

    with pytest.raises(ValueError, match="multiple names"):
        export(main)

    assert alias is main


def test_export_mixes_strings_and_knowledge_objects() -> None:
    secondary = claim("Secondary result.")

    assert export("main", secondary) == ["main", "secondary"]


def test_export_rejects_non_knowledge_value() -> None:
    with pytest.raises(TypeError, match="strings or Gaia Knowledge objects"):
        export(123)  # type: ignore[arg-type]


def test_export_requires_a_public_caller_name() -> None:
    # An inline object is bound to no caller-scope name, so it cannot be
    # resolved to an __all__ entry; the helper asks for an explicit string.
    with pytest.raises(ValueError, match="could not find a public caller-scope name"):
        export(claim("Unbound result."))


def test_export_ignores_private_caller_names() -> None:
    _hidden = claim("Private result.")

    with pytest.raises(ValueError, match="could not find a public caller-scope name"):
        export(_hidden)


def test_export_rejects_duplicate_names() -> None:
    with pytest.raises(ValueError, match="duplicate export name"):
        export("main", "main")
