"""Smoke test — every name introduced in Milestone A is reachable from `gaia.lang`."""

import subprocess
import sys


def test_milestone_a_public_surface():
    import gaia.engine.lang as lang

    expected = {
        # primitives
        "Nat",
        "Real",
        "Probability",
        "Bool",
        "PrimitiveType",
        # knowledge
        "Variable",
        "Domain",
        "ClaimKind",
        # formula AST
        "Term",
        "Constant",
        "FunctionApp",
        "ArithOp",
        "is_term",
        "Formula",
        "is_formula",
        "Equals",
        "NotEquals",
        "Greater",
        "GreaterEqual",
        "Less",
        "LessEqual",
        "UserPredicate",
        "ClaimAtom",
        "Land",
        "Lor",
        "Lnot",
        "Implies",
        "Iff",
        "Forall",
        "Exists",
        "FunctionSymbol",
        "PredicateSymbol",
    }
    missing = expected - set(dir(lang))
    assert not missing, f"missing public exports: {sorted(missing)}"


def test_gaia_lang_does_not_export_core_predict_verb():
    import gaia.engine.lang as lang

    # `predict` and `likelihood` remain bayes-specific verbs in
    # `gaia.engine.bayes` and must not pollute the top-level namespace.
    assert "predict" not in dir(lang)
    assert "predict" not in lang.__all__
    assert not hasattr(lang, "Predict")
    assert "likelihood" not in lang.__all__
    assert "Predict" not in lang.__all__
    # Distribution family names (Normal, LogNormal, Beta, ..., Binomial) are
    # intentionally top-level since v0.6 — they construct first-class
    # continuous-quantity Distributions for the predicate / equation surface.
    # See gaia.lang.runtime.distribution.


def test_gaia_lang_does_not_export_marker_only_causal_surface():
    import gaia.engine.lang as lang

    assert "Causes" not in dir(lang)
    assert "causal" not in dir(lang)
    assert "causes" not in dir(lang)
    assert "Causes" not in lang.__all__
    assert "causal" not in lang.__all__
    assert "causes" not in lang.__all__
    assert not hasattr(lang.ClaimKind, "CAUSAL")


def test_bayes_surface_exposes_model_and_compare_verbs():
    """The unified v0.5 Bayes surface is ``model`` + ``compare`` + ``PrecomputedLikelihoods``.

    The earlier in-flight alpha exposed ``bayes.likelihood``
    / ``bayes.data`` plus typed-value ``bayes.Normal`` / ``bayes.Binomial``
    distribution aliases. The clean break (see
    ``docs/specs/2026-05-17-bayes-unified-design.md``) replaces all of
    that with three names. This pin captures both the positive surface
    and the absence of the legacy names.
    """
    import gaia.engine.bayes as bayes

    assert hasattr(bayes, "model")
    assert hasattr(bayes, "compare")
    assert hasattr(bayes, "PrecomputedLikelihoods")
    assert "model" in bayes.__all__
    assert "compare" in bayes.__all__
    assert "PrecomputedLikelihoods" in bayes.__all__

    # Legacy verbs are gone — no compatibility shim.
    for removed in ("predict", "likelihood", "data"):
        assert not hasattr(bayes, removed), (
            f"gaia.engine.bayes.{removed} should be gone; use model / compare / observe instead"
        )

    # Typed-value distribution re-exports are gone — use gaia.engine.lang.
    for removed in ("Normal", "Binomial", "BetaBinomial", "Beta", "Poisson"):
        assert not hasattr(bayes, removed), (
            f"gaia.engine.bayes.{removed} should be gone; import gaia.engine.lang.{removed} instead"
        )


def test_gaia_lang_import_does_not_eagerly_import_bayes():
    code = (
        "import sys\n"
        "import gaia.engine.lang as lang\n"
        "print('gaia.engine.bayes' in sys.modules)\n"
        "print('scipy' in sys.modules)\n"
        "import gaia.engine.bayes as bayes\n"
        "print(hasattr(bayes, 'model'))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.stdout.splitlines() == ["False", "False", "True"]
