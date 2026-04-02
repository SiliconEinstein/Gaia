from gaia.lang import Package, claim, contradiction, deduction, question, setting
from gaia.lang.compiler import compile_package
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def test_compile_produces_valid_ir():
    with Package("test_pkg", namespace="reg") as pkg:
        setting("Background.")
        claim("Assertion.")
        question("Question?")
    ir = compile_package(pkg)
    assert ir["package_name"] == "test_pkg"
    assert ir["namespace"] == "reg"
    assert len(ir["knowledges"]) == 3
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors


def test_compile_knowledge_has_qid():
    with Package("test_pkg", namespace="reg") as pkg:
        claim("A claim.")
    pkg.knowledge[0].label = "my_claim"
    ir = compile_package(pkg)
    k = ir["knowledges"][0]
    assert k["id"] == "reg:test_pkg::my_claim"
    assert k["type"] == "claim"
    assert k["content"] == "A claim."
    assert k["content_hash"] is not None


def test_compile_strategy():
    with Package("test_pkg", namespace="reg") as pkg:
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
    with Package("test_pkg", namespace="reg") as pkg:
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
        with Package("test_pkg", namespace="reg") as pkg:
            a = claim("A.")
            claim("B.", given=[a])
        pkg.knowledge[0].label = "a"
        pkg.knowledge[1].label = "b"
        return compile_package(pkg)

    ir1 = build()
    ir2 = build()
    assert ir1["ir_hash"] == ir2["ir_hash"]


def test_compile_input_claims():
    with Package("test_pkg", namespace="reg") as pkg:
        a = claim("Input claim.")
        claim("Derived.", given=[a])
    pkg.knowledge[0].label = "a"
    pkg.knowledge[1].label = "b"
    ir = compile_package(pkg)
    inputs = [k for k in ir["knowledges"] if k.get("is_input")]
    assert len(inputs) == 1
    assert inputs[0]["label"] == "a"


def test_helper_claims_not_marked_as_input():
    """Bug fix: contradiction helper claims should NOT be is_input."""
    with Package("test_pkg", namespace="reg") as pkg:
        a = claim("A.")
        b = claim("B.")
        contradiction(a, b, reason="Conflict")
    pkg.knowledge[0].label = "a"
    pkg.knowledge[1].label = "b"
    pkg.knowledge[2].label = "contra"
    ir = compile_package(pkg)
    helper = [k for k in ir["knowledges"] if "not_both_true" in k["content"]]
    assert len(helper) == 1
    assert helper[0]["is_input"] is False


def test_formal_internal_helpers_not_marked_as_input():
    """Bug fix: deduction internal helper claims should NOT be is_input."""
    with Package("test_pkg", namespace="reg") as pkg:
        law = claim("Universal law.")
        case = claim("Specific case.")
        instance = claim("Specific instance.")
        deduction(premises=[law, case], conclusion=instance)
    pkg.knowledge[0].label = "law"
    pkg.knowledge[1].label = "case"
    pkg.knowledge[2].label = "instance"
    ir = compile_package(pkg)
    helpers = [
        k
        for k in ir["knowledges"]
        if k.get("metadata", {}).get("helper_visibility") == "formal_internal"
    ]
    assert helpers
    for h in helpers:
        assert h["is_input"] is False


def test_foreign_knowledge_preserves_identity():
    """Bug fix: imported claims should keep their original identity, not get rewritten."""
    from gaia.lang.runtime import Knowledge

    # Simulate a foreign claim (created outside any Package context)
    foreign_claim = Knowledge(content="Foreign assertion.", type="claim")
    foreign_claim.label = "foreign_conclusion"

    with Package("my_pkg", namespace="reg") as pkg:
        claim("My derived claim.", given=[foreign_claim])
    pkg.knowledge[0].label = "local_claim"
    ir = compile_package(pkg)

    # The strategy's premises should reference the foreign claim, not a local QID
    strategy = ir["strategies"][0]
    assert strategy["premises"] == ["external:anonymous::foreign_conclusion"]
    foreign_nodes = [
        k for k in ir["knowledges"] if k["id"] == "external:anonymous::foreign_conclusion"
    ]
    assert len(foreign_nodes) == 1
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors


def test_background_carried_through_given_shorthand():
    """Bug fix: claim(given=..., background=...) should pass background to strategy."""
    with Package("test_pkg", namespace="reg") as pkg:
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
