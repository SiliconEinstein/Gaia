"""Unit tests for the restricted-globals formula sandbox.

The sandbox lives at :mod:`gaia.cli.commands.author._formula_sandbox` and
is invoked by ``decompose --formula-expr`` and ``claim --predicate``. The
contract: only names in the static whitelist (formula primitives +
``ClaimAtom`` + Distribution factories + constants) plus the caller-
supplied ``extra_names`` set may appear; anything else raises
:class:`FormulaSandboxError`.
"""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.commands.author._formula_sandbox import (
    WHITELIST,
    FormulaSandboxError,
    validate_formula_expr,
)
from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


# --------------------------------------------------------------------------- #
# Whitelist + unit-level                                                      #
# --------------------------------------------------------------------------- #


def test_whitelist_contains_formula_primitives() -> None:
    """All named primitives are in the whitelist."""
    for name in ("land", "lor", "lnot", "implies", "iff", "equals", "forall", "exists"):
        assert name in WHITELIST


def test_whitelist_contains_bare_distribution_factories() -> None:
    """Distribution factories are imported as bare ``gaia.engine.lang`` names."""
    for name in ("Normal", "LogNormal", "Beta", "Gamma", "Poisson", "Binomial"):
        assert name in WHITELIST


def test_bare_distribution_factory_accepted() -> None:
    """The bare ``<Factory>`` shape passes the sandbox visitor."""
    from gaia.cli.commands.author._formula_sandbox import validate_formula_expr

    # No assert needed beyond a non-raising call.
    validate_formula_expr("Normal('normal variable', mu=0, sigma=1)")
    validate_formula_expr("Binomial('count variable', n=5, p=0.5)")


def test_dotted_bayes_distribution_factory_now_refused() -> None:
    """A dotted ``bayes.Normal(...)`` is refused by the sandbox."""
    import pytest as _pytest

    from gaia.cli.commands.author._formula_sandbox import (
        FormulaSandboxError,
        validate_formula_expr,
    )

    with _pytest.raises(FormulaSandboxError):
        validate_formula_expr("bayes.Normal(mu=0, sigma=1)")


def test_whitelist_contains_claim_atom() -> None:
    """ClaimAtom bridges Claim identifiers into formula calls."""
    assert "ClaimAtom" in WHITELIST


def test_whitelist_omits_uniform() -> None:
    """``Uniform`` does not ship in v0.5 (sanity check)."""
    # The engine ``__all__`` from ``gaia.engine.lang.runtime.distribution``
    # carries no Uniform; the sandbox aligns with the concrete shipping
    # set.
    assert "Uniform" not in WHITELIST


def test_simple_atom_passes() -> None:
    out = validate_formula_expr("ClaimAtom(a)", extra_names={"a"})
    assert out.expression == "ClaimAtom(a)"
    assert "ClaimAtom" in out.referenced_names
    assert "a" in out.referenced_names


def test_land_of_atoms_passes() -> None:
    out = validate_formula_expr(
        "land(ClaimAtom(a), ClaimAtom(b))",
        extra_names={"a", "b"},
    )
    assert "land" in out.referenced_names


def test_nested_implies_iff_passes() -> None:
    out = validate_formula_expr(
        "iff(land(ClaimAtom(a), ClaimAtom(b)), implies(ClaimAtom(c), ClaimAtom(d)))",
        extra_names={"a", "b", "c", "d"},
    )
    assert "iff" in out.referenced_names
    assert "implies" in out.referenced_names


def test_distribution_factory_passes_via_bare_shape() -> None:
    """Distribution factories are reached as bare ``gaia.engine.lang`` imports."""
    out = validate_formula_expr("Normal('response', mu=200, sigma=50)")
    assert "Normal" in out.referenced_names


def test_unknown_name_rejected() -> None:
    """A name outside the whitelist + extras raises FormulaSandboxError."""
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("os(ClaimAtom(a))", extra_names={"a"})
    assert "os" in str(exc.value)


def test_dunder_reference_rejected() -> None:
    """Dunder names are always denied even if listed in extras."""
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("__import__('os')")
    assert "__import__" in str(exc.value)


def test_attribute_access_rejected() -> None:
    """Attribute access is structurally rejected."""
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("ClaimAtom(a).__class__", extra_names={"a"})
    assert "attribute" in str(exc.value).lower()


def test_lambda_rejected() -> None:
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("(lambda: ClaimAtom(a))()", extra_names={"a"})
    assert "lambda" in str(exc.value).lower()


def test_subscript_rejected() -> None:
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("ClaimAtom(a)[0]", extra_names={"a"})
    assert "subscript" in str(exc.value).lower()


def test_kwargs_unpacking_rejected() -> None:
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("Normal(**{'mu': 0})")
    assert "kwargs" in str(exc.value).lower()


def test_empty_expression_rejected() -> None:
    with pytest.raises(FormulaSandboxError):
        validate_formula_expr("")


def test_syntax_error_rejected() -> None:
    with pytest.raises(FormulaSandboxError) as exc:
        validate_formula_expr("ClaimAtom(a")
    assert "not valid python" in str(exc.value).lower()


# --------------------------------------------------------------------------- #
# Integration — sandbox runs on decompose --formula-expr                      #
# --------------------------------------------------------------------------- #


def _seed_extra_atoms(gaia_package: FixturePackage) -> None:
    existing = gaia_package.source_init.read_text()
    gaia_package.source_init.write_text(
        existing
        + "\natom_a = claim('Atom A.')\n"
        + "atom_b = claim('Atom B.')\n"
        + "composite = claim('Composite.')\n"
    )


def test_decompose_formula_expr_sandbox_accepts_whitelisted_call(
    gaia_package: FixturePackage,
) -> None:
    """Decompose --formula-expr passes when the expression is on-spec."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a,atom_b",
            "--formula-expr",
            "iff(ClaimAtom(atom_a), ClaimAtom(atom_b))",
            "--dsl-binding-name",
            "sandbox_ok",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output


def test_decompose_formula_expr_sandbox_rejects_attribute_access(
    gaia_package: FixturePackage,
) -> None:
    """Attribute access fails the sandbox and surfaces as exit 2."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a",
            "--formula-expr",
            "ClaimAtom(atom_a).__class__",
            "--dsl-binding-name",
            "leak_attempt",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "sandbox" in diags[0]["message"].lower()


def test_decompose_formula_expr_sandbox_rejects_unknown_name(
    gaia_package: FixturePackage,
) -> None:
    """An expression naming a not-whitelisted identifier fails the sandbox."""
    _seed_extra_atoms(gaia_package)
    result = runner.invoke(
        app,
        [
            "author",
            "decompose",
            "--whole",
            "composite",
            "--parts",
            "atom_a",
            "--formula-expr",
            "exec('print(1)')",
            "--dsl-binding-name",
            "exec_attempt",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "exec" in diags[0]["message"]


# --------------------------------------------------------------------------- #
# Integration — sandbox runs on claim --predicate                             #
# --------------------------------------------------------------------------- #


def test_claim_predicate_sandbox_accepts_whitelisted_formula(
    gaia_package: FixturePackage,
) -> None:
    """``claim --predicate`` accepts a whitelisted formula expression."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Predicate-form claim.",
            "--dsl-binding-name",
            "pred_claim",
            "--references",
            "hypothesis,observation",
            "--predicate",
            "land(ClaimAtom(hypothesis), ClaimAtom(observation))",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "formula=land(ClaimAtom(hypothesis), ClaimAtom(observation))" in written


def test_claim_predicate_sandbox_rejects_attribute_access(
    gaia_package: FixturePackage,
) -> None:
    """``claim --predicate`` rejects attribute access."""
    result = runner.invoke(
        app,
        [
            "author",
            "claim",
            "Predicate-form claim.",
            "--dsl-binding-name",
            "leaky_claim",
            "--predicate",
            "ClaimAtom(hypothesis).__class__",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diags = envelope["diagnostics"]
    assert isinstance(diags, list)
    assert "sandbox" in diags[0]["message"].lower()
