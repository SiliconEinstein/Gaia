"""Tests for gaia check --brief / --show warrant structure output."""

from __future__ import annotations

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _write_two_module_package(pkg_dir):
    """Package with two modules: background + reasoning, using support strategy."""
    name = "brief_demo"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text(
        "from .background import *\nfrom .reasoning import *\n"
    )
    (pkg_dir / name / "background.py").write_text(
        "from gaia.lang import claim, setting\n\n"
        'env = setting("Experiment conducted at room temperature.")\n'
        'obs_a = claim("Observation A was recorded.", background=[env])\n'
        'obs_b = claim("Observation B was recorded.")\n'
    )
    (pkg_dir / name / "reasoning.py").write_text(
        "from gaia.lang import claim, support, contradiction\n"
        "from .background import obs_a, obs_b\n\n"
        'hypothesis = claim("The hypothesis holds.")\n'
        "support([obs_a, obs_b], hypothesis,\n"
        '    reason="Two observations converge.", prior=0.85)\n'
        'alt = claim("Alternative explanation.")\n'
        "not_both = contradiction(hypothesis, alt,\n"
        '    reason="Mutually exclusive.", prior=0.99)\n'
    )
    (pkg_dir / name / "priors.py").write_text(
        "from . import obs_a, obs_b, hypothesis, alt\n\n"
        "PRIORS = {\n"
        '    obs_a: (0.9, "Measured directly."),\n'
        '    obs_b: (0.85, "Reported observation."),\n'
        '    alt: (0.3, "Weak alternative."),\n'
        "}\n"
    )


def _write_induction_package(pkg_dir):
    """Package with induction composite strategy (binary support chain)."""
    name = "induction_demo"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text(
        "from gaia.lang import claim, support, induction\n\n"
        'law = claim("Universal law holds.")\n'
        'obs1 = claim("Sample 1 confirms law.")\n'
        'obs2 = claim("Sample 2 confirms law.")\n'
        'obs3 = claim("Sample 3 confirms law.")\n'
        "s1 = support([obs1], law, reason='obs1 supports law', prior=0.9)\n"
        "s2 = support([obs2], law, reason='obs2 supports law', prior=0.9)\n"
        "s3 = support([obs3], law, reason='obs3 supports law', prior=0.85)\n"
        "ind_12 = induction(s1, s2, law=law, reason='independent samples')\n"
        "ind_123 = induction(ind_12, s3, law=law, reason='third sample')\n"
    )
    (pkg_dir / name / "priors.py").write_text(
        "from . import law, obs1, obs2, obs3\n\n"
        "PRIORS = {\n"
        '    law: (0.5, "To be determined by induction."),\n'
        '    obs1: (0.9, "Confirmed."),\n'
        '    obs2: (0.9, "Confirmed."),\n'
        '    obs3: (0.9, "Confirmed."),\n'
        "}\n"
    )


def _compile(pkg_dir):
    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, result.output


# ── Unit tests on generate functions ──


def test_brief_overview_groups_by_module(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_overview

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_overview(ir)
    text = "\n".join(lines)

    # Module headers present
    assert "Module: background" in text
    assert "Module: reasoning" in text

    # Settings appear
    assert "env" in text
    assert "Experiment conducted" in text

    # Claims with roles
    assert "obs_a" in text
    assert "obs_b" in text
    assert "hypothesis" in text

    # Strategy with prior
    assert "support" in text
    assert "0.85" in text

    # Operator
    assert "contradiction" in text


def test_brief_overview_shows_priors(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_overview

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_overview(ir)
    text = "\n".join(lines)

    # Claim priors from priors.py should appear
    assert "prior=0.9" in text
    assert "prior=0.85" in text


def test_brief_module_expands_all_strategies(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_module

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_module(ir, "reasoning")
    text = "\n".join(lines)

    # Module header
    assert "reasoning" in text
    assert "expanded" in text

    # Full claim content (not truncated)
    assert "The hypothesis holds." in text
    assert "Alternative explanation." in text

    # Strategy warrant tree
    assert "support" in text
    assert "Two observations converge." in text

    # Operator
    assert "contradiction" in text
    assert "Mutually exclusive." in text


def test_brief_module_unknown_returns_error(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_module

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_module(ir, "nonexistent")
    text = "\n".join(lines)
    assert "No module" in text


def test_brief_detail_expands_formal_strategy(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_detail

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_detail(ir, "hypothesis")
    text = "\n".join(lines)

    # Claim header
    assert "hypothesis" in text
    assert "The hypothesis holds." in text

    # Warrant tree: support is a FormalStrategy, should show operators
    assert "support" in text
    assert "0.85" in text

    # Premises section
    assert "Premises:" in text
    assert "obs_a" in text
    assert "obs_b" in text


def test_brief_detail_expands_composite(tmp_path):
    pkg_dir = tmp_path / "induction_demo"
    _write_induction_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_detail

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    # Find the composition_warrant generated by induction — it is the derived claim
    # The law claim itself gets a composite strategy conclusion via induction
    # Let's check what labels exist
    labels = [k.get("label") for k in ir["knowledges"] if k.get("label")]

    # induction generates composition_warrant helper claims
    # The law is the target — check if any strategy concludes at law
    strat_conclusions = {s.get("conclusion") for s in ir["strategies"]}
    law_id = None
    for k in ir["knowledges"]:
        if k.get("label") == "law":
            law_id = k["id"]
            break

    # law may or may not be the conclusion of induction (it depends on how the DSL wires it)
    # Instead, look for any CompositeStrategy and test its detail
    composite_labels = []
    for s in ir["strategies"]:
        if s.get("sub_strategies"):
            conc_id = s.get("conclusion")
            for k in ir["knowledges"]:
                if k["id"] == conc_id and k.get("label"):
                    composite_labels.append(k["label"])

    # Should have at least one composite
    assert len(composite_labels) > 0 or law_id in strat_conclusions, (
        f"Expected composite strategy. Labels: {labels}"
    )

    # Try expanding the law claim or any composite conclusion
    target_label = composite_labels[0] if composite_labels else "law"
    lines = generate_brief_detail(ir, target_label)
    text = "\n".join(lines)

    # Should show composite sub-strategies
    assert "composite" in text.lower() or "support" in text.lower()


def test_brief_detail_unknown_label(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_detail

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_detail(ir, "nonexistent_label")
    text = "\n".join(lines)
    assert "No claim or strategy" in text


def test_dispatch_show_routes_module_vs_label(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import dispatch_show

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    # Module name → module expansion
    mod_lines = dispatch_show(ir, "reasoning")
    mod_text = "\n".join(mod_lines)
    assert "expanded" in mod_text

    # Claim label → detail expansion
    label_lines = dispatch_show(ir, "hypothesis")
    label_text = "\n".join(label_lines)
    assert "hypothesis" in label_text
    assert "content:" in label_text

    # Unknown → error
    err_lines = dispatch_show(ir, "does_not_exist")
    err_text = "\n".join(err_lines)
    assert "No module or label" in err_text


# ── CLI integration tests ──


def test_brief_cli_flag(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    result = runner.invoke(app, ["check", "--brief", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Check passed" in result.output
    assert "Module:" in result.output
    assert "support" in result.output


def test_show_cli_flag_module(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    result = runner.invoke(app, ["check", "--show", "reasoning", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "Check passed" in result.output
    assert "expanded" in result.output
    assert "hypothesis" in result.output


def test_show_cli_flag_label(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    result = runner.invoke(app, ["check", "--show", "hypothesis", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "hypothesis" in result.output
    assert "content:" in result.output


def test_show_cli_flag_unknown(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    result = runner.invoke(app, ["check", "--show", "nope", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert "No module or label" in result.output


def test_brief_and_show_combined(tmp_path):
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    result = runner.invoke(app, ["check", "--brief", "--show", "reasoning", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    # Both overview and expanded module should be present
    assert "Module: background" in result.output  # from overview
    assert "expanded" in result.output  # from --show


# ── Coverage tests for edge-case paths ──


def test_truncate_long_text():
    from gaia.cli.commands._brief import _truncate

    short = "hello"
    assert _truncate(short, 80) == "hello"
    long_text = "x" * 200
    result = _truncate(long_text, 80)
    assert len(result) == 80
    assert result.endswith("\u2026")


def test_is_helper_none_and_dunder():
    from gaia.cli.commands._brief import _is_helper

    assert _is_helper(None) is True
    assert _is_helper("") is True
    assert _is_helper("__warrant_xyz") is True
    assert _is_helper("hypothesis") is False


def test_prior_str_variants():
    from gaia.cli.commands._brief import _prior_str

    assert _prior_str(None) == ""
    assert _prior_str({}) == ""
    assert _prior_str({"prior": 0.8}) == ", prior=0.8"


def _write_question_package(pkg_dir):
    """Package with a question node to exercise question rendering paths."""
    name = "question_demo"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text("from .content import *\n")
    (pkg_dir / name / "content.py").write_text(
        "from gaia.lang import claim, question, setting\n\n"
        'env = setting("Test environment.")\n'
        'q = question("What is the mechanism?")\n'
        'obs = claim("Observation recorded.")\n'
    )
    (pkg_dir / name / "priors.py").write_text(
        'from . import obs\n\nPRIORS = {\n    obs: (0.9, "Measured."),\n}\n'
    )


def test_brief_overview_shows_questions(tmp_path):
    """Exercise the Questions section in overview."""
    pkg_dir = tmp_path / "question_demo"
    _write_question_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_overview

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_overview(ir)
    text = "\n".join(lines)

    assert "Questions:" in text
    assert "What is the mechanism?" in text


def test_brief_module_shows_settings_and_questions(tmp_path):
    """Exercise settings and questions sections in module expansion."""
    pkg_dir = tmp_path / "question_demo"
    _write_question_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_module

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_module(ir, "content")
    text = "\n".join(lines)

    assert "Settings:" in text
    assert "Test environment." in text
    assert "Questions:" in text
    assert "What is the mechanism?" in text


def test_brief_detail_independent_premise(tmp_path):
    """Claim with no strategy shows 'independent premise'."""
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_detail

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_detail(ir, "obs_a")
    text = "\n".join(lines)

    assert "independent premise" in text


def _write_abduction_package(pkg_dir):
    """Package with abduction to exercise composite + review notes."""
    name = "abduction_demo"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text("from .reasoning import *\n")
    (pkg_dir / name / "reasoning.py").write_text(
        "from gaia.lang import claim, support, compare, abduction\n\n"
        'obs = claim("Observed data.")\n'
        'hyp = claim("Hypothesis H predicts obs.")\n'
        'alt_pred = claim("Alternative predicts obs.")\n'
        'alt = claim("Alternative hypothesis.")\n'
        "s_h = support([hyp], obs, reason='H explains obs', prior=0.9)\n"
        "s_alt = support([alt], obs, reason='Alt explains obs', prior=0.5)\n"
        "cmp = compare(hyp, alt_pred, obs, reason='compare H vs Alt', prior=0.85)\n"
        "abd = abduction(s_h, s_alt, cmp, reason='IBE comparison')\n"
    )
    (pkg_dir / name / "priors.py").write_text(
        "from . import obs, hyp, alt_pred, alt\n\n"
        "PRIORS = {\n"
        '    obs: (0.95, "Measured."),\n'
        '    hyp: (0.6, "Prior hypothesis."),\n'
        '    alt_pred: (0.4, "Alt prediction."),\n'
        '    alt: (0.3, "Prior alternative."),\n'
        "}\n"
    )


def test_brief_detail_abduction_composite_with_review_notes(tmp_path):
    """Exercise composite tree + abduction review notes."""
    pkg_dir = tmp_path / "abduction_demo"
    _write_abduction_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import (
        _format_warrant_tree,
        _review_notes,
        _strategy_by_id,
    )

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    knowledge_by_id = {k["id"]: k for k in ir["knowledges"]}
    sid_map = _strategy_by_id(ir)

    abduction_strats = [
        s for s in ir["strategies"] if s.get("sub_strategies") and s.get("type") == "abduction"
    ]
    assert abduction_strats

    # Exercise _format_warrant_tree on composite
    tree_lines = _format_warrant_tree(abduction_strats[0], knowledge_by_id, sid_map, indent=4)
    tree_text = "\n".join(tree_lines)
    assert "composite" in tree_text or "sub-strategies" in tree_text

    # Exercise _review_notes on abduction with wide priors (0.9 vs 0.5)
    notes = _review_notes(abduction_strats[0], sid_map)
    notes_text = "\n".join(notes)
    assert "gap=" in notes_text


def _write_abduction_close_priors_package(pkg_dir):
    """Abduction where support priors are close — triggers warning note."""
    name = "abd_close"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text("from .reasoning import *\n")
    (pkg_dir / name / "reasoning.py").write_text(
        "from gaia.lang import claim, support, compare, abduction\n\n"
        'obs = claim("Observed data.")\n'
        'hyp = claim("Hypothesis H predicts obs.")\n'
        'alt_pred = claim("Alternative predicts obs.")\n'
        'alt = claim("Alternative hypothesis.")\n'
        "s_h = support([hyp], obs, reason='H explains obs', prior=0.75)\n"
        "s_alt = support([alt], obs, reason='Alt explains obs', prior=0.7)\n"
        "cmp = compare(hyp, alt_pred, obs, reason='compare', prior=0.8)\n"
        "abd = abduction(s_h, s_alt, cmp, reason='IBE')\n"
    )
    (pkg_dir / name / "priors.py").write_text(
        "from . import obs, hyp, alt_pred, alt\n\n"
        "PRIORS = {\n"
        '    obs: (0.95, "Measured."),\n'
        '    hyp: (0.6, "Prior."),\n'
        '    alt_pred: (0.5, "Prior."),\n'
        '    alt: (0.55, "Prior."),\n'
        "}\n"
    )


def test_review_notes_abduction_close_priors(tmp_path):
    """Abduction with close priors triggers warning."""
    pkg_dir = tmp_path / "abd_close"
    _write_abduction_close_priors_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import _review_notes, _strategy_by_id

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    sid_map = _strategy_by_id(ir)
    abduction_strats = [
        s for s in ir["strategies"] if s.get("sub_strategies") and s.get("type") == "abduction"
    ]
    assert abduction_strats
    notes = _review_notes(abduction_strats[0], sid_map)
    notes_text = "\n".join(notes)
    assert "weak" in notes_text.lower() or "\u26a0" in notes_text


def test_review_notes_induction_consistent(tmp_path):
    """Induction with consistent priors shows consistent message."""
    pkg_dir = tmp_path / "induction_demo"
    _write_induction_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import _review_notes, _strategy_by_id

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    sid_map = _strategy_by_id(ir)
    induction_strats = [
        s for s in ir["strategies"] if s.get("sub_strategies") and s.get("type") == "induction"
    ]
    assert induction_strats

    found_note = False
    for ind in induction_strats:
        notes = _review_notes(ind, sid_map)
        if notes:
            found_note = True
    assert found_note


def _write_infer_package(pkg_dir):
    """Package with an infer strategy to exercise the leaf 'infer' path."""
    name = "infer_demo"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text("from .reasoning import *\n")
    (pkg_dir / name / "reasoning.py").write_text(
        "from gaia.lang import claim, infer\n\n"
        'premise_a = claim("Premise A.")\n'
        'premise_b = claim("Premise B.")\n'
        'conclusion = claim("Conclusion.")\n'
        "strat = infer([premise_a, premise_b], conclusion, reason='custom CPT')\n"
    )
    (pkg_dir / name / "priors.py").write_text(
        "from . import premise_a, premise_b, conclusion\n\n"
        "PRIORS = {\n"
        '    premise_a: (0.8, "Known."),\n'
        '    premise_b: (0.7, "Known."),\n'
        '    conclusion: (0.5, "To determine."),\n'
        "}\n"
    )


def test_brief_detail_infer_strategy(tmp_path):
    """Exercise the infer leaf strategy path."""
    pkg_dir = tmp_path / "infer_demo"
    _write_infer_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_detail

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_detail(ir, "conclusion")
    text = "\n".join(lines)

    assert "infer" in text
    assert "CPT" in text or "2^" in text


def _write_deduction_package(pkg_dir):
    """Package with a deduction (FormalStrategy) for warrant tree coverage."""
    name = "deduction_demo"
    _write_base_package(pkg_dir, name=name)
    (pkg_dir / name / "__init__.py").write_text("from .reasoning import *\n")
    (pkg_dir / name / "reasoning.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'axiom = claim("All men are mortal.")\n'
        'socrates = claim("Socrates is a man.")\n'
        'mortal = claim("Socrates is mortal.")\n'
        "strat = deduction([axiom, socrates], mortal,\n"
        "    reason='syllogism', prior=0.99)\n"
    )
    (pkg_dir / name / "priors.py").write_text(
        "from . import axiom, socrates\n\n"
        "PRIORS = {\n"
        '    axiom: (0.99, "Universal truth."),\n'
        '    socrates: (0.99, "Known fact."),\n'
        "}\n"
    )


def test_brief_detail_formal_strategy_warrant_tree(tmp_path):
    """Exercise FormalStrategy branch in warrant tree."""
    pkg_dir = tmp_path / "deduction_demo"
    _write_deduction_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_detail

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_detail(ir, "mortal")
    text = "\n".join(lines)

    assert "deduction" in text
    assert "syllogism" in text
    assert "0.99" in text

    formal_strats = [s for s in ir["strategies"] if s.get("formal_expr")]
    assert formal_strats


def test_dispatch_show_module_not_in_order(tmp_path):
    """dispatch_show falls back to modules_in_ir when module not in module_order."""
    pkg_dir = tmp_path / "brief_demo"
    _write_two_module_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import dispatch_show

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    # Clear module_order to force fallback path
    ir["module_order"] = []
    lines = dispatch_show(ir, "reasoning")
    text = "\n".join(lines)
    assert "expanded" in text


def test_overview_filters_sub_strategies_and_prefers_composite(tmp_path):
    """Overview deduplicates strategies — composites preferred over leaves."""
    pkg_dir = tmp_path / "induction_demo"
    _write_induction_package(pkg_dir)
    _compile(pkg_dir)

    from gaia.cli._packages import apply_package_priors, load_gaia_package
    from gaia.cli._packages import compile_loaded_package_artifact
    from gaia.cli.commands._brief import generate_brief_overview

    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()

    lines = generate_brief_overview(ir)
    text = "\n".join(lines)

    assert "induction" in text.lower()
    assert "law" in text
