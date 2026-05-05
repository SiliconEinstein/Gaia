"""Smoke test — every name introduced in Milestone A is reachable from `gaia.lang`."""

import subprocess
import sys


def test_milestone_a_public_surface():
    import gaia.lang as lang

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


def test_gaia_lang_predict_is_core_bayes_free_verb():
    import gaia.lang as lang

    assert lang.predict.__module__ == "gaia.lang.dsl.support"
    assert "Binomial" not in lang.__all__
    assert "likelihood" not in lang.__all__


def test_gaia_lang_import_does_not_eagerly_import_bayes():
    code = (
        "import sys\n"
        "import gaia.lang as lang\n"
        "print('gaia.lang.bayes' in sys.modules)\n"
        "print('scipy' in sys.modules)\n"
        "from gaia.lang import bayes\n"
        "print(hasattr(bayes, 'model'))\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        check=True,
        text=True,
        capture_output=True,
    )
    assert result.stdout.splitlines() == ["False", "False", "True"]
