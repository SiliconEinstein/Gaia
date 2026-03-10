from pathlib import Path

import pytest

from libs.lang.loader import load_package
from libs.lang.models import Claim, Module, Package, Ref
from libs.lang.resolver import resolve_refs, ResolveError

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_resolve_simple_ref():
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    # reasoning module refs heavier_falls_faster from aristotle
    reasoning = next(m for m in resolved.loaded_modules if m.name == "reasoning")
    ref = next(
        d for d in reasoning.declarations if d.type == "ref" and d.name == "heavier_falls_faster"
    )
    assert ref._resolved is not None
    assert isinstance(ref._resolved, Claim)
    assert "重的物体" in ref._resolved.content


def test_resolve_all_refs():
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    # All refs should be resolved
    for module in resolved.loaded_modules:
        for decl in module.declarations:
            if decl.type == "ref":
                assert decl._resolved is not None, f"Unresolved ref: {module.name}.{decl.name}"


def test_resolve_cross_module():
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    follow_up = next(m for m in resolved.loaded_modules if m.name == "follow_up")
    vp_ref = next(d for d in follow_up.declarations if d.name == "vacuum_prediction")
    assert vp_ref._resolved is not None
    assert vp_ref._resolved.name == "vacuum_prediction"
    assert vp_ref._resolved.type == "claim"


def test_resolve_undefined_ref_raises():
    pkg = load_package(FIXTURE_DIR)
    # Add a bad ref
    from libs.lang.models import Ref

    bad_module = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    bad_module.declarations.append(Ref(name="nonexistent", target="fake_module.fake_name"))
    with pytest.raises(ResolveError, match="fake_module"):
        resolve_refs(pkg)


def test_build_declaration_index():
    """All declarations should be findable by module.name path."""
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    # Check that we can look up any exported declaration
    hff = resolved._index["aristotle.heavier_falls_faster"]
    assert hff.type == "claim"
    assert hff.prior == 0.7

    venv = resolved._index["setting.vacuum_env"]
    assert venv.type == "setting"

    vp = resolved._index["reasoning.vacuum_prediction"]
    assert vp.type == "claim"
    assert vp.prior == 0.5


# ── Inline tests (no galileo fixture) ─────────────────────────


def test_resolve_empty_package():
    """A package with no modules resolves without error."""
    pkg = Package(name="empty", modules=[])
    pkg.loaded_modules = []
    resolved = resolve_refs(pkg)
    assert resolved._index == {}


def test_resolve_ref_to_ref_raises():
    """A Ref targeting another Ref's path should raise ResolveError.

    Because Refs are skipped during index building, the target won't be found.
    """
    mod_a = Module(
        type="reasoning_module",
        name="a",
        declarations=[Ref(name="x", target="b.y")],
        export=["x"],
    )
    mod_b = Module(
        type="reasoning_module",
        name="b",
        declarations=[Ref(name="y", target="a.x")],
        export=["y"],
    )
    pkg = Package(name="circular_refs", modules=["a", "b"])
    pkg.loaded_modules = [mod_a, mod_b]

    with pytest.raises(ResolveError, match="target not found"):
        resolve_refs(pkg)
