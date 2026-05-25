"""Tests for the exploration render (SCHEMA.md §7g, build 5 — stellaris starmap).

The exploration map renders through gaia's own starmap pipeline
(``generate_graph_json`` → ``to_dot(theme="stellaris")`` → ``sfdp`` →
``post_process_stellaris_svg``), so it is visually identical to
``gaia inspect starmap --theme stellaris``. This module's render layer is the
pure, engine-safe overlay on top of that SVG:

* **Unit** — the overlay helpers: open frontier → dashed ``question`` graph
  nodes (+ ``background`` edges to in-graph sources), the exploration-state
  header fields, the header SVG injection (idempotent), and the self-contained
  HTML wrap.
* **CLI** — run ``gaia-lkm-explore render`` against the galileo example flow
  (compile + infer + init + frontier) and assert it writes a nonempty
  self-contained ``.html`` carrying the rendered ``<svg>`` (exercises the full
  starmap pipeline + the frontier/header overlay end-to-end; needs Graphviz).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app as gaia_app
from gaia.engine.exploration.render import (
    _two_word_label,
    exploration_header_fields,
    frontier_graph_elements,
    inject_exploration_header,
    wrap_self_contained_html,
)
from gaia.engine.exploration.state import (
    Contact,
    ExplorationMap,
    Policy,
)
from gaia.explore_client.cli import app

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

NS = "example"
PKG = "demo"


def _qid(label: str) -> str:
    return f"{NS}:{PKG}::{label}"


def _demo_map() -> ExplorationMap:
    """A small map: a seed + 2 open frontier contacts (one lkm paper, one qid) + a closed one."""
    seed = _qid("seed_claim")
    m = ExplorationMap(
        round=2,
        seeds=[{"kind": "claim", "text": "Why do bodies fall?", "qid": seed}],
        policy=Policy(doctrine="Inquisitor", budget_k=3),
    )
    m.frontier.append(
        Contact(
            id="ct_paper01",
            ref={"kind": "lkm", "value": "PAPER42"},
            sources=[{"qid": seed, "edge": "lkm_related"}],
            score=0.61,
            status="open",
            meta={"paper_id": "PAPER42", "title": "On the Acceleration of Falling Bodies"},
        )
    )
    m.frontier.append(
        Contact(
            id="ct_qid01",
            ref={"kind": "qid", "value": _qid("unmaterialized_factor")},
            sources=[{"qid": _qid("not_in_graph"), "edge": "depends_on"}],
            score=0.22,
            status="open",
        )
    )
    m.frontier.append(
        Contact(
            id="ct_closed",
            ref={"kind": "lkm", "value": "PAPER_CLOSED"},
            sources=[{"qid": seed, "edge": "lkm_related"}],
            score=0.4,
            status="surveyed",
        )
    )
    return m


def test_frontier_graph_elements_builds_question_nodes() -> None:
    m = _demo_map()
    seed = _qid("seed_claim")
    nodes, edges = frontier_graph_elements(m, existing_node_ids={seed})

    # Only the 2 OPEN contacts become nodes; the surveyed (non-open) one is excluded.
    ids = {n["id"] for n in nodes}
    assert ids == {"PAPER42", _qid("unmaterialized_factor")}
    assert "PAPER_CLOSED" not in ids
    # They render as dashed "question" (open-inquiry) nodes, unlit.
    for n in nodes:
        assert n["type"] == "question"
        assert n["belief"] is None
        assert n["exported"] is False
    # The drawn label is truncated to its first two words (+ … since the title
    # has more). `title` is left None so it can't override the truncated label
    # at render time (the dot emitter renders `title or label`).
    paper = next(n for n in nodes if n["id"] == "PAPER42")
    assert paper["title"] is None
    assert paper["label"] == "On the…"
    # An edge is added only to a source that is actually in the graph.
    assert {"source": seed, "target": "PAPER42", "role": "background"} in edges
    # The qid contact's source (_qid("not_in_graph")) is NOT a node → no dangling edge.
    assert all(e["target"] != _qid("unmaterialized_factor") for e in edges)


def test_two_word_label_truncates_to_first_two_words() -> None:
    # > 2 words → first two + ellipsis.
    assert _two_word_label("Muon g − 2 and Δα connection") == "Muon g…"
    assert _two_word_label("Evidence for and implications thereof") == "Evidence for…"
    # ≤ 2 words → unchanged (no ellipsis).
    assert _two_word_label("paper PAPER42") == "paper PAPER42"
    assert _two_word_label("solo") == "solo"
    # Never yields an empty label.
    assert _two_word_label("PAPER42") == "PAPER42"


def test_frontier_graph_elements_truncates_and_always_labels() -> None:
    """Every drawn fog node shows a non-empty, two-word-truncated label."""
    m = ExplorationMap(
        seeds=[{"kind": "claim", "text": "q", "qid": _qid("seed")}],
        policy=Policy(doctrine="Surveyor", budget_k=3),
    )
    # Multi-word title → first two words + … ; title-less lkm → "paper <id>".
    m.frontier.append(
        Contact(
            id="ct_multi",
            ref={"kind": "lkm", "value": "PAPER_MULTI"},
            score=0.9,
            status="open",
            meta={"title": "Evidence for and implications thereof"},
        )
    )
    m.frontier.append(
        Contact(
            id="ct_titleless",
            ref={"kind": "lkm", "value": "PAPER_BARE"},
            score=0.5,
            status="open",
        )
    )
    nodes, _edges = frontier_graph_elements(m, existing_node_ids=set())
    by_id = {n["id"]: n for n in nodes}
    assert by_id["PAPER_MULTI"]["label"] == "Evidence for…"
    # Title-less contact still labeled: "paper PAPER_BARE" is ≤2 words → kept whole.
    assert by_id["PAPER_BARE"]["label"] == "paper PAPER_BARE"
    # No drawn fog node is ever blank, and `title` never carries the full text
    # (which the dot emitter would prefer over the truncated `label`).
    for n in nodes:
        assert n["label"].strip() != ""
        assert n["title"] is None


def test_frontier_graph_elements_caps_fog_by_score() -> None:
    # A pulled paper can surface 100+ not-yet-formalized claims; the figure caps
    # the dashed fog at the top `limit` by score (survey is budget-bounded
    # elsewhere). The header still reports the true total separately.
    m = ExplorationMap(
        seeds=[{"kind": "claim", "text": "q", "qid": _qid("seed")}],
        policy=Policy(doctrine="Surveyor", budget_k=3),
    )
    for i in range(40):
        m.frontier.append(
            Contact(
                id=f"ct_{i:02d}",
                ref={"kind": "qid", "value": _qid(f"pulled_{i:02d}")},
                score=float(i),  # higher i = higher score
                status="open",
                meta={"pulled_unformalized": True, "title": f"claim {i}"},
            )
        )
    nodes, _edges = frontier_graph_elements(m, existing_node_ids=set(), limit=10)
    assert len(nodes) == 10
    # The 10 highest-scored (i = 39..30) are the ones drawn.
    drawn = {n["id"] for n in nodes}
    assert _qid("pulled_39") in drawn
    assert _qid("pulled_00") not in drawn


def test_exploration_header_fields() -> None:
    fields = dict(exploration_header_fields(_demo_map()))
    assert fields["doctrine"] == "Inquisitor"
    assert fields["round"] == "2"
    assert fields["frontier open"] == "2"
    assert "surveyed" in fields
    assert "Why do bodies fall?" in fields["seed"]


def test_inject_exploration_header_is_idempotent() -> None:
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 800 600" '
        'width="800pt" height="600pt"><g></g></svg>'
    )
    fields = exploration_header_fields(_demo_map())
    once = inject_exploration_header(svg, fields)
    assert 'id="exploration-header"' in once
    assert "Inquisitor" in once
    assert "exploration" in once
    assert once.count("</svg>") == 1
    # Idempotent: a second pass does not double the panel.
    twice = inject_exploration_header(once, fields)
    assert twice == once


def test_wrap_self_contained_html() -> None:
    svg = '<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    out = wrap_self_contained_html(svg)
    assert out.lstrip().startswith("<!DOCTYPE html>")
    assert "<html" in out and "</html>" in out
    assert svg in out
    # No external assets / CDN references; no required JS.
    assert "src=" not in out
    assert "href=" not in out
    assert "<script" not in out
    assert "https://" not in out


# --------------------------------------------------------------------------- #
# CLI — galileo example flow (full stellaris-starmap pipeline + overlay)       #
# --------------------------------------------------------------------------- #


def _example_root() -> Path:
    return Path(__file__).resolve().parents[2] / "examples" / "galileo-v0-5-gaia"


@pytest.fixture
def galileo_pkg(tmp_path: Path) -> Path:
    src = _example_root()
    assert src.is_dir(), f"galileo fixture not found at {src}"
    pkg = tmp_path / "galileo-v0-5-gaia"
    shutil.copytree(src, pkg)
    assert runner.invoke(gaia_app, ["build", "compile", str(pkg)]).exit_code == 0
    assert runner.invoke(gaia_app, ["run", "infer", str(pkg)]).exit_code == 0
    return pkg


def _galileo_qid(label: str) -> str:
    return f"example:galileo_v0_5::{label}"


@pytest.mark.skipif(shutil.which("sfdp") is None, reason="Graphviz sfdp not on PATH")
def test_cli_render_writes_nonempty_html(galileo_pkg: Path) -> None:
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])

    result = runner.invoke(app, ["render", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Rendered exploration map" in result.output

    out_path = galileo_pkg / ".gaia" / "exploration" / "map.html"
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert content.lstrip().startswith("<!DOCTYPE html>")
    assert "<svg" in content
    # The stellaris pipeline baked its node-role legend + space background in,
    # and our overlay added the exploration-state header.
    assert 'id="legend"' in content
    assert 'id="exploration-header"' in content
    assert "space-bg" in content


@pytest.mark.skipif(shutil.which("sfdp") is None, reason="Graphviz sfdp not on PATH")
def test_cli_render_custom_out_path(galileo_pkg: Path, tmp_path: Path) -> None:
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])
    custom = tmp_path / "out" / "galileo-map.html"
    result = runner.invoke(app, ["render", str(galileo_pkg), "--out", str(custom)])
    assert result.exit_code == 0, result.output
    assert custom.exists()
    assert custom.read_text(encoding="utf-8").lstrip().startswith("<!DOCTYPE html>")


@pytest.mark.skipif(shutil.which("sfdp") is None, reason="Graphviz sfdp not on PATH")
def test_render_stellaris_svg_fog_legend_gated_by_frontier_flag() -> None:
    """The fog legend row is drawn iff `include_frontier` is set.

    `render_command` passes `include_frontier=bool(frontier_nodes)`, so the fog
    row appears only when frontier (fog) boxes were actually overlaid — never on
    the plain `gaia inspect starmap` stellaris path (which renders the shared
    legend with the flag left False).
    """
    from gaia.explore_client.verbs import _render_stellaris_svg

    dot = 'digraph G { bgcolor="#05060f"; a [label="a"]; }'

    without = _render_stellaris_svg(dot, include_frontier=False)
    assert "frontier · unexplored (fog)" not in without
    assert 'stroke-dasharray="4,2"' not in without

    with_fog = _render_stellaris_svg(dot, include_frontier=True)
    assert "frontier · unexplored (fog)" in with_fog
    assert 'stroke-dasharray="4,2"' in with_fog
    # Default (no flag) matches the starmap path — no fog row.
    assert _render_stellaris_svg(dot) == without


def test_cli_render_without_init_fails_gracefully(galileo_pkg: Path) -> None:
    result = runner.invoke(app, ["render", str(galileo_pkg)])
    assert result.exit_code == 1
    assert "no exploration map" in result.output


# --------------------------------------------------------------------------- #
# Phase 3 (EXPANSION.md §3.E): ratified boundary / reopened flag in render       #
# --------------------------------------------------------------------------- #


def test_ratified_node_classes_marks_ratified_and_reopened() -> None:
    from gaia.engine.exploration.health import Component, MapHealth
    from gaia.engine.exploration.render import ratified_node_classes

    m = ExplorationMap()
    m.add_ratified_separation(["lkm:pkg::b"], rationale="sep", round_index=1)
    m.add_ratified_separation(["lkm:pkg::c"], rationale="sep", round_index=1)
    # A live health whose {c} island reopened (stale premise).
    health = MapHealth(
        components=(),
        largest_fraction=0.0,
        orphans=(),
        orphan_node_fraction=0.0,
        unratified_orphan_count=0,
        reopened=(Component(members=("lkm:pkg::c",), reopened=True),),
    )
    classes = ratified_node_classes(m, health=health)
    assert classes["lkm:pkg::b"] == "ratified"
    assert classes["lkm:pkg::c"] == "reopened"


def test_ratified_node_classes_without_health_all_ratified() -> None:
    from gaia.engine.exploration.render import ratified_node_classes

    m = ExplorationMap()
    m.add_ratified_separation(["lkm:pkg::b", "lkm:pkg::c"], rationale="sep", round_index=1)
    classes = ratified_node_classes(m)
    assert classes == {"lkm:pkg::b": "ratified", "lkm:pkg::c": "ratified"}


def test_header_fields_surface_connectivity_with_health() -> None:
    from gaia.engine.exploration.health import Component, MapHealth

    m = _demo_map()
    health = MapHealth(
        components=(Component(members=("x",), is_seed=True), Component(members=("y",))),
        largest_fraction=0.5,
        orphans=(Component(members=("y",)),),
        orphan_node_fraction=0.5,
        unratified_orphan_count=1,
        reopened=(),
    )
    fields = dict(exploration_header_fields(m, health=health))
    assert fields["components"] == "2"
    assert fields["orphans"] == "1"
    assert "ratified" in fields


def test_header_fields_surface_ratified_count_without_health() -> None:
    m = _demo_map()
    m.add_ratified_separation(["lkm:pkg::b"], rationale="sep", round_index=1)
    fields = dict(exploration_header_fields(m))
    assert fields["ratified"] == "1"
