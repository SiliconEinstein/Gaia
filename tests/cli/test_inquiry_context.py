"""CLI tests for gaia inquiry context."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _write_context_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "context-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "context_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "context_demo"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim, derive, note\n\n"
        'galileo_setting = note("Galilean free-fall setup used as background context.")\n\n'
        'coupled_body = claim("The coupled heavy-light body argument makes proportional-speed '
        'scaling internally unstable.")\n'
        'coupled_body.label = "coupled_body"\n\n'
        'obs_fall = claim("Observed falling bodies do not separate enough to support '
        'proportional-speed scaling.")\n'
        'obs_fall.label = "obs_fall"\n\n'
        'reject_prop_speed = claim("The proportional-speed law for falling bodies is not a '
        'reliable account of free fall.")\n'
        'reject_prop_speed.label = "reject_prop_speed"\n\n'
        "speed_refutation = derive(\n"
        "    reject_prop_speed,\n"
        "    given=(coupled_body,),\n"
        '    rationale="Observation and internal argument point against proportional-speed '
        'scaling.",\n'
        '    label="reject_prop_speed_route",\n'
        ")\n\n"
        "observation_refutation = derive(\n"
        "    reject_prop_speed,\n"
        "    given=(obs_fall,),\n"
        '    rationale="",\n'
        '    label="observation_route",\n'
        ")\n\n"
        'pendulum_timing = claim("Pendulum timing suggests short arcs are approximately '
        'isochronous.")\n'
        'pendulum_timing.label = "pendulum_timing"\n\n'
        'acceleration_inquiry = claim("Early Galilean reasoning favors acceleration-based '
        'inquiry over proportional-speed law.")\n'
        'acceleration_inquiry.label = "acceleration_inquiry"\n\n'
        "acceleration_case = derive(\n"
        "    acceleration_inquiry,\n"
        "    given=(reject_prop_speed, pendulum_timing),\n"
        "    background=[galileo_setting],\n"
        '    rationale="The refutation of proportional-speed scaling and pendulum regularity '
        'motivate a different inquiry target.",\n'
        '    label="acceleration_route",\n'
        ")\n\n"
        '__all__ = ["acceleration_inquiry"]\n',
        encoding="utf-8",
    )


def _write_operator_context_package(pkg_dir) -> None:
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "operator-context-demo-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "operator_context_demo"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / "operator_context_demo"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import claim, equal\n\n"
        'a = claim("Hypothesis A.")\n'
        'a.label = "a"\n\n'
        'b = claim("Observation B.")\n'
        'b.label = "b"\n\n'
        'same_ab = equal(a, b, rationale="A and B should track the same truth value.", '
        'label="same_ab")\n\n'
        '__all__ = ["same_ab"]\n',
        encoding="utf-8",
    )


def test_context_markdown_uses_focus_why_and_references(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    result = runner.invoke(
        app,
        ["inquiry", "context", str(pkg), "--focus", "acceleration_inquiry"],
    )

    assert result.exit_code == 0, result.output
    assert "## Focus" in result.output
    assert "### `acceleration_inquiry`" in result.output
    assert "Early Galilean reasoning favors acceleration-based inquiry" in result.output
    assert "## Why This Claim" in result.output
    assert "### Why `acceleration_inquiry`?" in result.output
    assert "**Because**" in result.output
    assert "The refutation of proportional-speed scaling and pendulum regularity" in result.output
    assert "**Given**" in result.output
    assert "`reject_prop_speed`:" in result.output
    assert "`pendulum_timing`:" in result.output
    assert "**Background**" in result.output
    assert "`galileo_setting`" in result.output
    assert "## References" in result.output
    assert "### `reject_prop_speed`" in result.output
    assert (
        "The proportional-speed law for falling bodies is not a reliable account of free fall."
        in result.output
    )
    assert "### `galileo_setting`" in result.output
    assert "Galilean free-fall setup used as background context." in result.output
    assert "C1" not in result.output
    assert "B1" not in result.output
    assert "belief" not in result.output.lower()


def test_context_json_is_envelope_with_ir_slice(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    result = runner.invoke(
        app,
        ["inquiry", "context", str(pkg), "--focus", "acceleration_inquiry", "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["context_schema_version"] == 1
    assert data["focus"]["label"] == "acceleration_inquiry"
    assert data["selection"] == {"trajectory": "most_uncertain", "order": "backward"}
    assert data["why_route"]
    assert data["why_route"][0]["edge_kind"] == "strategy"
    assert data["why_route"][0]["label"] == "acceleration_route"
    assert (
        data["why_route"][0]["rationale"]
        == "The refutation of proportional-speed scaling and pendulum regularity "
        "motivate a different inquiry target."
    )
    assert "ir" in data
    expected_ir_keys = {
        "namespace",
        "package_name",
        "scope",
        "knowledges",
        "strategies",
        "operators",
        "composes",
        "formula_graphs",
    }
    assert expected_ir_keys.issubset(data["ir"])
    assert "ir_hash" not in data["ir"]
    rendered_labels = {item.get("label") for item in data["ir"]["knowledges"]}
    assert {
        "acceleration_inquiry",
        "reject_prop_speed",
        "pendulum_timing",
        "galileo_setting",
    }.issubset(rendered_labels)
    assert "belief_report" not in data
    assert "beliefs" not in json.dumps(data)


def test_context_json_ir_slice_includes_operator_route_records(tmp_path):
    pkg = tmp_path / "operator_context_demo"
    _write_operator_context_package(pkg)

    result = runner.invoke(
        app,
        ["inquiry", "context", str(pkg), "--focus", "same_ab", "--json"],
    )

    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert data["why_route"][0]["edge_kind"] == "operator"
    assert data["why_route"][0]["label"] == "same_ab"
    assert data["ir"]["operators"]
    operator_labels = {
        (item.get("metadata") or {}).get("action_label", "").rsplit("::action::", 1)[-1]
        for item in data["ir"]["operators"]
    }
    assert "same_ab" in operator_labels


def test_context_uses_current_focus_without_mutating_state(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    focus = runner.invoke(app, ["inquiry", "focus", "acceleration_inquiry", "--path", str(pkg)])
    assert focus.exit_code == 0, focus.output
    state_path = pkg / ".gaia" / "inquiry" / "state.json"
    before = state_path.read_text(encoding="utf-8")

    result = runner.invoke(app, ["inquiry", "context", str(pkg)])

    assert result.exit_code == 0, result.output
    assert "### `acceleration_inquiry`" in result.output
    after = state_path.read_text(encoding="utf-8")
    assert after == before


def test_context_with_focus_does_not_create_inquiry_state_dir(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)
    inquiry_dir = pkg / ".gaia" / "inquiry"
    assert not inquiry_dir.exists()

    result = runner.invoke(
        app,
        ["inquiry", "context", str(pkg), "--focus", "acceleration_inquiry"],
    )

    assert result.exit_code == 0, result.output
    assert "### `acceleration_inquiry`" in result.output
    assert not inquiry_dir.exists()


def test_context_shortest_and_most_uncertain_can_choose_different_routes(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    shortest = runner.invoke(
        app,
        [
            "inquiry",
            "context",
            str(pkg),
            "--focus",
            "acceleration_inquiry",
            "--trajectory",
            "shortest",
            "--json",
        ],
    )
    uncertain = runner.invoke(
        app,
        [
            "inquiry",
            "context",
            str(pkg),
            "--focus",
            "acceleration_inquiry",
            "--trajectory",
            "most_uncertain",
            "--json",
        ],
    )

    assert shortest.exit_code == 0, shortest.output
    assert uncertain.exit_code == 0, uncertain.output
    shortest_labels = [step["label"] for step in json.loads(shortest.output)["why_route"]]
    uncertain_labels = [step["label"] for step in json.loads(uncertain.output)["why_route"]]
    assert shortest_labels == ["acceleration_route"]
    assert uncertain_labels == ["acceleration_route", "observation_route"]


def test_context_most_uncertain_honors_label_based_rejections(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)
    rejected = runner.invoke(
        app,
        [
            "inquiry",
            "reject",
            "reject_prop_speed_route",
            "--content",
            "This route needs follow-up.",
            "--path",
            str(pkg),
        ],
    )
    assert rejected.exit_code == 0, rejected.output

    result = runner.invoke(
        app,
        [
            "inquiry",
            "context",
            str(pkg),
            "--focus",
            "acceleration_inquiry",
            "--trajectory",
            "most_uncertain",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    labels = [step["label"] for step in json.loads(result.output)["why_route"]]
    assert labels == ["acceleration_route", "reject_prop_speed_route"]


def test_context_missing_focus_exits_2(tmp_path):
    pkg = tmp_path / "context_demo"
    _write_context_package(pkg)

    result = runner.invoke(app, ["inquiry", "context", str(pkg)])

    assert result.exit_code == 2
    assert "No inquiry focus set" in result.output
    assert "gaia inquiry focus <claim>" in result.output
