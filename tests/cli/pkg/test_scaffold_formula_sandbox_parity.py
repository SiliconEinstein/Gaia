"""Regression guard: scaffold imports cover the formula-sandbox callable whitelist.

Why this test exists — the cli's ``decompose --formula-expr`` /
``claim --formula`` paths validate user expressions against the
``gaia.cli.commands.author._formula_sandbox`` whitelist. When a freshly
scaffolded package needs to load its hand-written formula expressions
(authored via ``gaia author claim --formula ...``), the names the
sandbox accepts must also resolve in the scaffolded ``__init__.py``
module scope — otherwise the post-write ``gaia build check`` trips a
``NameError`` even though the cli accepted the expression.

The previous drift (``forall`` / ``exists`` accepted by the sandbox but
not imported by the scaffold template) is the kind of regression this
test catches. Future drift in either direction (sandbox grows a name
without the scaffold template, or the scaffold template silently drops
a name the sandbox still accepts) fires this gate.

Scope: only the *formula-callable* names — i.e. ``_FORMULA_PRIMITIVES``
plus ``_ATOM_CONSTRUCTORS`` plus ``_TYPED_TERMS`` (the actual term
constructors authors reach for inside formula expressions). The
``bayes.<DistributionFactory>`` shape is intentionally out of scope:
those names are accessed via attribute on the imported ``bayes``
module (see scaffold template's ``from gaia.engine import bayes``),
not as bare identifiers in ``__init__.py``. Constants (``True`` /
``False`` / ``None``) are Python literals — no import needed.
"""

from __future__ import annotations

import pytest

from gaia.cli.commands.author._formula_sandbox import (
    _ATOM_CONSTRUCTORS,
    _FORMULA_PRIMITIVES,
    _TYPED_TERMS,
)
from gaia.cli.commands.pkg.scaffold import _INIT_TEMPLATE_FULL

pytestmark = pytest.mark.pr_gate


def _import_block(template: str) -> str:
    """Pluck the ``from gaia.engine.lang import (...)`` block as text.

    The substring-presence assertions below run against this block so the
    test catches the realistic drift mode (a name absent from the import
    list) and not accidental matches against unrelated template prose
    like ``__all__ = ["hypothesis"]``.
    """
    marker = "from gaia.engine.lang import ("
    start = template.find(marker)
    assert start != -1, "scaffold template missing `from gaia.engine.lang import (...)` block"
    end = template.find(")", start)
    assert end != -1, "scaffold template `from gaia.engine.lang import (` block has no closing `)`"
    return template[start : end + 1]


def test_scaffold_full_template_imports_formula_primitives() -> None:
    """Every formula-primitive in the sandbox whitelist is imported by the full template."""
    block = _import_block(_INIT_TEMPLATE_FULL)
    missing = sorted(name for name in _FORMULA_PRIMITIVES if name not in block)
    assert not missing, (
        "scaffold _INIT_TEMPLATE_FULL is missing formula-primitive imports that the cli "
        f"sandbox accepts: {missing}. Add them to the `from gaia.engine.lang import (...)` "
        "block in `gaia/cli/commands/pkg/scaffold.py`."
    )


def test_scaffold_full_template_imports_atom_constructors() -> None:
    """``ClaimAtom`` (atom constructor) is imported by the full template."""
    block = _import_block(_INIT_TEMPLATE_FULL)
    missing = sorted(name for name in _ATOM_CONSTRUCTORS if name not in block)
    assert not missing, (
        "scaffold _INIT_TEMPLATE_FULL is missing atom-constructor imports: "
        f"{missing}. Authors reach for these inside formula expressions like "
        "`land(ClaimAtom(a), ClaimAtom(b))`."
    )


def test_scaffold_full_template_imports_typed_terms() -> None:
    """``Variable`` / ``Constant`` / domain primitives are imported by the full template."""
    block = _import_block(_INIT_TEMPLATE_FULL)
    missing = sorted(name for name in _TYPED_TERMS if name not in block)
    assert not missing, (
        "scaffold _INIT_TEMPLATE_FULL is missing typed-term imports: "
        f"{missing}. These are reached via `equals(my_var, Constant(395, Nat))` etc."
    )
