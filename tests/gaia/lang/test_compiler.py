from gaia.lang import Package, claim, question, setting
from gaia.lang.compiler import compile_package
from gaia.lang.operators import contradiction
from gaia.lang.strategies import deduction


def test_compile_produces_valid_ir():
    with Package("test_pkg", namespace="test") as pkg:
        setting("Background.")
        claim("Assertion.")
        question("Question?")
    ir = compile_package(pkg)
    assert ir["package"]["name"] == "test_pkg"
    assert ir["package"]["namespace"] == "test"
    assert len(ir["knowledge"]) == 3


def test_compile_knowledge_has_qid():
    with Package("test_pkg", namespace="test") as pkg:
        claim("A claim.")
    pkg.knowledge[0].label = "my_claim"
    ir = compile_package(pkg)
    k = ir["knowledge"][0]
    assert k["id"] == "test:test_pkg::my_claim"
    assert k["type"] == "claim"
    assert k["content"] == "A claim."
    assert k["content_hash"] is not None


def test_compile_strategy():
    with Package("test_pkg", namespace="test") as pkg:
        a = claim("A.")
        claim("B.", given=[a])
    pkg.knowledge[0].label = "a"
    pkg.knowledge[1].label = "b"
    ir = compile_package(pkg)
    assert len(ir["strategies"]) == 1
    s = ir["strategies"][0]
    assert s["type"] == "noisy_and"
    assert s["strategy_id"].startswith("lcs_")


def test_compile_operator():
    with Package("test_pkg", namespace="test") as pkg:
        a = claim("A.")
        b = claim("B.")
        contradiction(a, b, reason="Conflict")
    pkg.knowledge[0].label = "a"
    pkg.knowledge[1].label = "b"
    pkg.knowledge[2].label = "contra"
    ir = compile_package(pkg)
    assert len(ir["operators"]) == 1
    op = ir["operators"][0]
    assert op["operator"] == "contradiction"
    assert op["operator_id"].startswith("lco_")


def test_compile_ir_hash_deterministic():
    def build():
        with Package("test_pkg", namespace="test") as pkg:
            a = claim("A.")
            claim("B.", given=[a])
        pkg.knowledge[0].label = "a"
        pkg.knowledge[1].label = "b"
        return compile_package(pkg)

    ir1 = build()
    ir2 = build()
    assert ir1["ir_hash"] == ir2["ir_hash"]


def test_compile_input_claims():
    with Package("test_pkg", namespace="test") as pkg:
        a = claim("Input claim.")
        claim("Derived.", given=[a])
    pkg.knowledge[0].label = "a"
    pkg.knowledge[1].label = "b"
    ir = compile_package(pkg)
    inputs = [k for k in ir["knowledge"] if k.get("is_input")]
    assert len(inputs) == 1
    assert inputs[0]["label"] == "a"


def test_helper_claims_not_marked_as_input():
    """Bug fix: contradiction helper claims should NOT be is_input."""
    with Package("test_pkg", namespace="test") as pkg:
        a = claim("A.")
        b = claim("B.")
        contradiction(a, b, reason="Conflict")
    pkg.knowledge[0].label = "a"
    pkg.knowledge[1].label = "b"
    pkg.knowledge[2].label = "contra"
    ir = compile_package(pkg)
    helper = [k for k in ir["knowledge"] if "not_both_true" in k["content"]]
    assert len(helper) == 1
    assert helper[0]["is_input"] is False


def test_formal_internal_helpers_not_marked_as_input():
    """Bug fix: deduction internal helper claims should NOT be is_input."""
    with Package("test_pkg", namespace="test") as pkg:
        law = claim("Universal law.")
        instance = claim("Specific instance.")
        deduction(premises=[law], conclusion=instance)
    pkg.knowledge[0].label = "law"
    pkg.knowledge[1].label = "instance"
    ir = compile_package(pkg)
    helpers = [
        k for k in ir["knowledge"] if k["metadata"].get("helper_visibility") == "formal_internal"
    ]
    for h in helpers:
        assert h["is_input"] is False


def test_foreign_knowledge_preserves_identity():
    """Bug fix: imported claims should keep their original identity, not get rewritten."""
    from gaia.lang.runtime import Knowledge

    # Simulate a foreign claim (created outside any Package context)
    foreign_claim = Knowledge(content="Foreign assertion.", type="claim")
    foreign_claim.label = "foreign_conclusion"

    with Package("my_pkg", namespace="test") as pkg:
        claim("My derived claim.", given=[foreign_claim])
    pkg.knowledge[0].label = "local_claim"
    ir = compile_package(pkg)

    # The strategy's premises should reference the foreign claim, not a local QID
    strategy = ir["strategies"][0]
    # Foreign claim is not in pkg.knowledge, so it should get an external:: prefix
    foreign_refs = [p for p in strategy["premises"] if "external::" in p]
    assert len(foreign_refs) == 1
    assert "foreign_conclusion" in foreign_refs[0]


def test_background_carried_through_given_shorthand():
    """Bug fix: claim(given=..., background=...) should pass background to strategy."""
    with Package("test_pkg", namespace="test") as pkg:
        bg = setting("Context info.")
        premise = claim("A premise.")
        claim("Derived.", given=[premise], background=[bg])
    pkg.knowledge[0].label = "bg"
    pkg.knowledge[1].label = "premise"
    pkg.knowledge[2].label = "derived"
    ir = compile_package(pkg)

    strategy = ir["strategies"][0]
    assert len(strategy["background"]) == 1
    assert "bg" in strategy["background"][0]
