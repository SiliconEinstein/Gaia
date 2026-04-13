"""End-to-end integration tests for the refs system in compile.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def _write_package(
    root: Path,
    name: str,
    module_body: str,
    references_json: dict | None = None,
) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "1.0.0"\n\n'
        f'[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    src_dir = pkg_dir / name.replace("-", "_")
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text(module_body)
    if references_json is not None:
        (pkg_dir / "references.json").write_text(json.dumps(references_json))
    return pkg_dir


def test_compile_errors_on_label_citation_collision(tmp_path: Path) -> None:
    """Per spec §3.5, a key that exists in both the label table and
    references.json must cause a compile error."""
    pkg = _write_package(
        tmp_path,
        name="collision_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'bell_lemma = claim("A lemma about Bell.")\n'
            'main_result = claim("Main result.")\n'
            "deduction(premises=[bell_lemma], conclusion=main_result)\n"
            '__all__ = ["main_result", "bell_lemma"]\n'
        ),
        references_json={
            "bell_lemma": {
                "type": "article-journal",
                "title": "Bell's inequality paper",
            }
        },
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0, f"Expected non-zero exit but got output: {result.output}"
    assert "ambiguous" in result.output.lower()
    assert "bell_lemma" in result.output


def test_compile_errors_on_mixed_type_bracket_group(tmp_path: Path) -> None:
    """Per spec §3.2, a bracketed group must not mix knowledge refs and citations."""
    pkg = _write_package(
        tmp_path,
        name="mixed_group_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'lemma_a = claim("A helper lemma.")\n'
            'main_result = claim("Main result. See [see @lemma_a; @Bell1964, p. 5] for context.")\n'
            "deduction(premises=[lemma_a], conclusion=main_result)\n"
            '__all__ = ["main_result", "lemma_a"]\n'
        ),
        references_json={"Bell1964": {"type": "article-journal", "title": "On EPR"}},
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0, f"Expected non-zero exit but got: {result.output}"
    assert "mixed" in result.output.lower()
    assert "lemma_a" in result.output
    assert "Bell1964" in result.output


def test_compile_errors_on_strict_miss(tmp_path: Path) -> None:
    """`[@nothing]` is strict form — unknown key must error."""
    pkg = _write_package(
        tmp_path,
        name="strict_miss_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'premise_a = claim("Premise A.")\n'
            'main_result = claim("Main result. See [@nothing_at_all] for context.")\n'
            "deduction(premises=[premise_a], conclusion=main_result)\n"
            '__all__ = ["main_result", "premise_a"]\n'
        ),
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0, f"Expected non-zero exit but got: {result.output}"
    assert "nothing_at_all" in result.output
    # Error message should mention unknown/strict/bracket
    out_lower = result.output.lower()
    assert "unknown" in out_lower or "not" in out_lower


def test_compile_tolerates_opportunistic_miss(tmp_path: Path) -> None:
    """Bare `@nothing` is opportunistic — unknown key is treated as literal."""
    pkg = _write_package(
        tmp_path,
        name="opp_miss_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'premise_a = claim("Premise A.")\n'
            'main_result = claim("Use the @dataclass decorator for this.")\n'
            "deduction(premises=[premise_a], conclusion=main_result)\n"
            '__all__ = ["main_result", "premise_a"]\n'
        ),
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code == 0, f"Expected success but got: {result.output}"


def test_compile_scans_sub_strategy_reasons(tmp_path: Path) -> None:
    """Spec §3.2: sub_strategies of composite strategies must also be scanned
    for references. A strict-form unknown ref in a sub_strategy must error."""
    pkg = _write_package(
        tmp_path,
        name="sub_strategy_refs_pkg",
        module_body=(
            "from gaia.lang import claim, support, induction\n\n"
            'obs1 = claim("First observation.")\n'
            'obs2 = claim("Second observation.")\n'
            'law = claim("A general law.")\n'
            # Create sub-strategies manually to test recursion
            "sub1 = support(premises=[obs1], conclusion=law)\n"
            "sub2 = support(premises=[obs2], conclusion=law, reason='Justification [@missing_key]', prior=0.9)\n"
            "induction(sub1, sub2, law)\n"
            '__all__ = ["law", "obs1", "obs2"]\n'
        ),
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    # The sub_strategy's reason has a strict-form unknown ref,
    # so this should fail. (Verifies sub_strategy recursion works.)
    assert result.exit_code != 0, f"Expected error but got: {result.output}"
    assert "missing_key" in result.output


def test_compile_records_provenance_metadata(tmp_path: Path) -> None:
    """Provenance metadata records both cited_refs and referenced_claims."""
    pkg = _write_package(
        tmp_path,
        name="provenance_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'lemma_a = claim("A helper lemma.")\n'
            'main_result = claim("Main result depends on [@lemma_a] and [@Bell1964].")\n'
            "deduction(premises=[lemma_a], conclusion=main_result)\n"
            '__all__ = ["main_result", "lemma_a"]\n'
        ),
        references_json={"Bell1964": {"type": "article-journal", "title": "On EPR"}},
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code == 0, result.output

    ir_path = pkg / ".gaia" / "ir.json"
    assert ir_path.exists(), f"Expected compiled IR at {ir_path}"
    ir = json.loads(ir_path.read_text())

    main_nodes = [k for k in ir["knowledges"] if k["id"].endswith("::main_result")]
    assert len(main_nodes) == 1, f"Expected exactly one main_result node, got {len(main_nodes)}"
    main_node = main_nodes[0]

    metadata = main_node.get("metadata", {})
    gaia_meta = metadata.get("gaia", {})
    provenance = gaia_meta.get("provenance", {})
    assert provenance.get("cited_refs") == ["Bell1964"]
    assert provenance.get("referenced_claims") == ["lemma_a"]


# ---------------------------------------------------------------------------
# §3.1 regression: imported foreign labels must resolve in the symbol table
# ---------------------------------------------------------------------------


@pytest.fixture()
def two_package_setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Set up refs_dep_pkg (compiled) and return (dep_dir, main_dir, main_src) paths.

    The dep package exposes ``foreign_lemma`` via ``__all__``.
    The consumer package imports it and uses it as a deduction premise.

    Uses ``refs_dep_pkg`` as the module name (not ``dep_pkg``) to avoid
    collisions with other tests that also create a ``dep_pkg`` module.
    """
    # --- refs_dep_pkg ------------------------------------------------------
    dep_dir = tmp_path / "refs_dep_pkg_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-dep-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "refs_dep_pkg"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'foreign_lemma = claim("A foundational lemma from a dependency package.")\n'
        '__all__ = ["foreign_lemma"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    # Compile refs_dep_pkg so its exports manifest is available.
    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, f"refs_dep_pkg compile failed:\n{dep_compile.output}"

    # --- refs_main_pkg -----------------------------------------------------
    main_dir = tmp_path / "refs_main_pkg"
    main_dir.mkdir()
    (main_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "refs-main-pkg-gaia"\n'
        'version = "1.0.0"\n'
        'dependencies = ["refs-dep-pkg-gaia>=1.0.0"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    main_src = main_dir / "refs_main_pkg"
    main_src.mkdir()

    return dep_dir, main_dir, main_src


def test_imported_foreign_label_resolves_in_strict_form(
    two_package_setup: tuple,
) -> None:
    """Spec §3.1 regression: foreign label imported into the compile closure
    must resolve in strict ``[@foreign_lemma]`` form.

    If someone later narrows label_to_id to local-only labels, the strict
    form will raise an "unknown reference key" error — this test is the
    tripwire that catches that regression.
    """
    _dep_dir, main_dir, main_src = two_package_setup
    (main_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from refs_dep_pkg import foreign_lemma\n\n"
        "main_result = claim(\n"
        '    "Main result. This follows from [@foreign_lemma]."\n'
        ")\n"
        "deduction(premises=[foreign_lemma], conclusion=main_result)\n"
        '__all__ = ["main_result"]\n'
    )

    result = runner.invoke(app, ["compile", str(main_dir)])
    assert result.exit_code == 0, (
        f"Strict form [@foreign_lemma] failed to compile — "
        f"the symbol table may not include the full closure.\n{result.output}"
    )

    ir_path = main_dir / ".gaia" / "ir.json"
    assert ir_path.exists()
    ir = json.loads(ir_path.read_text())

    main_nodes = [k for k in ir["knowledges"] if k["id"].endswith("::main_result")]
    assert len(main_nodes) == 1
    main_node = main_nodes[0]

    provenance = main_node.get("metadata", {}).get("gaia", {}).get("provenance", {})
    assert "foreign_lemma" in provenance.get("referenced_claims", []), (
        f"Expected 'foreign_lemma' in referenced_claims provenance metadata, got: {provenance}"
    )


def test_imported_foreign_label_resolves_in_opportunistic_form(
    two_package_setup: tuple,
) -> None:
    """Spec §3.1 regression: foreign label imported into the compile closure
    must also resolve in opportunistic ``@foreign_lemma`` form (bare @-ref in
    a strategy reason).

    In opportunistic form an unknown key becomes a literal, so if the symbol
    table is missing the foreign label the reference silently disappears from
    provenance — no error, but wrong metadata. This test asserts the label IS
    present in provenance (i.e. it was resolved, not treated as a literal miss).
    """
    _dep_dir, main_dir, main_src = two_package_setup
    (main_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from refs_dep_pkg import foreign_lemma\n\n"
        'main_result = claim("Main result.")\n'
        "deduction(\n"
        "    premises=[foreign_lemma],\n"
        "    conclusion=main_result,\n"
        '    reason="Follows directly from @foreign_lemma.",\n'
        "    prior=0.9,\n"
        ")\n"
        '__all__ = ["main_result"]\n'
    )

    result = runner.invoke(app, ["compile", str(main_dir)])
    assert result.exit_code == 0, (
        f"Opportunistic form @foreign_lemma failed to compile.\n{result.output}"
    )

    ir_path = main_dir / ".gaia" / "ir.json"
    assert ir_path.exists()
    ir = json.loads(ir_path.read_text())

    main_nodes = [k for k in ir["knowledges"] if k["id"].endswith("::main_result")]
    assert len(main_nodes) == 1
    main_node = main_nodes[0]

    provenance = main_node.get("metadata", {}).get("gaia", {}).get("provenance", {})
    assert "foreign_lemma" in provenance.get("referenced_claims", []), (
        "Expected 'foreign_lemma' in referenced_claims provenance metadata — "
        "opportunistic @-ref was not resolved (treated as literal miss, "
        "which means the foreign label is not in the symbol table). "
        f"Got: {provenance}"
    )


def test_consumer_compile_tolerates_dep_content_with_unknown_refs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for Codex review P1: consumer must not re-validate the
    content of foreign (imported) knowledge nodes against its own symbol
    table.

    Scenario:
      - dep_pkg has a claim whose content contains ``[@Bell1964]``, a
        reference that is valid in the dep's own references.json
      - consumer_pkg imports that claim and uses it as a premise, but has
        no references.json of its own
      - consumer_pkg should compile successfully — the dep's content is
        the dep author's responsibility, not the consumer's
    """
    # --- dep_pkg with a citation in its own content -----------------------
    dep_dir = tmp_path / "refs_dep_p1_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-dep-p1-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (dep_dir / "references.json").write_text(
        json.dumps({"Bell1964": {"type": "article-journal", "title": "On EPR"}})
    )
    dep_src = dep_dir / "src" / "refs_dep_p1"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim\n\n"
        'foreign_lemma = claim("An important lemma [@Bell1964].")\n'
        '__all__ = ["foreign_lemma"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))

    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, f"dep compile failed:\n{dep_compile.output}"

    # --- consumer_pkg WITHOUT references.json -----------------------------
    main_dir = tmp_path / "refs_consumer_p1"
    main_dir.mkdir()
    (main_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "refs-consumer-p1-gaia"\n'
        'version = "1.0.0"\n'
        'dependencies = ["refs-dep-p1-gaia>=1.0.0"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    main_src = main_dir / "refs_consumer_p1"
    main_src.mkdir()
    (main_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n"
        "from refs_dep_p1 import foreign_lemma\n\n"
        'main_result = claim("Main result.")\n'
        "deduction(premises=[foreign_lemma], conclusion=main_result)\n"
        '__all__ = ["main_result"]\n'
    )

    result = runner.invoke(app, ["compile", str(main_dir)])
    assert result.exit_code == 0, (
        f"Consumer compile failed because it re-validated the dep's content "
        f"against its own (empty) references.json. Foreign node content is "
        f"the dep author's responsibility, not the consumer's.\n{result.output}"
    )


def test_bridge_reason_does_not_leak_provenance_to_foreign_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression for Codex adversarial review finding #2: a bridge
    package's fills() reason may contain citations, but those citations
    must NOT be attributed to the foreign ``target`` node's IR metadata.

    Scenario:
      - dep_pkg has a ``missing_lemma`` claim that is a local hole
      - bridge_pkg does ``fills(source=b_result, target=missing_lemma,
        reason="See [@Bell1964]")`` with Bell1964 in its own
        references.json
      - the bridge pkg's compiled IR must leave the foreign
        ``missing_lemma`` node's metadata.gaia.provenance alone

    Otherwise the consumer's citations leak onto dependency-owned nodes
    and make cross-consumer provenance queries return wrong answers.
    """
    # --- dep_pkg with a local hole -----------------------------------------
    dep_dir = tmp_path / "refs_dep_bridge_root"
    dep_dir.mkdir()
    (dep_dir / "pyproject.toml").write_text(
        '[project]\nname = "refs-dep-bridge-gaia"\nversion = "0.4.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    dep_src = dep_dir / "src" / "refs_dep_bridge"
    dep_src.mkdir(parents=True)
    (dep_src / "__init__.py").write_text(
        "from gaia.lang import claim, deduction\n\n"
        'missing_lemma = claim("A missing lemma.")\n'
        'main_theorem = claim("Main theorem.")\n'
        "deduction(premises=[missing_lemma], conclusion=main_theorem)\n"
        '__all__ = ["main_theorem"]\n'
    )
    monkeypatch.syspath_prepend(str(dep_dir / "src"))
    dep_compile = runner.invoke(app, ["compile", str(dep_dir)])
    assert dep_compile.exit_code == 0, dep_compile.output

    # --- bridge_pkg that fills() the foreign hole with a citation ----------
    bridge_dir = tmp_path / "refs_bridge_pkg"
    bridge_dir.mkdir()
    (bridge_dir / "pyproject.toml").write_text(
        "[project]\n"
        'name = "refs-bridge-pkg-gaia"\n'
        'version = "1.0.0"\n'
        'dependencies = ["refs-dep-bridge-gaia>=0.4.0"]\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    (bridge_dir / "references.json").write_text(
        json.dumps(
            {
                "Bell1964": {
                    "type": "article-journal",
                    "title": "On the Einstein Podolsky Rosen Paradox",
                }
            }
        )
    )
    bridge_src = bridge_dir / "refs_bridge_pkg"
    bridge_src.mkdir()
    (bridge_src / "__init__.py").write_text(
        "from gaia.lang import claim, fills\n"
        "from refs_dep_bridge import missing_lemma\n\n"
        'b_result = claim("A new theorem that proves the missing lemma.")\n'
        "fills(\n"
        "    source=b_result,\n"
        "    target=missing_lemma,\n"
        '    reason="Theorem 3 establishes the lemma. See [@Bell1964].",\n'
        ")\n"
        '__all__ = ["b_result"]\n'
    )

    result = runner.invoke(app, ["compile", str(bridge_dir)])
    assert result.exit_code == 0, result.output

    ir_path = bridge_dir / ".gaia" / "ir.json"
    ir = json.loads(ir_path.read_text())

    # Find the foreign missing_lemma entry in the bridge's compiled IR.
    foreign_nodes = [k for k in ir["knowledges"] if k["id"].endswith("::missing_lemma")]
    assert len(foreign_nodes) == 1, (
        f"Expected exactly one missing_lemma node, got {len(foreign_nodes)}"
    )
    foreign_node = foreign_nodes[0]

    # Foreign node must not carry consumer-local citations in its provenance.
    foreign_provenance = foreign_node.get("metadata", {}).get("gaia", {}).get("provenance", {})
    assert "Bell1964" not in foreign_provenance.get("cited_refs", []), (
        "Consumer-local citation 'Bell1964' leaked onto the foreign "
        "missing_lemma node's provenance. Bridge strategy reasons must not "
        "attribute refs to foreign targets — they belong to the dep author, "
        f"not the consumer. Got: {foreign_provenance}"
    )

    # Sanity check: Bell1964 should still have been VALIDATED (it is in the
    # bridge's references.json, so compile succeeds). The citation is simply
    # dropped from provenance writeback since there is no local owner.
