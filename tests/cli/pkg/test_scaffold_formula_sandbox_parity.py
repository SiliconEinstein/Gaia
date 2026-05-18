"""Regression guard: scaffold ships the minimal canonical import surface.

Why this test exists — earlier scaffold revisions hardcoded a *full*
import preamble covering every formula primitive + atom constructor +
typed term + bayes alias. That choice polluted every authored package
with unused imports the moment the file was created.

Wave 1 of the agent-fluency cleanup removes that wide preamble: a fresh
scaffold imports only ``claim`` from ``gaia.engine.lang`` and ships an
empty ``__all__``. Wave 2 makes the import block dynamic — added imports
follow added author verbs. This test guards the Wave-1 invariant so a
future revert doesn't silently bring the wide preamble back.
"""

from __future__ import annotations

import pytest

from gaia.cli.commands.pkg.scaffold import (
    _INIT_BODY_NO_DOCSTRING,
    _INIT_BODY_WITH_DOCSTRING,
)

pytestmark = pytest.mark.pr_gate


def test_default_template_imports_only_claim() -> None:
    """Default __init__.py imports `claim` and nothing else from gaia.engine.lang."""
    assert "from gaia.engine.lang import claim\n" in _INIT_BODY_NO_DOCSTRING
    # No broader formula primitives / atom constructors / typed terms / bayes alias.
    for forbidden in (
        "ClaimAtom",
        "Variable",
        "Constant",
        "land",
        "lor",
        "forall",
        "exists",
        "from gaia.engine import bayes",
    ):
        assert forbidden not in _INIT_BODY_NO_DOCSTRING, (
            f"scaffold default template unexpectedly imports {forbidden!r}; "
            "Wave 1 invariant says the default is narrow."
        )


def test_default_template_has_empty_all() -> None:
    """Default __init__.py ships an empty `__all__`, ready for author commands to populate."""
    assert "__all__: list[str] = []\n" in _INIT_BODY_NO_DOCSTRING


def test_default_template_omits_placeholder_hypothesis() -> None:
    """The legacy `hypothesis = claim(...)` placeholder is gone."""
    assert "hypothesis = claim(" not in _INIT_BODY_NO_DOCSTRING


def test_docstring_template_starts_with_triple_quote() -> None:
    """`--docstring` template's first character is the opening triple quote."""
    rendered = _INIT_BODY_WITH_DOCSTRING.format(docstring="example")
    assert rendered.startswith('"""example"""\n')
    assert "from gaia.engine.lang import claim\n" in rendered
    assert "__all__: list[str] = []\n" in rendered
