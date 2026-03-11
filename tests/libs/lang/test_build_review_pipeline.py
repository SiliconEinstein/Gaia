"""Integration test: elaborate + build + compile for all three packages."""

from pathlib import Path

from libs.lang.build_store import save_build
from libs.lang.compiler import compile_factor_graph
from libs.lang.elaborator import elaborate_package
from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_galileo_elaborate_and_build(tmp_path):
    """Galileo package can be elaborated and built."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)

    assert len(elaborated.prompts) >= 10
    assert len(elaborated.chain_contexts) >= 5

    build_dir = tmp_path / "build"
    save_build(elaborated, build_dir)
    assert (build_dir / "package.md").exists()
    content = (build_dir / "package.md").read_text()
    assert "galileo_falling_bodies" in content


def test_newton_elaborate_and_build(tmp_path):
    """Newton (with Galileo dep) can be elaborated and built."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})
    elaborated = elaborate_package(newton)

    assert len(elaborated.prompts) >= 4
    assert len(elaborated.chain_contexts) >= 4

    build_dir = tmp_path / "build"
    save_build(elaborated, build_dir)
    assert (build_dir / "package.md").exists()
    content = (build_dir / "package.md").read_text()
    assert "newton_principia" in content


def test_einstein_elaborate_and_build(tmp_path):
    """Einstein (with Newton + Galileo deps) can be elaborated and built."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    einstein = load_package(EINSTEIN_DIR)
    einstein = resolve_refs(
        einstein,
        deps={"newton_principia": newton, "galileo_falling_bodies": galileo},
    )
    elaborated = elaborate_package(einstein)

    assert len(elaborated.prompts) >= 8
    assert len(elaborated.chain_contexts) >= 7

    build_dir = tmp_path / "build"
    save_build(elaborated, build_dir)
    assert (build_dir / "package.md").exists()
    content = (build_dir / "package.md").read_text()
    assert "einstein_gravity" in content


def test_all_three_compile_factor_graphs():
    """All three packages compile valid factor graphs with expected sizes."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    einstein = load_package(EINSTEIN_DIR)
    einstein = resolve_refs(
        einstein,
        deps={"newton_principia": newton, "galileo_falling_bodies": galileo},
    )

    fg_g = compile_factor_graph(galileo)
    fg_n = compile_factor_graph(newton)
    fg_e = compile_factor_graph(einstein)

    # Galileo: 14 variables, 11 factors
    assert len(fg_g.variables) == 14
    assert len(fg_g.factors) == 11

    # Newton: 12 variables, 4 factors
    assert len(fg_n.variables) == 12
    assert len(fg_n.factors) == 4

    # Einstein: 15 variables, 10 factors (9 chain + 1 relation constraint)
    assert len(fg_e.variables) == 15
    assert len(fg_e.factors) == 10
