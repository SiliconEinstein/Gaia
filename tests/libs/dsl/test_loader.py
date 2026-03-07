# tests/libs/dsl/test_loader.py
from pathlib import Path

from libs.dsl.loader import load_package
from libs.dsl.models import (
    Claim,
    InferAction,
    ChainExpr,
    Ref,
)

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_load_package_metadata():
    pkg = load_package(FIXTURE_DIR)
    assert pkg.name == "galileo_falling_bodies"
    assert pkg.version == "1.0.0"
    assert pkg.manifest is not None
    assert "伽利略" in pkg.manifest.authors[0]


def test_load_package_modules():
    pkg = load_package(FIXTURE_DIR)
    assert len(pkg.loaded_modules) == 5
    names = {m.name for m in pkg.loaded_modules}
    assert names == {"motivation", "setting", "aristotle", "reasoning", "follow_up"}


def test_module_types():
    pkg = load_package(FIXTURE_DIR)
    type_map = {m.name: m.type for m in pkg.loaded_modules}
    assert type_map["motivation"] == "motivation_module"
    assert type_map["setting"] == "setting_module"
    assert type_map["reasoning"] == "reasoning_module"
    assert type_map["follow_up"] == "follow_up_module"


def test_declarations_parsed():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    # Should have: 3 refs + 2 infer_actions + 3 claims + 3 chain_exprs = 11
    assert len(reasoning.declarations) == 11


def test_claim_with_prior():
    pkg = load_package(FIXTURE_DIR)
    aristotle = next(m for m in pkg.loaded_modules if m.name == "aristotle")
    heavier = next(d for d in aristotle.declarations if d.name == "heavier_falls_faster")
    assert isinstance(heavier, Claim)
    assert heavier.prior == 0.7
    assert "重的物体" in heavier.content


def test_infer_action_with_params():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    reductio = next(d for d in reasoning.declarations if d.name == "reductio_ad_absurdum")
    assert isinstance(reductio, InferAction)
    assert len(reductio.params) == 2
    assert reductio.params[0].name == "hypothesis"
    assert reductio.return_type == "claim"
    assert "{hypothesis}" in reductio.content


def test_chain_expr_steps():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    chain = next(d for d in reasoning.declarations if d.name == "refutation_chain")
    assert isinstance(chain, ChainExpr)
    assert len(chain.steps) == 3
    # Step 1: ref
    assert chain.steps[0].ref == "heavier_falls_faster"
    # Step 2: apply with args
    assert chain.steps[1].apply == "reductio_ad_absurdum"
    assert chain.steps[1].args[0].dependency == "direct"
    # Step 3: ref
    assert chain.steps[2].ref == "aristotle_contradicted"


def test_ref_declaration():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    ref = next(d for d in reasoning.declarations if d.name == "heavier_falls_faster")
    assert isinstance(ref, Ref)
    assert ref.target == "aristotle.heavier_falls_faster"


def test_lambda_step():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    confound = next(d for d in reasoning.declarations if d.name == "confound_chain")
    assert isinstance(confound, ChainExpr)
    # Step 2 should be a lambda
    step2 = confound.steps[1]
    assert hasattr(step2, "lambda_")
    assert "空气阻力" in step2.lambda_


def test_exports():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    assert "vacuum_prediction" in reasoning.export


def test_load_nonexistent_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_package(Path("/nonexistent/path"))
