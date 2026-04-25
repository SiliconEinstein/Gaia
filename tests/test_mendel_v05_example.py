"""Regression tests for the v0.5 Mendel probability example package."""

from __future__ import annotations

import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app


runner = CliRunner()


def _copy_mendel_example(tmp_path: Path) -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    source = repo_root / "examples" / "mendel-v0-5-gaia"
    assert source.exists(), "Mendel v0.5 example package is missing"
    package = tmp_path / "mendel-v0-5-gaia"
    shutil.copytree(source, package, ignore=shutil.ignore_patterns(".gaia", "__pycache__"))
    return package


def _accept_all_reviews(package: Path) -> None:
    from gaia.cli._packages import (
        apply_package_priors,
        compile_loaded_package_artifact,
        load_gaia_package,
    )
    from gaia.ir import ReviewManifest, ReviewStatus

    loaded = load_gaia_package(package)
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    assert compiled.review is not None
    accepted = [
        review.model_copy(update={"status": ReviewStatus.ACCEPTED, "round": 2})
        for review in compiled.review.reviews
    ]
    (package / ".gaia" / "review_manifest.json").write_text(
        json.dumps(ReviewManifest(reviews=accepted).model_dump(mode="json"), indent=2)
    )


def _beliefs_by_label(package: Path) -> dict[str | None, float]:
    beliefs = json.loads((package / ".gaia" / "beliefs.json").read_text())
    return {item["label"]: item["belief"] for item in beliefs["beliefs"]}


def _load_probability_module(package: Path):
    module_path = package / "src" / "mendel_v0_5" / "probabilities.py"
    spec = importlib.util.spec_from_file_location("mendel_v0_5_probabilities", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_mendel_fixture_models_competing_theories_with_association(tmp_path: Path):
    package = _copy_mendel_example(tmp_path)
    probabilities = _load_probability_module(package)

    compile_result = runner.invoke(app, ["compile", str(package)])
    assert compile_result.exit_code == 0, compile_result.output

    association_parameters = probabilities.mendel_count_association_parameters()

    ir = json.loads((package / ".gaia" / "ir.json").read_text())
    knowledge_by_label = {item["label"]: item for item in ir["knowledges"] if item.get("label")}
    strategy_types = {item["type"] for item in ir["strategies"]}
    association = knowledge_by_label["mendel_count_association"]

    # The package uses a single associate (Mendel ↔ count) and three qualitative
    # contradict edges against blending. It declares no `infer` strategy of its own.
    assert "infer" not in strategy_types
    assert "associate" in strategy_types

    # Core claims and observations are present.
    for label in (
        "mendelian_segregation_model",
        "blending_inheritance_model",
        "f1_uniform_dominant_observation",
        "f2_has_discrete_classes_observation",
        "f2_recessive_reappears_observation",
        "f2_count_observation",
        "mendel_predicts_f1_dominance",
        "mendel_predicts_discrete_classes",
        "mendel_predicts_recessive_reappearance",
        "mendel_predicts_three_to_one_ratio",
        "f2_dominant_count_specific",
        "f1_mendel_match",
        "f2_discrete_classes_mendel_match",
        "f2_reappearance_mendel_match",
        "blending_predicts_intermediate_f1",
        "blending_predicts_f2_continuous",
        "blending_predicts_no_recessive_reappearance",
        "f1_blending_conflict",
        "f2_discrete_classes_blending_conflict",
        "f2_reappearance_blending_conflict",
    ):
        assert label in knowledge_by_label, f"missing knowledge {label}"

    # The Mendel↔count associate uses the pointwise binomial PMF on one side and
    # the Bayes-consistent posterior on the other. All four numbers are fully
    # determined by ``MENDELIAN_DOMINANT_PROBABILITY`` and a uniform prior on p.
    assert association["metadata"]["helper_kind"] == "association"
    assert association["metadata"]["relation"]["p_a_given_b"] == pytest.approx(
        association_parameters.p_mendelian_given_count
    )
    assert association["metadata"]["relation"]["p_b_given_a"] == pytest.approx(
        association_parameters.p_count_given_mendelian
    )
    assert association["metadata"]["relation"]["prior_a"] == pytest.approx(
        association_parameters.prior_mendelian
    )
    assert association["metadata"]["relation"]["prior_b"] == pytest.approx(
        association_parameters.prior_count
    )

    # The diffuse alternative has the closed-form marginal 1/(N+1).
    assert association_parameters.p_count_given_diffuse == pytest.approx(1.0 / (295 + 100 + 1))
    # Sanity-check direction: a point likelihood peaked near the Mendelian mode
    # must beat a Uniform(p) reference measure at the same count.
    assert (
        association_parameters.p_count_given_mendelian
        > association_parameters.p_count_given_diffuse
    )

    _accept_all_reviews(package)

    infer_result = runner.invoke(app, ["infer", str(package)])
    assert infer_result.exit_code == 0, infer_result.output

    beliefs = _beliefs_by_label(package)

    # Directional belief checks: Mendel should rise above its prior and dominate
    # blending. We avoid hard-coded posterior values to stay robust to future
    # changes in the inference engine's numerical details.
    assert beliefs["mendelian_segregation_model"] > association_parameters.prior_mendelian
    assert beliefs["mendelian_segregation_model"] > 0.8
    assert beliefs["blending_inheritance_model"] < 0.2
    assert beliefs["mendelian_segregation_model"] > beliefs["blending_inheritance_model"]
    # The count observation's belief is driven upward by the associate and by
    # the prior we placed on it.
    assert beliefs["f2_count_observation"] > association_parameters.prior_count
