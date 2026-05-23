"""Tests for the exploration render (SCHEMA.md §7g, build 5).

Two layers, mirroring the other exploration tests:

* **Unit** — build a small in-memory map (a seed + a couple surveyed nodes with
  beliefs + a contradiction-involved node + an ``lkm_related`` paper-contact + a
  round with discoveries), render it via :func:`render_map_html`, and assert the
  output is one self-contained HTML document (``<!DOCTYPE html>`` / ``<html>``,
  an inline ``<svg>``, no external ``src=``/``href=`` to a CDN), carries the
  seed / contradiction / support CSS markers, the frontier contact's pull line,
  and the legend + header fields.
* **CLI** — run ``gaia explore render`` against the galileo example flow
  (compile + infer + init + frontier) and assert it writes a nonempty ``.html``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.engine.exploration.frontier import JointView
from gaia.engine.exploration.render import compute_layout, render_map_html
from gaia.engine.exploration.state import (
    Contact,
    ExplorationMap,
    Policy,
    SurveyRecord,
)

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

NS = "example"
PKG = "demo"


def _qid(label: str) -> str:
    return f"{NS}:{PKG}::{label}"


def _demo_map() -> tuple[ExplorationMap, JointView, dict[str, float], list[dict]]:
    """Build a small in-memory map for the unit render tests.

    A seed + 2 surveyed nodes (one contradiction-involved) + an ``lkm_related``
    paper-contact + a qid stub contact + a round with discoveries.
    """
    seed = _qid("seed_claim")
    claim_a = _qid("claim_a")
    claim_b = _qid("claim_b")

    m = ExplorationMap(
        round=1,
        seeds=[{"kind": "claim", "text": "Why do bodies fall?", "qid": seed}],
        policy=Policy(doctrine="Inquisitor", budget_k=3),
    )
    for qid in (seed, claim_a, claim_b):
        m.surveyed[qid] = SurveyRecord(qid=qid, survey_round=0)

    # An lkm_related paper-contact on the rim, off the seed.
    m.frontier.append(
        Contact(
            id="ct_paper01",
            ref={"kind": "lkm", "value": "PAPER42"},
            sources=[{"qid": seed, "edge": "lkm_related"}],
            score=0.61,
            score_features={
                "belief_entropy": 0.9,
                "closeness_to_seed": 1.0,
                "survey_cost": 2.0,
                "tension_potential": 0.0,
                "bridge_potential": 0.0,
                "new_territory": 0.8,
            },
            status="open",
            meta={
                "paper_id": "PAPER42",
                "title": "On the Acceleration of Falling Bodies",
                "index_id": "bohrium",
            },
        )
    )
    # A qid stub contact off claim_a.
    m.frontier.append(
        Contact(
            id="ct_qid01",
            ref={"kind": "qid", "value": _qid("unmaterialized_factor")},
            sources=[{"qid": claim_a, "edge": "depends_on"}],
            score=0.22,
            status="open",
        )
    )

    # Joint view: seed/claim_a tied by a strategy edge, seed/claim_b by an
    # operator edge (so the contradiction-involved claim_b is adjacent to seed).
    view = JointView(
        materialized={seed, claim_a, claim_b},
        edges=[
            ("strategy_given", [seed, claim_a]),
            ("operator_target", [seed, claim_b]),
        ],
    )
    beliefs = {seed: 0.9, claim_a: 0.5, claim_b: 0.15}
    rounds = [
        {
            "round": 0,
            "policy": {"doctrine": "Inquisitor"},
            "discoveries": [
                {"kind": "contradiction", "ids": [claim_b], "note": "belief dropped"},
                {"kind": "keystone", "ids": [seed], "note": "high in-degree"},
            ],
        }
    ]
    return m, view, beliefs, rounds


def test_render_is_self_contained_html() -> None:
    m, view, beliefs, rounds = _demo_map()
    out = render_map_html(m, view, beliefs=beliefs, rounds=rounds)

    # One self-contained HTML document.
    assert out.lstrip().startswith("<!DOCTYPE html>")
    assert "<html" in out and "</html>" in out
    assert "<svg" in out and "</svg>" in out

    # No external assets / CDN references: every src=/href= would be an external
    # dep. We have none (inline SVG + inline CSS only).
    assert "src=" not in out
    assert "href=" not in out
    assert "http://" not in out.replace("http://www.w3.org/2000/svg", "")
    assert "https://" not in out
    assert "<script" not in out  # no required JS


def test_render_carries_color_vocabulary_classes() -> None:
    m, view, beliefs, rounds = _demo_map()
    claim_b = _qid("claim_b")
    claim_a = _qid("claim_a")
    out = render_map_html(
        m,
        view,
        beliefs=beliefs,
        rounds=rounds,
        contradiction_qids={claim_b},
        support_qids={claim_a},
    )
    # The CSS vocabulary (matching the stellaris semantics) is present.
    assert ".seed" in out
    assert ".contradiction" in out
    assert ".support" in out
    # And the role classes are applied to nodes.
    assert "seed" in out
    assert "contradiction" in out
    assert "support" in out
    # Space-dark background gradient is defined inline.
    assert "space-bg" in out


def test_render_shows_frontier_pull_line_and_title() -> None:
    m, view, beliefs, rounds = _demo_map()
    out = render_map_html(m, view, beliefs=beliefs, rounds=rounds)
    # The lkm_related contact carries its title + the pull line.
    assert "On the Acceleration of Falling Bodies" in out
    assert "gaia pkg add --lkm-index bohrium --lkm-paper PAPER42" in out


def test_render_has_legend_and_header_fields() -> None:
    m, view, beliefs, rounds = _demo_map()
    out = render_map_html(m, view, beliefs=beliefs, rounds=rounds)
    # Legend present.
    assert 'id="legend"' in out
    assert "Legend" in out
    # Header fields present.
    assert 'id="header"' in out
    assert "doctrine" in out
    assert "Inquisitor" in out
    assert "round" in out
    assert "surveyed" in out
    assert "frontier open" in out
    # Per-round discovery summary.
    assert 'id="discoveries"' in out
    assert "Round discoveries" in out
    assert "contradiction" in out


def test_render_is_deterministic() -> None:
    m, view, beliefs, rounds = _demo_map()
    a = render_map_html(m, view, beliefs=beliefs, rounds=rounds)
    b = render_map_html(m, view, beliefs=beliefs, rounds=rounds)
    assert a == b


def test_compute_layout_centers_lone_seed() -> None:
    seed = _qid("seed_claim")
    layout = compute_layout([seed], [seed], {}, {})
    placement = layout.surveyed[seed]
    # The lone seed sits exactly at the canvas centre (ring 0).
    assert placement.ring == 0
    from gaia.engine.exploration.render import _CENTER_X, _CENTER_Y

    assert placement.x == pytest.approx(_CENTER_X)
    assert placement.y == pytest.approx(_CENTER_Y)


def test_render_handles_empty_map() -> None:
    # An empty map (no seeds, no surveyed, no frontier, no rounds) still renders a
    # valid self-contained doc rather than crashing.
    m = ExplorationMap()
    view = JointView()
    out = render_map_html(m, view, beliefs={}, rounds=[])
    assert out.lstrip().startswith("<!DOCTYPE html>")
    assert "<svg" in out
    assert 'id="legend"' in out
    assert "(no rounds yet)" in out


# --------------------------------------------------------------------------- #
# CLI — galileo example flow                                                  #
# --------------------------------------------------------------------------- #


def _example_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "galileo-v0-5-gaia"


@pytest.fixture
def galileo_pkg(tmp_path: Path) -> Path:
    src = _example_root()
    assert src.is_dir(), f"galileo fixture not found at {src}"
    pkg = tmp_path / "galileo-v0-5-gaia"
    shutil.copytree(src, pkg)
    assert runner.invoke(app, ["build", "compile", str(pkg)]).exit_code == 0
    assert runner.invoke(app, ["run", "infer", str(pkg)]).exit_code == 0
    return pkg


def _galileo_qid(label: str) -> str:
    return f"example:galileo_v0_5::{label}"


def test_cli_render_writes_nonempty_html(galileo_pkg: Path) -> None:
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])

    result = runner.invoke(app, ["explore", "render", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Rendered exploration map" in result.output

    out_path = galileo_pkg / ".gaia" / "exploration" / "map.html"
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert len(content) > 0
    assert content.lstrip().startswith("<!DOCTYPE html>")
    assert "<svg" in content


def test_cli_render_custom_out_path(galileo_pkg: Path, tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    custom = tmp_path / "out" / "galileo-map.html"
    result = runner.invoke(app, ["explore", "render", str(galileo_pkg), "--out", str(custom)])
    assert result.exit_code == 0, result.output
    assert custom.exists()
    assert custom.read_text(encoding="utf-8").lstrip().startswith("<!DOCTYPE html>")


def test_cli_render_without_init_fails_gracefully(galileo_pkg: Path) -> None:
    result = runner.invoke(app, ["explore", "render", str(galileo_pkg)])
    assert result.exit_code == 1
    assert "no exploration map" in result.output
