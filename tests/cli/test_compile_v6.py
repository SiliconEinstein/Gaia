"""End-to-end tests for v6 Knowledge types."""

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_v6_knowledge_types_compile(tmp_path):
    """A package using v6 Knowledge types compiles to correct IR."""
    pkg_dir = tmp_path / "v6_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "v6-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "v6 test"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "v6_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import Claim, Grounding, Note\n\n"
        "ctx = Note('Raw AB test data from dashboard.', format='text')\n"
        "exp = Note('AB test exp_123: 50/50 randomization.')\n"
        "hyp = Claim(\n"
        "    'Variant B is better.',\n"
        "    prior=0.5,\n"
        "    grounding=Grounding(kind='judgment', rationale='Uninformative prior.'),\n"
        ")\n"
        "__all__ = ['hyp']\n"
    )
    (pkg_src / "priors.py").write_text(
        'from . import hyp\n\nPRIORS: dict = {\n    hyp: (0.5, "uninformative"),\n}\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Compile failed: {result.output}"

    ir_path = pkg_dir / ".gaia" / "ir.json"
    assert ir_path.exists()
    ir = json.loads(ir_path.read_text())

    types = {k["type"] for k in ir["knowledges"]}
    assert "note" in types

    ctx_node = [k for k in ir["knowledges"] if k.get("label") == "ctx"][0]
    assert ctx_node["format"] == "text"

    hyp_node = [k for k in ir["knowledges"] if k.get("label") == "hyp"][0]
    assert hyp_node["format"] == "markdown"
    assert hyp_node["metadata"]["grounding"]["kind"] == "judgment"
    assert hyp_node["metadata"]["grounding"]["rationale"] == "Uninformative prior."
