import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_compile_v6_actions_package(tmp_path):
    pkg_dir = tmp_path / "v6-actions-gaia"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "v6-actions-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "v6_actions"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, contradict, derive, equal, infer, observe\n\n"
        'calibrated = claim("Spectrometer is calibrated.")\n'
        'data = observe("UV spectrum is finite.", rationale="Measured.", label="observe_uv")\n'
        'prediction = claim("Planck model predicts finite UV spectrum.")\n'
        'classical = claim("Classical model predicts divergent UV spectrum.")\n'
        'agreement = equal(prediction, data, rationale="Prediction matches data.", label="match")\n'
        'conflict = contradict(classical, data, rationale="Prediction conflicts.", label="conflict")\n'
        "data = infer(\n"
        "    data,\n"
        "    hypothesis=prediction,\n"
        "    background=[calibrated],\n"
        "    p_e_given_h=0.9,\n"
        "    p_e_given_not_h=0.1,\n"
        '    rationale="Bayesian update.",\n'
        '    label="bayes_update",\n'
        ")\n"
        "favored = derive(\n"
        '    "Planck model is favored.",\n'
        "    given=(agreement, conflict, data),\n"
        '    rationale="Agreement, conflict, and observed data favor Planck.",\n'
        '    label="favor_planck",\n'
        ")\n"
        '__all__ = ["favored"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, result.output

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())
    strategy_patterns = {
        s["metadata"]["pattern"]
        for s in ir["strategies"]
        if s.get("metadata") and "pattern" in s["metadata"]
    }
    assert {"derivation", "inference"} <= strategy_patterns
    infer_strategy = next(
        s
        for s in ir["strategies"]
        if (s.get("metadata") or {}).get("action_label")
        == "github:v6_actions::action::bayes_update"
    )
    assert infer_strategy["conditional_probabilities"] == [0.1, 0.9]

    grounding_patterns = {
        k["metadata"]["grounding"]["pattern"]
        for k in ir["knowledges"]
        if (k.get("metadata") or {}).get("grounding") and "pattern" in k["metadata"]["grounding"]
    }
    assert "observation" in grounding_patterns

    operator_types = {op["operator"] for op in ir["operators"]}
    assert {"equivalence", "contradiction"} <= operator_types

    action_labels = [
        s["metadata"]["action_label"]
        for s in ir["strategies"]
        if s.get("metadata") and "action_label" in s["metadata"]
    ]
    action_labels.extend(
        op["metadata"]["action_label"]
        for op in ir["operators"]
        if op.get("metadata") and "action_label" in op["metadata"]
    )
    action_labels.extend(
        k["metadata"]["grounding"]["action_label"]
        for k in ir["knowledges"]
        if (k.get("metadata") or {}).get("grounding")
        and "action_label" in k["metadata"]["grounding"]
    )
    assert "github:v6_actions::action::observe_uv" in action_labels
    assert "github:v6_actions::action::favor_planck" in action_labels
    assert "github:v6_actions::action::match" in action_labels
    assert "github:v6_actions::action::conflict" in action_labels
