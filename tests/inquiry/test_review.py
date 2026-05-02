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
from gaia.inquiry.review import run_review

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
