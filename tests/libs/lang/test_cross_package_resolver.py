"""Tests for cross-package ref resolution."""

from pathlib import Path

import pytest

from libs.lang.loader import load_package
from libs.lang.models import Claim, Module, Package, Ref
from libs.lang.resolver import ResolveError, resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_resolve_intra_package_still_works():
    """Backward compat: single-package resolve without deps."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    ref = next(
        d for d in reasoning.knowledge if isinstance(d, Ref) and d.name == "heavier_falls_faster"
    )
    assert ref._resolved is not None
    assert ref._resolved.name == "heavier_falls_faster"


def test_cross_package_ref_resolves():
    """Newton refs to Galileo package exports should resolve when Galileo is provided as dep."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    implications = next(m for m in newton.loaded_modules if m.name == "implications")
    ref = next(
        d
        for d in implications.knowledge
        if isinstance(d, Ref) and d.name == "galileo_vacuum_prediction"
    )
    assert ref._resolved is not None
    assert ref._resolved.name == "vacuum_prediction"


def test_cross_package_exported_alias_resolves():
    """Dependency package exports may be Ref aliases, not only concrete declarations."""
    dep_module = Module(
        type="reasoning_module",
        name="core",
        knowledge=[
            Claim(type="claim", name="base", content="base claim"),
            Ref(name="public_alias", target="core.base"),
        ],
        export=["public_alias"],
    )
    dep_pkg = Package(
        name="dep_pkg",
        modules=["core"],
        export=["public_alias"],
        loaded_modules=[dep_module],
    )
    dep_pkg = resolve_refs(dep_pkg)

    consumer_module = Module(
        type="reasoning_module",
        name="consumer",
        knowledge=[Ref(name="use_alias", target="dep_pkg.public_alias")],
        export=[],
    )
    consumer_pkg = Package(
        name="consumer_pkg", modules=["consumer"], loaded_modules=[consumer_module]
    )
    consumer_pkg = resolve_refs(consumer_pkg, deps={"dep_pkg": dep_pkg})

    ref = next(d for d in consumer_module.knowledge if isinstance(d, Ref) and d.name == "use_alias")
    assert ref._resolved is not None
    assert ref._resolved.name == "base"


def test_multi_hop_alias_chain_resolves():
    """Ref chains should resolve transitively, not depend on declaration order."""
    mod = Module(
        type="reasoning_module",
        name="m",
        knowledge=[
            Ref(name="a", target="m.b"),
            Ref(name="b", target="m.c"),
            Ref(name="c", target="m.base"),
            Claim(type="claim", name="base", content="base claim"),
        ],
        export=["a", "b", "c", "base"],
    )
    pkg = Package(name="chain_pkg", modules=["m"], loaded_modules=[mod])
    resolved = resolve_refs(pkg)

    for name in ["a", "b", "c"]:
        ref = next(d for d in mod.knowledge if isinstance(d, Ref) and d.name == name)
        assert ref._resolved is not None
        assert ref._resolved.name == "base"
        assert resolved._index[f"m.{name}"].name == "base"


def test_cross_package_legacy_module_path_for_export_still_resolves():
    """Legacy pkg.module.name paths remain valid for package-exported names."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    mod = Module(
        type="reasoning_module",
        name="consumer",
        knowledge=[
            Ref(
                name="legacy_ref",
                target="galileo_falling_bodies.reasoning.vacuum_prediction",
            )
        ],
        export=[],
    )
    pkg = Package(name="consumer_pkg", modules=["consumer"], loaded_modules=[mod])
    pkg = resolve_refs(pkg, deps={"galileo_falling_bodies": galileo})

    ref = next(d for d in mod.knowledge if isinstance(d, Ref) and d.name == "legacy_ref")
    assert ref._resolved is not None
    assert ref._resolved.name == "vacuum_prediction"


def test_cross_package_ref_fails_without_dep():
    """Newton refs to Galileo fail if Galileo is not provided."""
    newton = load_package(NEWTON_DIR)
    with pytest.raises(ResolveError, match="galileo_falling_bodies"):
        resolve_refs(newton)


def test_transitive_deps_resolve():
    """Einstein refs to both Newton and Galileo should resolve."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    einstein = load_package(EINSTEIN_DIR)
    einstein = resolve_refs(
        einstein,
        deps={"newton_principia": newton, "galileo_falling_bodies": galileo},
    )

    prior_knowledge = next(m for m in einstein.loaded_modules if m.name == "prior_knowledge")
    ref = next(
        d for d in prior_knowledge.knowledge if isinstance(d, Ref) and d.name == "newton_gravity"
    )
    assert ref._resolved is not None
    assert ref._resolved.name == "law_of_gravity"


def test_dep_name_not_in_package_export_is_not_resolvable():
    """Cross-package visibility follows package export, not module export."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    # everyday_observation is module-exported in Galileo's aristotle module,
    # but it is not part of the package's public export surface.
    mod = Module(
        type="reasoning_module",
        name="test_mod",
        knowledge=[
            Ref(
                name="sneaky_ref",
                target="galileo_falling_bodies.everyday_observation",
            )
        ],
        export=[],
    )
    pkg = Package(name="test_pkg", type="test", modules=[], loaded_modules=[mod])

    with pytest.raises(ResolveError, match="sneaky_ref"):
        resolve_refs(pkg, deps={"galileo_falling_bodies": galileo})
