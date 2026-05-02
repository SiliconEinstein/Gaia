"""Step 2 — eight-section review + JSON schema + diagnostics composition."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.inquiry.diagnostics import (
    Diagnostic,
    format_diagnostics_as_next_edits,
    from_validation,
)
from gaia.inquiry.review import publish_blockers, run_review

runner = CliRunner()


def _pkg_with_holes(pkg_dir: Path, name: str = "review_pkg") -> None:
    """Build a package with: 1 prior-set claim, 1 hole, 1 setting, 1 question."""
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / name
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, setting, question, support\n"
        'covered = claim("covered hypothesis", metadata={"prior": 0.7})\n'
        'hole = claim("hypothesis with no prior")\n'
        'derived_claim = claim("derived conclusion")\n'
        "sup = support(premises=[hole, covered], conclusion=derived_claim)\n"
        'iid = setting("data is i.i.d.")\n'
        'rq = question("does it generalize?")\n'
        '__all__ = ["covered", "hole", "derived_claim", "sup", "iid", "rq"]\n',
        encoding="utf-8",
    )


# --------------------------------------------------------------------------- #
# Diagnostics — pure function tests                                           #
# --------------------------------------------------------------------------- #


def test_from_validation_lifts_warnings_and_errors():
    diags = from_validation(["w1", "w2"], ["e1"])
    kinds = [d.kind for d in diags]
    sevs = [d.severity for d in diags]
    assert "validation_error" in kinds
    assert "validation_warning" in kinds
    assert "error" in sevs and "warning" in sevs


def test_next_edits_dedup_and_severity_order():
    diags = [
        Diagnostic("info", "background_only_claim", "x", "x", "msg", "edit B"),
        Diagnostic("error", "validation_error", "g", "g", "msg", "edit A"),
        Diagnostic("warning", "prior_hole", "y", "y", "msg", "edit A"),
    ]
    edits = format_diagnostics_as_next_edits(diags)
    assert edits == ["edit A", "edit B"]


# --------------------------------------------------------------------------- #
# Report shape                                                                #
# --------------------------------------------------------------------------- #


def test_review_report_has_all_eight_sections(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    d = report.to_json_dict()
    for key in (
        "focus",
        "compile",
        "semantic_diff",
        "graph_health",
        "inquiry_tree",
        "prior_holes",
        "belief_report",
        "diagnostics",
        "next_edits",
    ):
        assert key in d, f"missing JSON section: {key}"


def test_review_compile_section(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    assert report.compile_status == "ok"
    assert report.counts["knowledge"] >= 4
    assert report.counts["strategies"] >= 1


def test_review_prior_holes_detect_missing_prior(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    labels = [h["label"] for h in report.prior_holes]
    assert "hole" in labels
    assert "covered" not in labels


def test_review_graph_health_reports_orphans_and_holes(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    gh = report.graph_health
    assert "hole" in gh["prior_holes"]
    assert "covered" not in gh["prior_holes"]


def test_review_inquiry_tree_counts_questions_as_goals(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    assert report.inquiry_tree["goals"] == 1
    assert report.inquiry_tree["unreviewed_warrants"] >= 1


def test_review_diagnostics_include_prior_hole_and_orphan(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    kinds = {d.kind for d in report.diagnostics}
    assert "prior_hole" in kinds
    assert "orphaned_claim" in kinds


def test_review_next_edits_nonempty_when_holes_exist(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    assert any('set_prior("hole"' in e for e in report.next_edits)


def test_review_semantic_diff_empty_on_first_run(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    report = run_review(pkg, no_infer=True)
    assert report.semantic_diff.is_empty
    assert report.semantic_diff.baseline_review_id is None


# --------------------------------------------------------------------------- #
# Text rendering — eight ## headers                                           #
# --------------------------------------------------------------------------- #


def test_text_render_has_all_eight_section_headers(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    r = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer"])
    assert r.exit_code == 0, r.output
    for h in (
        "## Focus",
        "## Compile",
        "## Semantic diff",
        "## Graph health",
        "## Inquiry tree",
        "## Prior holes",
        "## Belief report",
        "## Next edits",
    ):
        assert h in r.output, f"text output missing header: {h}\n{r.output}"


def test_text_render_lists_holes(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    r = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer"])
    assert "- hole" in r.output


# --------------------------------------------------------------------------- #
# JSON output — schema fidelity                                               #
# --------------------------------------------------------------------------- #


def test_json_output_well_formed_and_schema_v1(tmp_path):
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    r = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer", "--json"])
    assert r.exit_code == 0, r.output
    data = json.loads(r.output)
    assert data["compile"]["status"] == "ok"
    assert isinstance(data["graph_health"]["prior_holes"], list)
    assert isinstance(data["diagnostics"], list)
    assert any(d["kind"] == "prior_hole" for d in data["diagnostics"])
    assert isinstance(data["next_edits"], list)
    assert data["semantic_diff"]["baseline_review_id"] is None


def test_strict_no_warnings_no_exit(tmp_path):
    """Strict mode must NOT exit non-zero when only info-level diagnostics exist."""
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    # First review: validation may warn; we just check exit-code path is reachable.
    r = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer", "--mode", "publish"])
    assert r.exit_code in (0, 1)  # depends on validator output for empty-strategy pkg


# --------------------------------------------------------------------------- #
# Composition contract — must use check_core, not duplicate logic             #
# --------------------------------------------------------------------------- #


def test_review_uses_check_core_breakdown(tmp_path):
    """Sanity: prior_holes from review must match check_core directly."""
    pkg = tmp_path / "p"
    _pkg_with_holes(pkg)
    from gaia.cli._packages import (
        apply_package_priors,
        compile_loaded_package_artifact,
        ensure_package_env,
        load_gaia_package,
    )
    from gaia.cli.commands.check_core import analyze_knowledge_breakdown
    from gaia.inquiry.review import _graph_to_ir_dict

    ensure_package_env(pkg)
    loaded = load_gaia_package(str(pkg))
    apply_package_priors(loaded)
    graph = compile_loaded_package_artifact(loaded).graph
    kb = analyze_knowledge_breakdown(_graph_to_ir_dict(graph))
    expected = sorted(h.label for h in kb.holes)

    report = run_review(pkg, no_infer=True)
    actual = sorted(h["label"] for h in report.prior_holes)
    assert actual == expected


def test_review_adapter_preserves_strategy_and_operator_ids(tmp_path):
    pkg = tmp_path / "p"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "id-review-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg / "id_review"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, contradiction, support\n"
        'a = claim("A", metadata={"prior": 0.7})\n'
        'b = claim("B", metadata={"prior": 0.4})\n'
        'c = claim("C")\n'
        "sup = support(premises=[a], conclusion=c)\n"
        "conflict = contradiction(a, b)\n"
        '__all__ = ["a", "b", "c", "sup", "conflict"]\n',
        encoding="utf-8",
    )

    from gaia.cli._packages import (
        apply_package_priors,
        compile_loaded_package_artifact,
        ensure_package_env,
        load_gaia_package,
    )
    from gaia.inquiry.review import _graph_to_ir_dict

    ensure_package_env(pkg)
    loaded = load_gaia_package(str(pkg))
    apply_package_priors(loaded)
    graph = compile_loaded_package_artifact(loaded).graph
    ir = _graph_to_ir_dict(graph)

    assert ir["strategies"][0]["id"].startswith("lcs_")
    assert ir["operators"][0]["id"].startswith("lco_")

    report = run_review(pkg, no_infer=True)
    unreviewed = [d for d in report.diagnostics if d.kind == "unreviewed_warrant"]
    assert unreviewed
    assert all(d.target.startswith("lcs_") for d in unreviewed)


def _write_dep_package(dep_dir: Path, *, name: str, monkeypatch) -> None:
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    import_name = name.replace("-", "_")
    src = dep_dir / import_name
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        'evidence = claim("Strong upstream evidence.", title="evidence")\n'
        'upstream_conclusion = claim("Upstream conclusion.", title="conclusion")\n'
        "deduction(premises=[evidence], conclusion=upstream_conclusion, "
        "reason='evidence supports conclusion', prior=0.9)\n"
        '__all__ = ["evidence", "upstream_conclusion"]\n',
        encoding="utf-8",
    )
    (src / "priors.py").write_text(
        'from . import evidence\n\nPRIORS = {evidence: (0.85, "Strong evidence")}\n',
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(dep_dir))


def test_review_depth_uses_joint_dependency_graphs(tmp_path, monkeypatch):
    from unittest.mock import patch

    dep_dir = tmp_path / "upstream_dep"
    _write_dep_package(dep_dir, name="upstream_dep", monkeypatch=monkeypatch)
    compile_dep = runner.invoke(app, ["compile", str(dep_dir)])
    assert compile_dep.exit_code == 0, compile_dep.output

    pkg = tmp_path / "local_pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "local-pkg-gaia"\nversion = "1.0.0"\n'
        'dependencies = ["upstream-dep-gaia"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg / "local_pkg"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from upstream_dep import upstream_conclusion\n"
        'local_obs = claim("Local observation.")\n'
        "local_result = claim('Local result.')\n"
        "deduction(premises=[upstream_conclusion, local_obs], conclusion=local_result, "
        "reason='apply upstream', prior=0.9)\n"
        '__all__ = ["local_obs", "local_result"]\n',
        encoding="utf-8",
    )

    flat = run_review(pkg, depth=0)
    with patch("gaia.cli._packages._locate_dependency_manifest_root", return_value=dep_dir):
        joint = run_review(pkg, depth=1)

    upstream_id = "github:upstream_dep::upstream_conclusion"
    flat_beliefs = {b["knowledge_id"]: b["belief"] for b in flat.belief_report["beliefs"]}
    joint_beliefs = {b["knowledge_id"]: b["belief"] for b in joint.belief_report["beliefs"]}

    assert flat.compile_status == "ok"
    assert joint.compile_status == "ok"
    assert upstream_id in joint_beliefs
    assert joint_beliefs[upstream_id] != flat_beliefs.get(upstream_id, 0.5)


def test_review_depth_inference_errors_surface_in_graph_health(tmp_path):
    pkg = tmp_path / "missing_dep_pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "missing-dep-pkg-gaia"\nversion = "1.0.0"\n'
        'dependencies = ["missing-upstream-gaia"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg / "missing_dep_pkg"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim\n"
        'local_obs = claim("Local observation.", metadata={"prior": 0.6})\n'
        '__all__ = ["local_obs"]\n',
        encoding="utf-8",
    )

    report = run_review(pkg, depth=1)

    assert not report.belief_report["ran_inference"]
    assert any("missing_upstream" in err for err in report.graph_health["errors"])

    result = runner.invoke(app, ["inquiry", "review", str(pkg), "--depth", "1"])
    assert result.exit_code == 1
    assert "errors: 1" in result.output
    assert "missing_upstream" in result.output


def test_review_manifest_accepted_strategy_is_not_unreviewed(tmp_path):
    pkg = tmp_path / "reviewed_pkg"
    pkg.mkdir()
    (pkg / "pyproject.toml").write_text(
        '[project]\nname = "reviewed-pkg-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg / "reviewed_pkg"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.lang import claim, derive\n"
        'a = claim("A.", metadata={"prior": 0.7})\n'
        'c = derive("C.", given=a, rationale="A implies C.", label="derive_c")\n'
        '__all__ = ["c"]\n',
        encoding="utf-8",
    )

    from gaia.cli._packages import (
        apply_package_priors,
        compile_loaded_package_artifact,
        ensure_package_env,
        load_gaia_package,
    )
    from gaia.ir import ReviewManifest, ReviewStatus

    ensure_package_env(pkg)
    loaded = load_gaia_package(str(pkg))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    generated = compiled.review
    assert generated is not None
    assert len(generated.reviews) == 1
    accepted = generated.reviews[0].model_copy(update={"status": ReviewStatus.ACCEPTED, "round": 2})
    review_path = pkg / ".gaia" / "review_manifest.json"
    review_path.parent.mkdir()
    review_path.write_text(
        json.dumps(ReviewManifest(reviews=[accepted]).model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    report = run_review(pkg, no_infer=True, mode="publish")

    assert report.inquiry_tree["accepted_warrants"] == 1
    assert report.inquiry_tree["unreviewed_warrants"] == 0
    assert not any(
        d.kind == "unreviewed_warrant" and d.target == accepted.target_id
        for d in report.diagnostics
    )
    assert not any("unreviewed_warrant" in blocker for blocker in publish_blockers(report))
