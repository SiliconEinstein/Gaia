"""Smoke test — every name introduced in Milestone A is reachable from `gaia.lang`."""


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
