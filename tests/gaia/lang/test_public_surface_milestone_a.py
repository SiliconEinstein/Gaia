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


def test_bayes_surface_exposes_v05_and_v06_authoring_verbs():
    """v0.6 PoC: legacy ``bayes.model`` coexists with the new ``bayes.predict``.

    The Milestone-A test originally asserted that ``bayes.predict`` was
    *not* present (the v0.5 design picked ``bayes.model`` as the verb name
    deliberately). The v0.6 unified-bayes redesign (see
    ``docs/specs/2026-05-17-bayes-unified-design.md``) introduces
    ``predict`` and ``compare`` as the canonical surface; the legacy
    ``model`` / ``likelihood`` verbs stay importable through one release
    so existing packages keep compiling. This assertion captures both:
    legacy names are still reachable, new names are wired up.
    """
    import gaia.engine.bayes as bayes

    assert hasattr(bayes, "model")
    assert hasattr(bayes, "predict")
    assert hasattr(bayes, "likelihood")
    assert hasattr(bayes, "compare")
    assert "model" in bayes.__all__
    assert "predict" in bayes.__all__
    assert "likelihood" in bayes.__all__
    assert "compare" in bayes.__all__


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
