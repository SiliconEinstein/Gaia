"""Unit tests for gaia.lang.compiler.compile internals."""

import pytest

import warnings

from gaia.lang import (
    Step,
    claim,
    infer,
    noisy_and,
    setting,
    composite,
    abduction,
    contradiction,
    induction,
)
from gaia.lang.compiler.compile import (
    compile_package_artifact,
    _compile_reason,
    _extract_at_labels,
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
        b = claim("Claim B.", given=[a])
        b.label = "b"
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


def test_compile_abduction_creates_formal_strategy():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        obs = claim("Observation.")
        obs.label = "obs"
        hyp = claim("Hypothesis.")
        hyp.label = "hyp"
        abduction(observation=obs, hypothesis=hyp, reason="best explanation")
    result = compile_package_artifact(pkg)
    # abduction is a compile-time formal strategy
    assert len(result.graph.strategies) == 1
    strat = result.graph.strategies[0]
    assert strat.type == "abduction"


def test_compile_operator():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        c = contradiction(a, b, reason="they conflict")
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


# ── @label validation ──


def test_extract_at_labels_string():
    labels = _extract_at_labels("Based on @premise_a and @premise_b, we conclude...")
    assert labels == {"premise_a", "premise_b"}


def test_extract_at_labels_none():
    assert _extract_at_labels(None) == set()


def test_extract_at_labels_list():
    labels = _extract_at_labels(["Step using @claim_x.", Step(reason="Also @claim_y.")])
    assert labels == {"claim_x", "claim_y"}


def test_at_label_valid_no_warning():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        infer(premises=[a], conclusion=b, reason="Derived from @a.")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
        at_warnings = [x for x in w if "@" in str(x.message)]
        assert len(at_warnings) == 0


def test_at_label_unknown_warns():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        infer(premises=[a], conclusion=b, reason="Uses @nonexistent.")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
        at_warnings = [x for x in w if "nonexistent" in str(x.message)]
        assert len(at_warnings) == 1
        assert "does not match any knowledge label" in str(at_warnings[0].message)


def test_at_label_not_in_premises_warns():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        c = claim("C.")
        c.label = "c"
        infer(premises=[a], conclusion=b, reason="Uses @a and @c.")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
        at_warnings = [x for x in w if "@c" in str(x.message)]
        assert len(at_warnings) == 1
        assert "not in premises or background" in str(at_warnings[0].message)


def test_at_label_in_background_ok():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        ctx = setting("Context.")
        ctx.label = "ctx"
        a = claim("A.")
        a.label = "a"
        b = claim("B.")
        b.label = "b"
        infer(
            premises=[a], conclusion=b, background=[ctx], reason="Given @a under conditions @ctx."
        )
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
        at_warnings = [x for x in w if "@" in str(x.message)]
        assert len(at_warnings) == 0


def test_induction_reason_at_labels_do_not_warn_on_sub_abductions():
    pkg = CollectedPackage("test_pkg", namespace="github", version="1.0.0")
    with pkg:
        law = claim("Law.")
        law.label = "law"
        obs1 = claim("Observation 1.")
        obs1.label = "obs1"
        obs2 = claim("Observation 2.")
        obs2.label = "obs2"
        induction([obs1, obs2], law, reason="Generalizes from @obs1 and @obs2.")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        compile_package_artifact(pkg)
        at_warnings = [x for x in w if "@" in str(x.message)]
        assert len(at_warnings) == 0


def test_compile_induction():
    """Induction compiles to CompositeStrategy + FormalStrategy sub-abductions."""
    pkg = CollectedPackage("test_induction", namespace="github", version="1.0.0")
    with pkg:
        law = claim("All metals expand when heated.")
        law.label = "law"
        obs1 = claim("Iron expands when heated.")
        obs1.label = "obs1"
        obs2 = claim("Copper expands when heated.")
        obs2.label = "obs2"
        alt1 = claim("Iron expansion has local cause.")
        alt1.label = "alt1"

        induction([obs1, obs2], law, alt_exps=[alt1, None])

    result = compile_package_artifact(pkg)

    # Find the CompositeStrategy (type=induction)
    composites = [
        s for s in result.graph.strategies if hasattr(s, "sub_strategies") and s.sub_strategies
    ]
    assert len(composites) == 1
    comp = composites[0]
    assert comp.type == "induction"

    # It should reference 2 sub-strategies
    assert len(comp.sub_strategies) == 2

    # Sub-strategies should be FormalStrategy(type=abduction)
    strategy_by_id = {s.strategy_id: s for s in result.graph.strategies}
    for sub_id in comp.sub_strategies:
        sub = strategy_by_id[sub_id]
        assert sub.type == "abduction"
        assert hasattr(sub, "formal_expr")  # formalized at compile time
