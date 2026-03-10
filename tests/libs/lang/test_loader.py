# tests/libs/lang/test_loader.py
from pathlib import Path

from libs.lang.loader import load_package
from libs.lang.models import (
    Claim,
    InferAction,
    ChainExpr,
    Ref,
)

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages" / "galileo_falling_bodies"


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
    counts: dict[str, int] = {}
    for decl in reasoning.declarations:
        counts[decl.type] = counts.get(decl.type, 0) + 1

    # The richer Galileo fixture should contain:
    # 4 refs, 4 reusable infer actions, 9 explicit claims, 8 chain expressions,
    # 1 contradiction relation, 1 retract_action.
    assert counts == {
        "ref": 4,
        "infer_action": 4,
        "claim": 9,
        "chain_expr": 8,
        "contradiction": 1,
        "retract_action": 1,
    }


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
    synthesize = next(
        d for d in reasoning.declarations if d.name == "synthesize_equal_fall_prediction"
    )
    assert isinstance(synthesize, InferAction)
    assert len(synthesize.params) == 4
    assert [p.name for p in synthesize.params] == ["verdict", "confound", "support", "env"]
    assert synthesize.return_type == "claim"
    assert "{env}" in synthesize.content


def test_chain_expr_steps():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    chain = next(d for d in reasoning.declarations if d.name == "contradiction_chain")
    assert isinstance(chain, ChainExpr)
    assert len(chain.steps) == 3
    # After refactoring, contradiction_chain has no edge_type (defaults to deduction)
    assert chain.edge_type is None
    # Step 1: ref
    assert chain.steps[0].ref == "tied_pair_slower_than_heavy"
    # Step 2: apply with args
    assert chain.steps[1].apply == "expose_mutual_exclusion"
    assert chain.steps[1].args[0].dependency == "direct"
    assert chain.steps[1].args[1].dependency == "direct"
    # Step 3: ref
    assert chain.steps[2].ref == "tied_balls_contradiction"


def test_ref_declaration():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    ref = next(d for d in reasoning.declarations if d.name == "heavier_falls_faster")
    assert isinstance(ref, Ref)
    assert ref.target == "aristotle.heavier_falls_faster"


def test_lambda_step():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    combined = next(d for d in reasoning.declarations if d.name == "combined_weight_chain")
    assert isinstance(combined, ChainExpr)
    # Step 2 should be a lambda
    step2 = combined.steps[1]
    assert hasattr(step2, "lambda_")
    assert "复合体 HL 总重量大于单独的重球 H" in step2.lambda_


def test_exports():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    assert {
        "tied_balls_contradiction",
        "aristotle_contradicted",
        "air_resistance_is_confound",
        "inclined_plane_supports_equal_fall",
        "vacuum_prediction",
    }.issubset(set(reasoning.export))


def test_load_nonexistent_raises():
    import pytest

    with pytest.raises(FileNotFoundError):
        load_package(Path("/nonexistent/path"))


# ── Inline / tmp_path tests (no galileo fixture) ──────────────


def test_load_missing_module_file(tmp_path):
    """package.yaml references module 'foo' but foo.yaml does not exist."""
    import pytest

    pkg_yaml = tmp_path / "package.yaml"
    pkg_yaml.write_text("name: test_pkg\nmodules:\n  - foo\n")

    with pytest.raises(FileNotFoundError, match="foo.yaml"):
        load_package(tmp_path)


def test_unknown_step_format_raises(tmp_path):
    """A chain step with neither ref/apply/lambda should raise ValueError."""
    import pytest

    pkg_yaml = tmp_path / "package.yaml"
    pkg_yaml.write_text("name: test_pkg\nmodules:\n  - m\n")

    mod_yaml = tmp_path / "m.yaml"
    mod_yaml.write_text(
        "type: reasoning_module\n"
        "name: m\n"
        "declarations:\n"
        "  - type: chain_expr\n"
        "    name: bad_chain\n"
        "    steps:\n"
        "      - step: 1\n"
        "        unknown_key: oops\n"
        "export: []\n"
    )

    with pytest.raises(ValueError, match="Unknown step format"):
        load_package(tmp_path)


def test_unknown_type_falls_back_to_declaration(tmp_path):
    """A declaration with an unrecognized type falls back to base Declaration."""
    pkg_yaml = tmp_path / "package.yaml"
    pkg_yaml.write_text("name: test_pkg\nmodules:\n  - m\n")

    mod_yaml = tmp_path / "m.yaml"
    mod_yaml.write_text(
        "type: reasoning_module\n"
        "name: m\n"
        "declarations:\n"
        "  - type: custom_type\n"
        "    name: my_custom\n"
        "export: []\n"
    )

    pkg = load_package(tmp_path)
    mod = pkg.loaded_modules[0]
    assert len(mod.declarations) == 1
    decl = mod.declarations[0]
    # Should be a base Declaration (not a specific subclass like Claim)
    assert type(decl).__name__ == "Declaration"
    assert decl.type == "custom_type"
    assert decl.name == "my_custom"


def test_load_minimal_package(tmp_path):
    """A minimal package with one empty module loads successfully."""
    pkg_yaml = tmp_path / "package.yaml"
    pkg_yaml.write_text("name: minimal\nmodules:\n  - m\n")

    mod_yaml = tmp_path / "m.yaml"
    mod_yaml.write_text("type: reasoning_module\nname: m\ndeclarations: []\nexport: []\n")

    pkg = load_package(tmp_path)
    assert pkg.name == "minimal"
    assert len(pkg.loaded_modules) == 1
    assert pkg.loaded_modules[0].name == "m"
    assert pkg.loaded_modules[0].declarations == []
    assert pkg.loaded_modules[0].export == []


def test_load_package_with_dependencies(tmp_path):
    """Dependencies in package.yaml are parsed."""
    pkg_yaml = tmp_path / "package.yaml"
    pkg_yaml.write_text(
        "name: dep_test\n"
        "modules: []\n"
        "dependencies:\n"
        "  - package: physics_base\n"
        '    version: ">=1.0.0"\n'
        "  - package: math_utils\n"
    )
    pkg = load_package(tmp_path)
    assert len(pkg.dependencies) == 2
    assert pkg.dependencies[0].package == "physics_base"
    assert pkg.dependencies[0].version == ">=1.0.0"
    assert pkg.dependencies[1].package == "math_utils"
    assert pkg.dependencies[1].version is None
