"""Tests for Language -> v2 storage model conversion."""

from pathlib import Path

from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_galileo_converts_to_v2():
    """Galileo package converts to v2 models with correct counts."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test-run")

    assert data.package.package_id == "galileo_falling_bodies"
    assert data.package.name == "galileo_falling_bodies"
    assert len(data.modules) == 5
    assert len(data.closures) > 0
    assert len(data.chains) > 0

    # Closure IDs should use / separator
    for c in data.closures:
        assert "/" in c.closure_id
        assert c.closure_id.startswith("galileo_falling_bodies/")

    # Chain IDs should use . separator
    for ch in data.chains:
        assert ch.chain_id.startswith("galileo_falling_bodies.")


def test_closure_dedup():
    """Same closure referenced from multiple modules should produce one Closure."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test")

    ids = [c.closure_id for c in data.closures]
    assert len(ids) == len(set(ids)), f"Duplicate closure IDs: {ids}"


def test_cross_package_refs_not_duplicated():
    """Newton referencing Galileo closures should not re-create them."""
    from cli.lang_to_v2 import convert_to_v2

    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)
    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    data = convert_to_v2(pkg=newton, review={}, beliefs={}, bp_run_id="test")

    # Newton closures should only include Newton's own declarations
    for c in data.closures:
        assert c.source_package_id == "newton_principia"


def test_beliefs_become_snapshots():
    """Belief values should become BeliefSnapshot records."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    beliefs = {"vacuum_prediction": 0.82, "heavier_falls_faster": 0.35}
    data = convert_to_v2(pkg=pkg, review={}, beliefs=beliefs, bp_run_id="test-run")

    snapshots_by_name = {s.closure_id.split("/")[1]: s for s in data.belief_snapshots}
    assert snapshots_by_name["vacuum_prediction"].belief == 0.82
    assert snapshots_by_name["heavier_falls_faster"].belief == 0.35
