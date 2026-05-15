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
        "Causes",
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
    # `gaia.lang.bayes` and must not pollute the top-level namespace.
    assert "predict" not in dir(lang)
    assert "predict" not in lang.__all__
    assert not hasattr(lang, "Predict")
    assert "likelihood" not in lang.__all__
    assert "Predict" not in lang.__all__
    # Distribution family names (Normal, LogNormal, Beta, ..., Binomial) are
    # intentionally top-level since v0.6 — they construct first-class
    # continuous-quantity Distributions for the predicate / equation surface.
    # See gaia.lang.runtime.distribution.


def test_bayes_surface_uses_model_not_predict_alias():
    from gaia.engine.lang import bayes

    assert hasattr(bayes, "model")
    assert not hasattr(bayes, "predict")
    assert "predict" not in bayes.__all__


def test_gaia_lang_import_does_not_eagerly_import_bayes():
    code = (
        "import sys\n"
        "import gaia.engine.lang as lang\n"
        "print('gaia.lang.bayes' in sys.modules)\n"
        "print('scipy' in sys.modules)\n"
        "from gaia.engine.lang import bayes\n"
        "print(hasattr(bayes, 'model'))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.stdout.splitlines() == ["False", "False", "True"]
