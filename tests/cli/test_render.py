"""Tests for gaia render command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_base_package(pkg_dir, *, name: str, version: str = "1.0.0") -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "{version}"\n'
        'description = "Test package."\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (pkg_dir / name).mkdir()


def _write_minimal_source(pkg_dir, name: str) -> None:
    (pkg_dir / name / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence_a = claim("Observed evidence A.")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "s = deduction(premises=[evidence_a, evidence_b], conclusion=hypothesis)\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "s"]\n'
    )


def _write_review(pkg_dir, package_name: str, review_name: str) -> None:
    reviews_dir = pkg_dir / package_name / "reviews"
    reviews_dir.mkdir(exist_ok=True)
    (reviews_dir / f"{review_name}.py").write_text(
        "from gaia.review import ReviewBundle, review_claim, review_strategy\n"
        "from .. import evidence_a, evidence_b, hypothesis, s\n\n"
        "REVIEW = ReviewBundle(\n"
        f'    source_id="{review_name}",\n'
        "    objects=[\n"
        '        review_claim(evidence_a, prior=0.9, judgment="strong", justification="Direct observation."),\n'
        '        review_claim(evidence_b, prior=0.8, judgment="supporting", justification="A second reinforcing observation."),\n'
        '        review_claim(hypothesis, prior=0.4, judgment="tentative", justification="Base rate before support."),\n'
        '        review_strategy(s, judgment="good", justification="The evidence usually supports the hypothesis."),\n'
        "    ],\n"
        ")\n"
    )


def _prepare_inferred_package(tmp_path, name: str = "render_demo"):
    """Create a package, write a review, compile and infer it. Returns pkg_dir."""
    pkg_dir = tmp_path / name
    _write_base_package(pkg_dir, name=name)
    _write_minimal_source(pkg_dir, name)
    _write_review(pkg_dir, name, "self_review")

    compile_result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert compile_result.exit_code == 0, compile_result.output
    infer_result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert infer_result.exit_code == 0, infer_result.output
    return pkg_dir


def test_render_target_all_writes_docs_and_github(tmp_path):
    """Happy path: render --target all (default) writes both docs and github outputs."""
    pkg_dir = _prepare_inferred_package(tmp_path)

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    docs_path = pkg_dir / "docs" / "detailed-reasoning.md"
    assert docs_path.exists(), "render should write docs/detailed-reasoning.md"
    content = docs_path.read_text()
    assert "# render_demo-gaia" in content or "# render_demo" in content

    github_dir = pkg_dir / ".github-output"
    assert (github_dir / "wiki" / "Home.md").exists()
    assert (github_dir / "manifest.json").exists()
    assert (github_dir / "docs" / "public" / "data" / "graph.json").exists()
    assert (github_dir / "README.md").exists()


def test_render_fails_when_ir_artifacts_missing(tmp_path):
    """render before compile → error about missing compiled artifacts."""
    pkg_dir = tmp_path / "no_compile"
    _write_base_package(pkg_dir, name="no_compile")
    _write_minimal_source(pkg_dir, "no_compile")
    _write_review(pkg_dir, "no_compile", "self_review")

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing compiled artifacts" in result.output


def test_render_fails_when_ir_stale(tmp_path):
    """render when source changed after compile → stale-artifact error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="stale_ir")

    # Mutate source so re-compile yields a different ir_hash
    (pkg_dir / "stale_ir" / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'evidence_a = claim("Observed evidence A (edited).")\n'
        'evidence_b = claim("Observed evidence B.")\n'
        'hypothesis = claim("Main hypothesis.")\n'
        "s = deduction(premises=[evidence_a, evidence_b], conclusion=hypothesis)\n"
        '__all__ = ["evidence_a", "evidence_b", "hypothesis", "s"]\n'
    )

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()


def test_render_target_github_fails_when_no_review_sidecar(tmp_path):
    """--target github hard-errors when no review.py / reviews/*.py exists."""
    pkg_dir = tmp_path / "no_review_gh"
    _write_base_package(pkg_dir, name="no_review_gh")
    _write_minimal_source(pkg_dir, "no_review_gh")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code != 0
    assert "review" in result.output.lower() or "inference" in result.output.lower()


def test_render_target_docs_succeeds_without_review_sidecar(tmp_path):
    """--target docs renders from compiled IR alone when no review sidecar exists."""
    pkg_dir = tmp_path / "no_review_docs"
    _write_base_package(pkg_dir, name="no_review_docs")
    _write_minimal_source(pkg_dir, "no_review_docs")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "warning" in result.output.lower()


def test_render_target_all_degrades_to_docs_without_review_sidecar(tmp_path):
    """--target all falls back to docs-only with a warning when no review sidecar."""
    pkg_dir = tmp_path / "no_review_all"
    _write_base_package(pkg_dir, name="no_review_all")
    _write_minimal_source(pkg_dir, "no_review_all")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert not (pkg_dir / ".github-output").exists()
    assert "skipping" in result.output.lower()


def test_render_target_github_fails_when_beliefs_missing(tmp_path):
    """--target github hard-errors when review exists but infer has not been run."""
    pkg_dir = tmp_path / "no_infer_gh"
    _write_base_package(pkg_dir, name="no_infer_gh")
    _write_minimal_source(pkg_dir, "no_infer_gh")
    _write_review(pkg_dir, "no_infer_gh", "self_review")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code != 0
    assert "inference" in result.output.lower() or "gaia infer" in result.output


def test_render_target_docs_warns_when_beliefs_missing(tmp_path):
    """--target docs renders docs with a warning when review exists but beliefs don't."""
    pkg_dir = tmp_path / "no_infer_docs"
    _write_base_package(pkg_dir, name="no_infer_docs")
    _write_minimal_source(pkg_dir, "no_infer_docs")
    _write_review(pkg_dir, "no_infer_docs", "self_review")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "warning" in result.output.lower()


def test_render_target_all_degrades_when_beliefs_missing(tmp_path):
    """--target all renders docs and skips github with a warning when beliefs missing."""
    pkg_dir = tmp_path / "no_infer_all"
    _write_base_package(pkg_dir, name="no_infer_all")
    _write_minimal_source(pkg_dir, "no_infer_all")
    _write_review(pkg_dir, "no_infer_all", "self_review")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert not (pkg_dir / ".github-output").exists()
    assert "skipping" in result.output.lower()


def test_render_fails_when_beliefs_stale(tmp_path):
    """render when beliefs.json has a wrong ir_hash → stale beliefs error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="stale_beliefs")
    beliefs_path = pkg_dir / ".gaia" / "reviews" / "self_review" / "beliefs.json"
    beliefs = json.loads(beliefs_path.read_text())
    beliefs["ir_hash"] = "not-the-real-hash"
    beliefs_path.write_text(json.dumps(beliefs))

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()
    assert "beliefs" in result.output.lower()


def test_render_fails_when_parameterization_stale(tmp_path):
    """render when parameterization.json has a wrong ir_hash → stale param error.

    beliefs.json is kept fresh to prove the parameterization check is
    independent: without it, a stale parameterization.json would silently
    feed old priors into the rendered output.
    """
    pkg_dir = _prepare_inferred_package(tmp_path, name="stale_param")
    param_path = pkg_dir / ".gaia" / "reviews" / "self_review" / "parameterization.json"
    param = json.loads(param_path.read_text())
    param["ir_hash"] = "not-the-real-hash"
    param_path.write_text(json.dumps(param))

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code != 0
    assert "stale" in result.output.lower()
    assert "parameterization" in result.output.lower()


def test_render_target_github_fails_when_parameterization_missing(tmp_path):
    """Regression for #398: --target github with beliefs but missing
    parameterization.json must error instead of silently using 0.5 defaults."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="missing_param")
    param_path = pkg_dir / ".gaia" / "reviews" / "self_review" / "parameterization.json"
    param_path.unlink()  # delete parameterization but keep beliefs

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code != 0, (
        f"Expected error when parameterization.json is missing but beliefs.json "
        f"is present. Without it, github output would show default 0.5 priors. "
        f"Got: {result.output}"
    )
    assert "parameterization" in result.output.lower()


def test_render_target_all_degrades_when_parameterization_missing(tmp_path):
    """--target all with beliefs but missing parameterization → skip github, render docs."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="missing_param_all")
    param_path = pkg_dir / ".gaia" / "reviews" / "self_review" / "parameterization.json"
    param_path.unlink()

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "parameterization" in result.output.lower()
    assert "skipping" in result.output.lower()


def _write_second_review(pkg_dir, package_name: str, review_name: str) -> None:
    reviews_dir = pkg_dir / package_name / "reviews"
    (reviews_dir / f"{review_name}.py").write_text(
        "from gaia.review import ReviewBundle, review_claim, review_strategy\n"
        "from .. import evidence_a, evidence_b, hypothesis, s\n\n"
        "REVIEW = ReviewBundle(\n"
        f'    source_id="{review_name}",\n'
        "    objects=[\n"
        '        review_claim(evidence_a, prior=0.5, judgment="tentative", justification="Alt."),\n'
        '        review_claim(evidence_b, prior=0.5, judgment="tentative", justification="Alt."),\n'
        '        review_claim(hypothesis, prior=0.5, judgment="tentative", justification="Alt."),\n'
        '        review_strategy(s, judgment="weak", justification="Alt."),\n'
        "    ],\n"
        ")\n"
    )


def test_render_target_all_degrades_when_multiple_reviews(tmp_path):
    """Two review sidecars + no --review + default target → docs rendered, github skipped.

    Accumulating an alternate/experimental review sidecar must not block the
    IR-only authoring workflow. Docs should still render from the compiled IR,
    with warnings pointing the user at `--review <name>` to unlock github.
    """
    pkg_dir = _prepare_inferred_package(tmp_path, name="multi_review_all")
    _write_second_review(pkg_dir, "multi_review_all", "alt_review")
    alt_infer = runner.invoke(app, ["infer", str(pkg_dir), "--review", "alt_review"])
    assert alt_infer.exit_code == 0, alt_infer.output

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert not (pkg_dir / ".github-output").exists()
    assert "multiple review sidecars" in result.output
    assert "--review <name>" in result.output


def test_render_target_docs_degrades_when_multiple_reviews(tmp_path):
    """Explicit --target docs + multiple reviews + no --review → warn and render."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="multi_review_docs")
    _write_second_review(pkg_dir, "multi_review_docs", "alt_review")
    alt_infer = runner.invoke(app, ["infer", str(pkg_dir), "--review", "alt_review"])
    assert alt_infer.exit_code == 0, alt_infer.output

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "multiple review sidecars" in result.output


def test_render_target_github_fails_when_multiple_reviews(tmp_path):
    """Explicit --target github + multiple reviews + no --review → hard error."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="multi_review_gh")
    _write_second_review(pkg_dir, "multi_review_gh", "alt_review")
    alt_infer = runner.invoke(app, ["infer", str(pkg_dir), "--review", "alt_review"])
    assert alt_infer.exit_code == 0, alt_infer.output

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code != 0
    assert "multiple review sidecars" in result.output


def test_render_target_docs_degrades_when_review_broken(tmp_path):
    """Broken review module (syntax error) → docs still renders with a warning.

    A malformed review.py must not block the IR-only docs workflow — render
    should fall back to no-beliefs rendering when the review module can't be
    imported. This is the second half of the ``--target docs`` contract.
    """
    pkg_dir = tmp_path / "broken_review_docs"
    _write_base_package(pkg_dir, name="broken_review_docs")
    _write_minimal_source(pkg_dir, "broken_review_docs")

    # Write a review that will fail to import cleanly (syntax error)
    reviews_dir = pkg_dir / "broken_review_docs" / "reviews"
    reviews_dir.mkdir()
    (reviews_dir / "broken.py").write_text("this is not valid python !!!\n")

    assert runner.invoke(app, ["compile", str(pkg_dir)]).exit_code == 0

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "could not load review sidecar" in result.output


def test_render_explicit_review_errors_when_unknown(tmp_path):
    """`--review NAME` with unknown name → always hard error, even for --target docs.

    When the user passes an explicit `--review` flag they are making a
    specific request; silently ignoring it and rendering without beliefs
    would be surprising and unsafe.
    """
    pkg_dir = _prepare_inferred_package(tmp_path, name="unknown_review")

    result = runner.invoke(
        app, ["render", str(pkg_dir), "--target", "docs", "--review", "does_not_exist"]
    )
    assert result.exit_code != 0
    assert "unknown review sidecar" in result.output
    # Docs should NOT be regenerated since the user's explicit request failed
    # (the file may exist from the _prepare_inferred_package setup... actually
    # _prepare_inferred_package does NOT run render, so the docs file should
    # not exist at all)
    assert not (pkg_dir / "docs" / "detailed-reasoning.md").exists()


def test_render_selects_named_review(tmp_path):
    """--review <name> selects that review's beliefs for rendering."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="named_review")
    _write_second_review(pkg_dir, "named_review", "alt_review")
    alt_infer = runner.invoke(app, ["infer", str(pkg_dir), "--review", "alt_review"])
    assert alt_infer.exit_code == 0, alt_infer.output

    result = runner.invoke(app, ["render", str(pkg_dir), "--review", "alt_review"])
    assert result.exit_code == 0, result.output
    assert "Review: alt_review" in result.output


def test_render_target_docs_only(tmp_path):
    """--target docs creates docs/detailed-reasoning.md but not .github-output/."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="docs_only")

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code == 0, result.output

    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert not (pkg_dir / ".github-output").exists()
    assert "Docs:" in result.output
    assert "GitHub:" not in result.output


def test_render_target_github_only(tmp_path):
    """--target github creates .github-output/ but not docs/detailed-reasoning.md."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="github_only")

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "github"])
    assert result.exit_code == 0, result.output

    assert (pkg_dir / ".github-output" / "manifest.json").exists()
    assert not (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert "GitHub:" in result.output
    assert "Docs:" not in result.output


def test_render_target_all_is_default(tmp_path):
    """Omitting --target is the same as --target all."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="all_default")

    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert (pkg_dir / "docs" / "detailed-reasoning.md").exists()
    assert (pkg_dir / ".github-output" / "manifest.json").exists()


def test_render_fails_when_review_sidecar_edited_after_infer(tmp_path):
    """Editing a review sidecar between `gaia infer` and `gaia render` must
    be detected. The IR hash is unchanged (review params are not part of IR),
    but the persisted `review_content_hash` in beliefs.json will mismatch the
    hash computed from the current sidecar — render must hard-error.

    Regression test for Codex adversarial review Finding 1 (high).
    """
    pkg_dir = _prepare_inferred_package(tmp_path, name="review_edit")

    # Sanity: baseline render succeeds (review unchanged since infer)
    baseline = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert baseline.exit_code == 0, baseline.output

    # Edit the review sidecar — change priors from the originals. This does
    # NOT touch the IR (priors are review-layer data, not IR structure).
    review_path = pkg_dir / "review_edit" / "reviews" / "self_review.py"
    original = review_path.read_text()
    # Originals are 0.9/0.8/0.4; bump each by +0.05 to produce a different content hash
    edited = (
        original.replace("prior=0.9", "prior=0.95")
        .replace("prior=0.8", "prior=0.85")
        .replace("prior=0.4", "prior=0.45")
    )
    assert edited != original, "fixture priors didn't match expected substrings"
    review_path.write_text(edited)

    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "docs"])
    assert result.exit_code != 0, (
        "render should have rejected the stale beliefs after review edit; "
        f"got exit={result.exit_code} output={result.output}"
    )
    assert "review" in result.output.lower()
    assert "changed" in result.output.lower() or "content_hash" in result.output.lower()
    assert "gaia infer" in result.output


def test_render_target_obsidian_writes_vault(tmp_path):
    """Obsidian target creates gaia-wiki/ with _index.md and module pages."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="obsidian_demo")
    result = runner.invoke(app, ["render", str(pkg_dir), "--target", "obsidian"])
    assert result.exit_code == 0, result.output
    wiki_dir = pkg_dir / "gaia-wiki"
    assert wiki_dir.is_dir()
    assert (wiki_dir / "_index.md").exists()
    assert (wiki_dir / "overview.md").exists()
    assert (wiki_dir / ".obsidian" / "graph.json").exists()
    assert "Obsidian:" in result.output


def test_render_target_all_does_not_include_obsidian(tmp_path):
    """Obsidian is opt-in — --target all should NOT create gaia-wiki/."""
    pkg_dir = _prepare_inferred_package(tmp_path, name="all_no_obsidian")
    result = runner.invoke(app, ["render", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    assert not (pkg_dir / "gaia-wiki").exists()
