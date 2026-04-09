"""End-to-end integration tests for the refs system in compile.py."""

from __future__ import annotations

import json
from pathlib import Path

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
            "from gaia.lang import claim, abduction, induction\n\n"
            'obs1 = claim("First observation.")\n'
            'obs2 = claim("Second observation.")\n'
            'law = claim("A general law.")\n'
            # Create sub-strategies manually to test recursion
            "sub1 = abduction(obs1, law)\n"
            "sub2 = abduction(obs2, law, reason='Justification [@missing_key]')\n"
            "induction([sub1, sub2])\n"
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
