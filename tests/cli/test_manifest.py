"""Tests for build manifest serialization."""

from pathlib import Path

from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"


def test_manifest_roundtrip(tmp_path):
    """Serialize a resolved package to manifest.json and deserialize it back."""
    from cli.manifest import deserialize_package, save_manifest

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    manifest_path = save_manifest(pkg, tmp_path)
    assert manifest_path.exists()
    assert manifest_path.name == "manifest.json"

    restored = deserialize_package(manifest_path)
    assert restored.name == pkg.name
    assert len(restored.loaded_modules) == len(pkg.loaded_modules)

    # Check that knowledge objects survived
    reasoning = next(m for m in restored.loaded_modules if m.name == "reasoning")
    claims = [d for d in reasoning.knowledge if d.type == "claim"]
    assert len(claims) > 0


def test_manifest_preserves_resolution_index(tmp_path):
    """Resolution index should allow Ref._resolved to be rebuilt."""
    from cli.manifest import deserialize_package, save_manifest
    from libs.lang.models import Ref

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    save_manifest(pkg, tmp_path)
    restored = deserialize_package(tmp_path / "manifest.json")

    # Check that _index was rebuilt
    assert len(restored._index) > 0

    # Check a specific Ref has _resolved rebuilt
    reasoning = next(m for m in restored.loaded_modules if m.name == "reasoning")
    ref = next(
        d for d in reasoning.knowledge if isinstance(d, Ref) and d.name == "heavier_falls_faster"
    )
    assert ref._resolved is not None
    assert ref._resolved.name == "heavier_falls_faster"


def test_manifest_preserves_all_knowledge_types(tmp_path):
    """All knowledge subtypes should survive roundtrip with their specific fields."""
    from cli.manifest import deserialize_package, save_manifest
    from libs.lang.models import (
        ChainExpr,
        Claim,
        Contradiction,
        InferAction,
        Question,
        Ref,
        RetractAction,
        Setting,
    )

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    save_manifest(pkg, tmp_path)
    restored = deserialize_package(tmp_path / "manifest.json")

    # Gather all knowledge objects across all modules
    all_knowledge = [k for m in restored.loaded_modules for k in m.knowledge]
    type_set = {type(k) for k in all_knowledge}

    # The galileo package exercises these types
    assert Claim in type_set
    assert Setting in type_set
    assert Question in type_set
    assert Ref in type_set
    assert ChainExpr in type_set
    assert InferAction in type_set
    assert RetractAction in type_set
    assert Contradiction in type_set

    # Check that subclass-specific fields are preserved
    reasoning = next(m for m in restored.loaded_modules if m.name == "reasoning")

    # Claim with content
    vp = next(k for k in reasoning.knowledge if k.name == "vacuum_prediction")
    assert isinstance(vp, Claim)
    assert "真空" in vp.content

    # Contradiction with between
    contra = next(k for k in reasoning.knowledge if k.name == "tied_balls_contradiction")
    assert isinstance(contra, Contradiction)
    assert len(contra.between) == 2

    # ChainExpr with steps
    chain = next(k for k in reasoning.knowledge if k.name == "drag_prediction_chain")
    assert isinstance(chain, ChainExpr)
    assert len(chain.steps) > 0

    # InferAction with params
    action = next(k for k in reasoning.knowledge if k.name == "deduce_drag_effect")
    assert isinstance(action, InferAction)
    assert len(action.params) > 0

    # RetractAction with target and reason
    retract = next(k for k in reasoning.knowledge if k.name == "retract_aristotle")
    assert isinstance(retract, RetractAction)
    assert retract.target == "heavier_falls_faster"
    assert retract.reason == "tied_balls_contradiction"


def test_manifest_preserves_step_types(tmp_path):
    """StepRef, StepApply, and StepLambda should all survive roundtrip."""
    from cli.manifest import deserialize_package, save_manifest
    from libs.lang.models import ChainExpr, StepApply, StepLambda, StepRef

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    save_manifest(pkg, tmp_path)
    restored = deserialize_package(tmp_path / "manifest.json")

    reasoning = next(m for m in restored.loaded_modules if m.name == "reasoning")
    drag_chain = next(k for k in reasoning.knowledge if k.name == "drag_prediction_chain")
    assert isinstance(drag_chain, ChainExpr)

    step_types = {type(s) for s in drag_chain.steps}
    assert StepRef in step_types
    assert StepApply in step_types

    # combined_weight_chain has a StepLambda
    cw_chain = next(k for k in reasoning.knowledge if k.name == "combined_weight_chain")
    assert isinstance(cw_chain, ChainExpr)
    lambda_steps = [s for s in cw_chain.steps if isinstance(s, StepLambda)]
    assert len(lambda_steps) > 0
    assert lambda_steps[0].lambda_ != ""


def test_manifest_preserves_package_metadata(tmp_path):
    """Package-level fields (version, manifest, export) should survive."""
    from cli.manifest import deserialize_package, save_manifest

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    save_manifest(pkg, tmp_path)
    restored = deserialize_package(tmp_path / "manifest.json")

    assert restored.version == pkg.version
    assert restored.export == pkg.export
    assert restored.manifest is not None
    assert restored.manifest.description == pkg.manifest.description
    assert restored.manifest.authors == pkg.manifest.authors
    assert restored.modules_list == pkg.modules_list
