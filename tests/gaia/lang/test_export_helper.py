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
