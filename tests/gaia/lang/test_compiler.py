"""Unit tests for gaia.lang.compiler.compile internals."""

import pytest

from gaia.lang import (
    Step,
    claim,
    compare,
    noisy_and,
    setting,
    composite,
    abduction,
    contradiction,
    fills,
    induction,
    support,
)
from gaia.lang.compiler.compile import (
    compile_package_artifact,
    _compile_reason,
    _knowledge_id,
    _normalize_label,
    _anonymous_label,
    _content_hash,
)
from gaia.lang.runtime.package import CollectedPackage


# ── _content_hash / _anonymous_label / _normalize_label ──


def test_content_hash_deterministic():
    a = claim("Test content.")
    b = claim("Test content.")
    assert _content_hash(a) == _content_hash(b)


def test_content_hash_differs_by_type():
    a = claim("Same text.")
    b = setting("Same text.")
    assert _content_hash(a) != _content_hash(b)


def test_anonymous_label_format():
    k = claim("Some claim.")
    label = _anonymous_label(k)
    assert label.startswith("_anon_")
    assert len(label) == len("_anon_") + 8


def test_normalize_label_basic():
    assert _normalize_label("Hello World") == "hello_world"


def test_normalize_label_empty():
    assert _normalize_label("") == "_anon"


def test_normalize_label_starts_with_digit():
    assert _normalize_label("3d_model") == "_3d_model"


# ── _knowledge_id ──


def test_knowledge_id_local_with_label():
    pkg = CollectedPackage("test_pkg", namespace="github")
    k = claim("A.")
    k.label = "my_claim"
    pkg.knowledge.append(k)
    kid, counter = _knowledge_id(k, pkg, local_anon_counter=0)
    assert kid == "github:test_pkg::my_claim"
    assert counter == 0  # label was set, no counter increment


def test_knowledge_id_local_anonymous():
    pkg = CollectedPackage("test_pkg", namespace="github")
    k = claim("A.")
    k.label = None
    pkg.knowledge.append(k)
    kid, counter = _knowledge_id(k, pkg, local_anon_counter=5)
    assert kid == "github:test_pkg::_anon_005"
    assert counter == 6


def test_knowledge_id_foreign_with_metadata_qid():
    pkg = CollectedPackage("test_pkg", namespace="github")
    k = claim("Foreign claim.")
    k.metadata["qid"] = "external:other_pkg::foreign_claim"
    # NOT in pkg.knowledge → foreign
    kid, counter = _knowledge_id(k, pkg, local_anon_counter=0)
    assert kid == "external:other_pkg::foreign_claim"


def test_knowledge_id_foreign_with_package():
    pkg = CollectedPackage("test_pkg", namespace="github")
    foreign_pkg = CollectedPackage("other_pkg", namespace="github")
    k = claim("Foreign claim.")
    k.label = "fc"
    k._package = foreign_pkg
    kid, counter = _knowledge_id(k, pkg, local_anon_counter=0)
    assert kid == "github:other_pkg::fc"


def test_knowledge_id_foreign_fallback():
    pkg = CollectedPackage("test_pkg", namespace="github")
    k = claim("Orphan claim.")
    k.label = "orphan"
    k._package = None
    kid, counter = _knowledge_id(k, pkg, local_anon_counter=0)
    assert kid == "external:anonymous::orphan"


# ── _compile_reason ──


def test_compile_reason_string():
    result = _compile_reason("simple reason", {})
    assert result is None  # string goes to metadata, not steps


def test_compile_reason_empty_list():
    result = _compile_reason([], {})
    assert result is None


def test_compile_reason_string_list():
    result = _compile_reason(["step 1", "step 2"], {})
    assert len(result) == 2
    assert result[0].reasoning == "step 1"


def test_compile_reason_step_objects():
    a = claim("A.")
    km = {id(a): "ns:p::a"}
    result = _compile_reason([Step(reason="uses A", premises=[a])], km)
    assert len(result) == 1
    assert result[0].reasoning == "uses A"
    assert result[0].premises == ["ns:p::a"]


def test_compile_reason_invalid_type():
    with pytest.raises(ValueError, match="Unsupported reason entry type"):
        _compile_reason([123], {})


# ── compile_package_artifact ──


def test_compile_basic_package():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("Claim A.")
        a.label = "a"
        b = claim("Claim B.")
        b.label = "b"
        noisy_and([a], b)
    result = compile_package_artifact(pkg)
    assert result.graph.namespace == "github"
    assert result.graph.package_name == "test_pkg"
    knowledge_ids = {k.label: k.id for k in result.graph.knowledges}
    assert "github:test_pkg::a" in knowledge_ids.values()
    assert "github:test_pkg::b" in knowledge_ids.values()
    assert len(result.graph.strategies) == 1


def test_compile_with_background():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        ctx = setting("Context.")
        ctx.label = "ctx"
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        noisy_and(premises=[a], conclusion=b, background=[ctx])
    result = compile_package_artifact(pkg)
    strat = result.graph.strategies[0]
    assert strat.background is not None
    assert "github:test_pkg::ctx" in strat.background


def test_compile_with_reason_steps():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        noisy_and(
            premises=[a],
            conclusion=b,
            reason=[Step(reason="A supports B", premises=[a])],
        )
    result = compile_package_artifact(pkg)
    strat = result.graph.strategies[0]
    assert strat.steps is not None
    assert strat.steps[0].reasoning == "A supports B"
    assert strat.steps[0].premises == ["github:test_pkg::a"]


def test_compile_composite_strategy():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        mid = claim("Mid.")
        mid.label = "mid"
        c = claim("C.")
        c.label = "c"
        s1 = noisy_and(premises=[a], conclusion=mid)
        s2 = noisy_and(premises=[mid], conclusion=c)
        composite(premises=[a], conclusion=c, sub_strategies=[s1, s2])
    result = compile_package_artifact(pkg)
    # Should have 3 strategies: s1, s2, and composite
    assert len(result.graph.strategies) == 3


def test_compile_abduction_creates_composite_strategy():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        obs = claim("Observation.")
        obs.label = "obs"
        theory_h = claim("Hypothesis H.")
        theory_h.label = "theory_h"
        theory_alt = claim("Alternative theory.")
        theory_alt.label = "theory_alt"
        pred_h = claim("Prediction from H.")
        pred_h.label = "pred_h"
        pred_alt = claim("Prediction from Alt.")
        pred_alt.label = "pred_alt"

        sup_h = support(premises=[theory_h], conclusion=obs)
        sup_alt = support(premises=[theory_alt], conclusion=obs)
        comp = compare(pred_h, pred_alt, obs)
        abduction(sup_h, sup_alt, comp, reason="best explanation")
    result = compile_package_artifact(pkg)
    # abduction is now a CompositeStrategy with sub-strategies
    composites = [
        s for s in result.graph.strategies if hasattr(s, "sub_strategies") and s.sub_strategies
    ]
    assert len(composites) == 1
    found_comp = composites[0]
    assert found_comp.type == "abduction"


def test_compile_operator():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        c = contradiction(a, b, reason="they conflict", prior=0.9)
        c.label = "a_vs_b"
    result = compile_package_artifact(pkg)
    assert len(result.graph.operators) == 1
    op = result.graph.operators[0]
    assert op.operator == "contradiction"


def test_compile_exported_labels():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    pkg._exported_labels = {"b"}
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
    result = compile_package_artifact(pkg)
    by_label = {k.label: k for k in result.graph.knowledges}
    assert by_label["a"].exported is False
    assert by_label["b"].exported is True


def test_compile_fills_preserves_relation_metadata_and_foreign_target():
    foreign_pkg = CollectedPackage("dep_pkg", namespace="github", version="1.4.0")
    with foreign_pkg:
        target = claim("Missing premise.")
        target.label = "target"

    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        result = claim("B theorem.")
        result.label = "result"
        fills(source=result, target=target, strength="conditional", mode="infer")

    compiled = compile_package_artifact(pkg)
    strat = compiled.graph.strategies[0]
    assert strat.type == "infer"
    assert strat.premises == ["github:test_pkg::result"]
    assert strat.conclusion == "github:dep_pkg::target"
    assert strat.metadata["gaia"]["relation"] == {
        "type": "fills",
        "strength": "conditional",
        "mode": "infer",
    }


def test_compile_title_preserved():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.", title="Claim Alpha")
        a.label = "a"
    result = compile_package_artifact(pkg)
    ir_a = next(k for k in result.graph.knowledges if k.label == "a")
    assert ir_a.title == "Claim Alpha"


def test_compile_module_order():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    pkg._module_order = ["sec_a", "sec_b"]
    with pkg:
        a = claim("A.")
        a.label = "a"
    result = compile_package_artifact(pkg)
    assert result.graph.module_order == ["sec_a", "sec_b"]


def test_compile_module_titles():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    pkg._module_order = ["intro"]
    pkg._module_titles = {"intro": "Introduction"}
    with pkg:
        a = claim("A.")
        a.label = "a"
    result = compile_package_artifact(pkg)
    assert result.graph.module_titles == {"intro": "Introduction"}


def test_compile_induction():
    """Induction compiles to CompositeStrategy with support sub-strategies."""
    pkg = CollectedPackage("test_induction", namespace="github", version="1.0.0")
    with pkg:
        law = claim("All metals expand when heated.")
        law.label = "law"
        obs1 = claim("Iron expands when heated.")
        obs1.label = "obs1"
        obs2 = claim("Copper expands when heated.")
        obs2.label = "obs2"

        sup1 = support(premises=[obs1], conclusion=law)
        sup2 = support(premises=[obs2], conclusion=law)
        induction(sup1, sup2, law)

    result = compile_package_artifact(pkg)

    # Find the CompositeStrategy (type=induction)
    composites = [
        s for s in result.graph.strategies if hasattr(s, "sub_strategies") and s.sub_strategies
    ]
    assert len(composites) == 1
    comp = composites[0]
    assert comp.type == "induction"

    # It should reference 2 sub-strategies (the supports)
    assert len(comp.sub_strategies) == 2

    # Sub-strategies should be support
    strategy_by_id = {s.strategy_id: s for s in result.graph.strategies}
    for sub_id in comp.sub_strategies:
        sub = strategy_by_id[sub_id]
        assert sub.type == "support"
