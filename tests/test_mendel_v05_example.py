"""Regression tests for the v0.5 Mendel probability example package."""

from __future__ import annotations

import json
import shutil
import importlib.util
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

    association_parameters = probabilities.mendel_data_association_parameters()

    ir = json.loads((package / ".gaia" / "ir.json").read_text())
    knowledge_by_label = {item["label"]: item for item in ir["knowledges"] if item.get("label")}
    strategy_types = {item["type"] for item in ir["strategies"]}
    association = knowledge_by_label["mendel_data_association"]

    assert "infer" not in strategy_types
    assert "associate" in strategy_types
    assert "mendelian_segregation_model" in knowledge_by_label
    assert "blending_inheritance_model" in knowledge_by_label
    assert "f2_ratio_near_three_to_one" in knowledge_by_label
    assert association["metadata"]["helper_kind"] == "association"
    assert association["metadata"]["relation"]["p_a_given_b"] == pytest.approx(
        association_parameters.p_mendelian_given_ratio
    )
    assert association["metadata"]["relation"]["p_b_given_a"] == pytest.approx(
        association_parameters.p_ratio_given_mendelian
    )
    assert association["metadata"]["relation"]["prior_a"] == pytest.approx(
        association_parameters.prior_mendelian
    )
    assert association["metadata"]["relation"]["prior_b"] == pytest.approx(
        association_parameters.prior_ratio
    )

    _accept_all_reviews(package)

    infer_result = runner.invoke(app, ["infer", str(package)])
    assert infer_result.exit_code == 0, infer_result.output

    beliefs = _beliefs_by_label(package)

    assert beliefs["f2_ratio_near_three_to_one"] > association_parameters.prior_ratio
    assert beliefs["mendelian_segregation_model"] > association_parameters.prior_mendelian
    assert beliefs["blending_inheritance_model"] < 0.5
    assert beliefs["mendelian_segregation_model"] == pytest.approx(0.9994315850994945)
    assert beliefs["blending_inheritance_model"] == pytest.approx(0.00047284967827781446)
    assert beliefs["f2_count_observation"] == pytest.approx(0.87519129844639)
    assert beliefs["f2_ratio_near_three_to_one"] == pytest.approx(0.8942732068909091)
