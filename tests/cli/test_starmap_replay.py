"""Tests for the `gaia starmap-replay` command."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.commands._replay_build import (
    annotate_layout_with_kinds,
    annotate_ticks_with_survival,
    bridge_event_symbols_to_layout,
    collect_round_lkm_membership,
    collect_round_order,
    rekey_layout_to_lkm_ids,
    split_into_ir_ticks,
    topo_reorder_ticks,
)
from gaia.cli.commands.starmap_replay import (
    build_timeline_payload,
    merge_events,
)
from gaia.cli.main import app

runner = CliRunner()

FIXTURE_DIR = (
    Path(__file__).resolve().parents[1] / "fixtures" / "starmap_replay" / "mendelian_inheritance"
)


def _extract_timeline(html: str) -> dict:
    """Pull the JSON blob the CLI injects via window.TIMELINE_DATA."""
    match = re.search(r"window\.TIMELINE_DATA = (.*?);</script>", html, re.DOTALL)
    assert match is not None, "window.TIMELINE_DATA assignment missing from replay HTML"
    return json.loads(match.group(1))


# ── Smoke test against the real fixture ─────────────────────────────────────


def test_starmap_replay_against_fixture(tmp_path):
    """End-to-end: the bundled fixture renders 7 retrievals + 35 growth events."""
    assert FIXTURE_DIR.is_dir(), f"fixture not present at {FIXTURE_DIR}"

    out_path = tmp_path / "replay.html"
    result = runner.invoke(
        app,
        ["starmap-replay", str(FIXTURE_DIR), "--out", str(out_path)],
    )
    assert result.exit_code == 0, result.output
    assert out_path.exists()

    html = out_path.read_text(encoding="utf-8")
    # Self-contained HTML carries the timeline JSON inline plus expected DOM
    # IDs the frontend script binds to.
    assert "window.TIMELINE_DATA" in html
    assert 'id="graph-canvas"' in html
    assert 'id="btn-play"' in html
    assert 'id="lane-retrieval-track"' in html

    payload = _extract_timeline(html)
    assert payload["schema_version"] == "1"
    assert payload["retrieval_count"] == 7
    assert payload["growth_count"] == 35
    assert len(payload["events"]) == 42

    # v4: tick axis + rounds + (best-effort) layout / round_beliefs.
    assert "ticks" in payload
    assert isinstance(payload["ticks"], list)
    # The fixture has a known set of IR-relevant gaia_actions
    # (claim/deduction/support/contradiction/equivalence/prior); ticks
    # must be non-empty and never exceed total gaia_actions count.
    assert len(payload["ticks"]) > 0
    total_actions = sum(len(e.get("gaia_actions") or []) for e in payload["events"])
    assert len(payload["ticks"]) <= total_actions
    assert payload["rounds"] == ["round_0000", "round_0001", "round_0002"]
    # round_beliefs and final_layout default to {} / None when the
    # package has no compiled IR — the fixture is shipped without one.
    assert "round_beliefs" in payload
    assert "final_layout" in payload

    # Each event should carry an event_kind tag and the merged stream should
    # be sorted (timestamp, actor_id, seq) ascending.
    kinds = {e["event_kind"] for e in payload["events"]}
    assert kinds == {"retrieval", "growth"}
    timestamps = [e["timestamp_utc"] for e in payload["events"]]
    assert timestamps == sorted(timestamps), "events not chronologically sorted"

    # First event must be the package_initialized growth event; last must be
    # the final stage_transition to done — guards the merge boundary.
    first = payload["events"][0]
    assert first["event_kind"] == "growth"
    assert first["decision"] == "package_initialized"
    last = payload["events"][-1]
    assert last["event_kind"] == "growth"
    assert last["decision"] == "stage_transition"
    assert last["payload"]["to"] == "done"

    # Reporting line includes both counts.
    assert "7 retrievals" in result.output
    assert "35 growth events" in result.output


def test_starmap_replay_default_output_path(tmp_path):
    """Without --out, replay lands at <pkg>/.gaia/starmap-replay.html."""
    # Copy fixture into tmp_path so we don't pollute the source-tree fixture.
    import shutil

    pkg_dir = tmp_path / "mendelian_inheritance"
    shutil.copytree(FIXTURE_DIR, pkg_dir)

    result = runner.invoke(app, ["starmap-replay", str(pkg_dir)])
    assert result.exit_code == 0, result.output
    expected = pkg_dir / ".gaia" / "starmap-replay.html"
    assert expected.is_file()


def test_starmap_replay_missing_logs(tmp_path):
    """Missing logs produce a clear error and non-zero exit."""
    pkg_dir = tmp_path / "empty_pkg"
    (pkg_dir / "artifacts" / "lkm-discovery").mkdir(parents=True)

    result = runner.invoke(app, ["starmap-replay", str(pkg_dir)])
    assert result.exit_code != 0
    assert "missing timeline log" in result.output


def test_starmap_replay_path_must_be_directory(tmp_path):
    """Non-directory path is rejected up front."""
    f = tmp_path / "not_a_dir.txt"
    f.write_text("hi")
    result = runner.invoke(app, ["starmap-replay", str(f)])
    assert result.exit_code != 0
    assert "is not a directory" in result.output


# ── Merge-ordering unit tests on synthetic input ────────────────────────────


def _ev(actor_id: str, seq: int, ts: str, **extra) -> dict:
    base = {
        "schema_version": "1",
        "actor_id": actor_id,
        "seq": seq,
        "timestamp_utc": ts,
        "event_id": f"{ts}__{actor_id}__x__{seq}",
    }
    base.update(extra)
    return base


def test_merge_orders_by_timestamp_then_actor_then_seq():
    retrievals = [
        _ev("actor-A", 2, "2026-05-05T00:00:01.000Z", channel="support"),
    ]
    growths = [
        _ev("actor-B", 1, "2026-05-05T00:00:00.500Z", decision="round_open"),
        # Same timestamp as the retrieval, different actor — actor sorts second.
        _ev("actor-Z", 1, "2026-05-05T00:00:01.000Z", decision="dismissed"),
        # Same timestamp & actor, larger seq.
        _ev("actor-A", 3, "2026-05-05T00:00:01.000Z", decision="accepted_support"),
    ]
    merged = merge_events(retrievals, growths)
    ids = [(e["timestamp_utc"], e["actor_id"], e["seq"]) for e in merged]
    assert ids == [
        ("2026-05-05T00:00:00.500Z", "actor-B", 1),
        ("2026-05-05T00:00:01.000Z", "actor-A", 2),
        ("2026-05-05T00:00:01.000Z", "actor-A", 3),
        ("2026-05-05T00:00:01.000Z", "actor-Z", 1),
    ]
    # event_kind tags are populated.
    kinds = [e["event_kind"] for e in merged]
    assert kinds.count("retrieval") == 1
    assert kinds.count("growth") == 3


# ── v4: tick splitting + round membership ──────────────────────────────────


def test_split_into_ir_ticks_one_tick_per_ir_action():
    """Each IR-relevant gaia_action becomes one tick; non-IR actions skipped."""
    events = [
        # Two IR actions in one event → two ticks, in array order.
        {
            "event_id": "e1",
            "round_id": "r0",
            "retrieval_event_ids": ["r-1"],
            "gaia_actions": [
                {"action": "claim", "symbol": "a"},
                {"action": "support", "symbol": "s"},
                # Non-IR action — must NOT produce a tick.
                {"action": "inquiry_hypothesis", "symbol": "h"},
            ],
        },
        # Event with no actions → zero ticks.
        {"event_id": "e2", "round_id": "r0", "gaia_actions": []},
        # Event whose only action is inquiry-only → zero ticks.
        {
            "event_id": "e3",
            "round_id": "r1",
            "gaia_actions": [{"action": "inquiry_obligation", "symbol": "o"}],
        },
        # Single IR action.
        {
            "event_id": "e4",
            "round_id": "r1",
            "retrieval_event_ids": [],
            "gaia_actions": [{"action": "deduction", "symbol": "d"}],
        },
    ]
    ticks = split_into_ir_ticks(events)
    assert [t["action"]["action"] for t in ticks] == ["claim", "support", "deduction"]
    assert [t["event_index"] for t in ticks] == [0, 0, 3]
    assert [t["action_index"] for t in ticks] == [0, 1, 0]
    assert ticks[0]["lkm_driven"] is True
    assert ticks[2]["lkm_driven"] is False
    assert ticks[0]["round_id"] == "r0"
    assert ticks[2]["round_id"] == "r1"
    # tick_index is dense + 0-based.
    assert [t["tick_index"] for t in ticks] == [0, 1, 2]


def test_collect_round_lkm_membership_is_cumulative():
    """Cumulative truncation: round R contains R's lkm_ids plus all earlier."""
    events = [
        {
            "round_id": "r0",
            "graph_delta": {"nodes_added": [{"lkm_id": "gcn_a"}, {"lkm_id": "gcn_b"}]},
        },
        {
            "round_id": "r1",
            "graph_delta": {"nodes_added": [{"lkm_id": "gcn_c"}]},
        },
        # Round 1 again — adds another id.
        {
            "round_id": "r1",
            "graph_delta": {"nodes_added": [{"lkm_id": "gcn_d"}]},
        },
        {"round_id": "r2", "graph_delta": {"nodes_added": []}},
    ]
    membership = collect_round_lkm_membership(events)
    assert collect_round_order(events) == ["r0", "r1", "r2"]
    assert membership["r0"] == {"gcn_a", "gcn_b"}
    assert membership["r1"] == {"gcn_a", "gcn_b", "gcn_c", "gcn_d"}
    assert membership["r2"] == {"gcn_a", "gcn_b", "gcn_c", "gcn_d"}


def test_payload_carries_ticks_and_rounds_for_synthetic_input():
    """build_timeline_payload exposes ticks / rounds even without a pkg_dir."""
    retrievals: list[dict] = []
    growths = [
        {
            "event_id": "g1",
            "actor_id": "a",
            "seq": 1,
            "timestamp_utc": "2026-05-05T00:00:00.000Z",
            "round_id": "r0",
            "decision": "round_open",
            "schema_version": "1",
        },
        {
            "event_id": "g2",
            "actor_id": "a",
            "seq": 2,
            "timestamp_utc": "2026-05-05T00:00:01.000Z",
            "round_id": "r0",
            "decision": "accepted_claim",
            "schema_version": "1",
            "gaia_actions": [
                {"action": "claim", "symbol": "x"},
                {"action": "prior", "symbol": "x"},
            ],
        },
    ]
    payload = build_timeline_payload(retrievals, growths, package_name="syn")
    assert payload["rounds"] == ["r0"]
    assert len(payload["ticks"]) == 2
    assert payload["ticks"][0]["action"]["action"] == "claim"
    assert payload["round_beliefs"] == {}
    assert payload["final_layout"] is None


# ── v4 fix: layout re-key by lkm_id ─────────────────────────────────────────


def test_rekey_layout_moves_knowledge_keys_to_lkm_ids():
    """Verify rekey layout moves knowledge keys to lkm ids.

    Knowledge layout entries get re-keyed to their metadata.lkm_id; helpers without an lkm_id
    keep their namespaced key; strat_/oper_ entries are untouched.
    """
    layout = {
        "viewport": {"width": 100, "height": 50},
        "nodes": {
            "github:pkg::with_lkm": {"x": 1.0, "y": 2.0},
            "github:pkg::no_lkm": {"x": 3.0, "y": 4.0},
            "github:pkg::__implication_result_abc": {"x": 5.0, "y": 6.0},
            "strat_0": {"x": 7.0, "y": 8.0},
            "oper_3": {"x": 9.0, "y": 10.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {
                "id": "github:pkg::with_lkm",
                "metadata": {"lkm_id": "gcn_deadbeef"},
            },
            {
                "id": "github:pkg::no_lkm",
                "metadata": {},
            },
            {
                "id": "github:pkg::__implication_result_abc",
                "metadata": {"lkm_id": None},
            },
        ]
    }
    new_layout, warns = rekey_layout_to_lkm_ids(layout, ir)
    assert warns == []
    keys = set(new_layout["nodes"].keys())
    assert "gcn_deadbeef" in keys, "with_lkm should be re-keyed"
    assert "github:pkg::with_lkm" not in keys, "old IR id should be gone"
    assert "github:pkg::no_lkm" in keys, "no_lkm helper keeps namespaced key"
    assert "github:pkg::__implication_result_abc" in keys, "implication helper kept"
    assert "strat_0" in keys and "oper_3" in keys
    assert new_layout["nodes"]["gcn_deadbeef"] == {"x": 1.0, "y": 2.0}


def test_rekey_layout_warns_on_lkm_id_collision():
    """Two IR knowledges sharing one lkm_id → warning, second mapping skipped."""
    layout = {
        "viewport": {"width": 100, "height": 50},
        "nodes": {
            "github:pkg::a": {"x": 1.0, "y": 2.0},
            "github:pkg::b": {"x": 3.0, "y": 4.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "github:pkg::a", "metadata": {"lkm_id": "gcn_dup"}},
            {"id": "github:pkg::b", "metadata": {"lkm_id": "gcn_dup"}},
        ]
    }
    new_layout, warns = rekey_layout_to_lkm_ids(layout, ir)
    assert any("duplicate lkm_id" in w for w in warns)
    assert "gcn_dup" in new_layout["nodes"]
    # The second node, whose mapping was skipped, retains its namespaced key.
    assert "github:pkg::b" in new_layout["nodes"]


def test_rekey_layout_overlaps_with_event_ids_after_fix():
    """Simulate the bug-1 fix end-to-end on a small synthetic payload.

    Before the re-key, the layout keys nodes by IR-namespaced ids while
    events reference them by raw lkm_ids → 0% overlap. After re-keying,
    every gcn-style event id finds its pinned coordinate.
    """
    layout = {
        "viewport": {"width": 200, "height": 100},
        "nodes": {
            "local:pkg::alpha": {"x": 10.0, "y": 20.0},
            "local:pkg::beta": {"x": 30.0, "y": 40.0},
            "local:pkg::__implication_result_x": {"x": 50.0, "y": 60.0},
            "strat_0": {"x": 70.0, "y": 80.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "local:pkg::alpha", "metadata": {"lkm_id": "gcn_aaaa"}},
            {"id": "local:pkg::beta", "metadata": {"lkm_id": "gcn_bbbb"}},
            {"id": "local:pkg::__implication_result_x", "metadata": {}},
        ]
    }
    events = [
        {"graph_delta": {"nodes_added": [{"id": "gcn_aaaa", "lkm_id": "gcn_aaaa"}]}},
        {"graph_delta": {"nodes_added": [{"id": "gcn_bbbb", "lkm_id": "gcn_bbbb"}]}},
    ]
    new_layout, _ = rekey_layout_to_lkm_ids(layout, ir)
    event_ids = {
        n["id"] for ev in events for n in (ev.get("graph_delta") or {}).get("nodes_added", [])
    }
    layout_keys = set(new_layout["nodes"].keys())
    overlap = event_ids & layout_keys
    assert overlap == event_ids, (
        f"every gcn event id should now resolve to a pinned position; "
        f"missing: {event_ids - layout_keys}"
    )


def test_bridge_event_symbols_to_layout_handles_deduction_and_operator():
    """Verify bridge event symbols to layout handles deduction and operator.

    Strategy gfac_* and operator-symbol contradictions get aliased to their strat_<i> / oper_<i>
    pinned positions.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0},
            "gcn_b": {"x": 2.0, "y": 2.0},
            "gcn_c": {"x": 3.0, "y": 3.0},
            "strat_0": {"x": 10.0, "y": 10.0},
            "oper_0": {"x": 20.0, "y": 20.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "metadata": {"lkm_id": "gcn_b"}},
            {"id": "ns:c", "metadata": {"lkm_id": "gcn_c"}},
        ],
        "strategies": [
            {
                "type": "deduction",
                "premises": ["ns:a"],
                "conclusion": "ns:b",
            },
        ],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:b", "ns:c"],
            },
        ],
    }
    events = [
        {
            "gaia_actions": [{"action": "deduction", "symbol": "gfac_xx"}],
            "graph_delta": {
                "nodes_added": [{"id": "gfac_xx", "kind": "deduction"}],
                "edges_added": [
                    {"kind": "deduction", "from": "gcn_a", "to": "gcn_b"},
                ],
            },
        },
        {
            "gaia_actions": [
                {"action": "contradiction", "symbol": "b_vs_c"},
            ],
            "graph_delta": {
                "nodes_added": [{"id": "b_vs_c", "kind": "contradiction"}],
                "edges_added": [
                    {"kind": "contradiction", "from": "gcn_b", "to": "gcn_c"},
                ],
            },
        },
    ]
    new_layout, warns = bridge_event_symbols_to_layout(layout, ir, events)
    nodes = new_layout["nodes"]
    assert "gfac_xx" in nodes
    assert nodes["gfac_xx"]["x"] == 10.0
    assert nodes["gfac_xx"]["y"] == 10.0
    assert nodes["gfac_xx"]["canonical_id"] == "strat_0"
    assert "b_vs_c" in nodes
    assert nodes["b_vs_c"]["x"] == 20.0
    assert nodes["b_vs_c"]["y"] == 20.0
    assert nodes["b_vs_c"]["canonical_id"] == "oper_0"
    assert any("bridged 2" in w for w in warns)


def test_bridge_handles_multiple_actions_per_event():
    """Two support actions in one event pair positionally with two edges."""
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0},
            "gcn_b": {"x": 2.0, "y": 2.0},
            "gcn_c": {"x": 3.0, "y": 3.0},
            "gcn_target": {"x": 4.0, "y": 4.0},
            "strat_0": {"x": 10.0, "y": 10.0},
            "strat_1": {"x": 11.0, "y": 11.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "metadata": {"lkm_id": "gcn_b"}},
            {"id": "ns:c", "metadata": {"lkm_id": "gcn_c"}},
            {"id": "ns:target", "metadata": {"lkm_id": "gcn_target"}},
        ],
        "strategies": [
            {"type": "support", "premises": ["ns:a"], "conclusion": "ns:target"},
            {"type": "support", "premises": ["ns:b"], "conclusion": "ns:target"},
        ],
    }
    events = [
        {
            "gaia_actions": [
                {"action": "support", "symbol": "support_one"},
                {"action": "support", "symbol": "support_two"},
            ],
            "graph_delta": {
                "nodes_added": [
                    {"id": "support_one", "kind": "support"},
                    {"id": "support_two", "kind": "support"},
                ],
                "edges_added": [
                    {"kind": "support", "from": "gcn_a", "to": "gcn_target"},
                    {"kind": "support", "from": "gcn_b", "to": "gcn_target"},
                ],
            },
        },
    ]
    new_layout, _ = bridge_event_symbols_to_layout(layout, ir, events)
    nodes = new_layout["nodes"]
    assert (nodes["support_one"]["x"], nodes["support_one"]["y"]) == (10.0, 10.0), (
        "first support → strat_0"
    )
    assert (nodes["support_two"]["x"], nodes["support_two"]["y"]) == (11.0, 11.0), (
        "second support → strat_1"
    )
    assert nodes["support_one"]["canonical_id"] == "strat_0"
    assert nodes["support_two"]["canonical_id"] == "strat_1"


def test_bridge_resolves_sparse_payload_via_file_kind_uniqueness():
    """Verify bridge resolves sparse payload via file kind uniqueness.

    Regression: an `accepted_contradiction` event whose payload lacks a `contradicts` list AND
    whose `graph_delta.edges_added` references gcns that don't match any IR operator's variables
    (a stale/renamed relation) must still bridge — via file-uniqueness fallback when the IR has
    exactly one unbridged contradiction operator declared in the same source file as the action.

    This is the 2dheg `n_quarter_scaling_vs_shell_filling_noise` shape:
    package author renamed the contradiction in `cross_paper.py` after
    the event was emitted, so the symbol is stale but the structural
    intent ("there's a contradiction in this file") survives.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0},
            "gcn_b": {"x": 2.0, "y": 2.0},
            "oper_0": {"x": 20.0, "y": 20.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "module": "cross_paper", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "module": "cross_paper", "metadata": {"lkm_id": "gcn_b"}},
            # The IR's current contradiction conclusion id — the slug
            # encodes the *current* Python symbol name, which differs
            # from the action.symbol below (stale rename).
            {"id": "ns:current_name_for_contradiction", "module": "cross_paper"},
        ],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:a", "ns:b"],
                "conclusion": "ns:current_name_for_contradiction",
            },
        ],
        "strategies": [],
    }
    events = [
        {
            "gaia_actions": [
                {
                    "action": "contradiction",
                    "symbol": "stale_contradiction_name",
                    "file": "src/pkg/cross_paper.py",
                },
            ],
            # Sparse payload: only `operator` + `relation_type`, no
            # `contradicts` field, no helpful structural info.
            "payload": {
                "operator": "stale_contradiction_name",
                "relation_type": "scientific_inconsistency",
            },
            "graph_delta": {
                "nodes_added": [{"id": "stale_contradiction_name", "kind": "contradiction"}],
                # Edge endpoints don't match the IR operator's variables
                # — represents the stale-rename / reshuffled-claims
                # case where the agent's old `graph_delta` no longer
                # mirrors the IR.
                "edges_added": [
                    {"from": "gcn_other_x", "to": "gcn_other_y", "kind": "contradiction"},
                ],
            },
        },
    ]
    new_layout, warns = bridge_event_symbols_to_layout(layout, ir, events)
    nodes = new_layout["nodes"]
    # The action's symbol must resolve to oper_0's pinned coords with
    # canonical_id stamped, so the survival check + frontend render see
    # the bridge.
    assert "stale_contradiction_name" in nodes
    assert nodes["stale_contradiction_name"]["x"] == 20.0
    assert nodes["stale_contradiction_name"]["y"] == 20.0
    assert nodes["stale_contradiction_name"]["canonical_id"] == "oper_0"
    # The fallback path is auditable via a build_warning naming the
    # strategy used.
    assert any("file-uniqueness fallback" in w for w in warns), (
        f"expected uniqueness-fallback warning, got: {warns}"
    )


def test_bridge_positional_fallback_pairs_sparse_events_in_declaration_order():
    """Verify bridge positional fallback pairs sparse events in declaration order.

    When the file has multiple unbridged operators of the same kind and the symbol-name doesn't
    match any of them, the positional fallback pairs the Nth pending event with the Nth
    unbridged IR operator in declaration order.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0},
            "gcn_b": {"x": 2.0, "y": 2.0},
            "gcn_c": {"x": 3.0, "y": 3.0},
            "gcn_d": {"x": 4.0, "y": 4.0},
            "oper_0": {"x": 20.0, "y": 20.0},
            "oper_1": {"x": 21.0, "y": 21.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "module": "cross_paper", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "module": "cross_paper", "metadata": {"lkm_id": "gcn_b"}},
            {"id": "ns:c", "module": "cross_paper", "metadata": {"lkm_id": "gcn_c"}},
            {"id": "ns:d", "module": "cross_paper", "metadata": {"lkm_id": "gcn_d"}},
            {"id": "ns:concl_0", "module": "cross_paper"},
            {"id": "ns:concl_1", "module": "cross_paper"},
        ],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:a", "ns:b"],
                "conclusion": "ns:concl_0",
            },
            {
                "operator": "contradiction",
                "variables": ["ns:c", "ns:d"],
                "conclusion": "ns:concl_1",
            },
        ],
        "strategies": [],
    }
    # Two sparse events whose graph_deltas reference unrelated gcns —
    # neither edge-signature nor symbol-name can resolve them, so the
    # positional fallback is forced.
    events = [
        {
            "gaia_actions": [
                {
                    "action": "contradiction",
                    "symbol": "first_stale",
                    "file": "src/pkg/cross_paper.py",
                },
            ],
            "payload": {"operator": "first_stale"},
            "graph_delta": {
                "nodes_added": [{"id": "first_stale", "kind": "contradiction"}],
                "edges_added": [
                    {"from": "gcn_unrelated_x", "to": "gcn_unrelated_y", "kind": "contradiction"},
                ],
            },
        },
        {
            "gaia_actions": [
                {
                    "action": "contradiction",
                    "symbol": "second_stale",
                    "file": "src/pkg/cross_paper.py",
                },
            ],
            "payload": {"operator": "second_stale"},
            "graph_delta": {
                "nodes_added": [{"id": "second_stale", "kind": "contradiction"}],
                "edges_added": [
                    {"from": "gcn_unrelated_p", "to": "gcn_unrelated_q", "kind": "contradiction"},
                ],
            },
        },
    ]
    new_layout, warns = bridge_event_symbols_to_layout(layout, ir, events)
    nodes = new_layout["nodes"]
    # First pending → oper_0, second pending → oper_1 by IR declaration
    # order in the same module.
    assert nodes["first_stale"]["canonical_id"] == "oper_0"
    assert nodes["second_stale"]["canonical_id"] == "oper_1"
    # Positional fallback emits an auditable warning for each fired
    # match.
    positional_warns = [w for w in warns if "positional fallback" in w]
    assert len(positional_warns) == 2, f"expected 2 positional-fallback warnings, got: {warns}"


def test_bridge_skips_fallback_when_action_file_lacks_py_extension():
    """Verify bridge skips fallback when action file lacks py extension.

    Degenerate `action.file` (no `.py` extension, e.g `src/perovskite_arpes_polaron`) must not
    trigger the file/positional fallbacks — those guard against false matches in packages where
    the agent emitted under-specified structural events that should remain orphans on the
    canvas.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0},
            "gcn_b": {"x": 2.0, "y": 2.0},
            "oper_0": {"x": 20.0, "y": 20.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "module": "cross_paper", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "module": "cross_paper", "metadata": {"lkm_id": "gcn_b"}},
            {"id": "ns:concl", "module": "cross_paper"},
        ],
        "operators": [
            {
                "operator": "contradiction",
                "variables": ["ns:a", "ns:b"],
                "conclusion": "ns:concl",
            },
        ],
        "strategies": [],
    }
    events = [
        {
            "gaia_actions": [
                {
                    "action": "contradiction",
                    "symbol": "stale",
                    # No .py extension — degenerate file path.
                    "file": "src/pkg",
                },
            ],
            "payload": {"operator": "stale"},
            "graph_delta": {
                "nodes_added": [{"id": "stale", "kind": "contradiction"}],
                "edges_added": [
                    {"from": "gcn_x", "to": "gcn_y", "kind": "contradiction"},
                ],
            },
        },
    ]
    new_layout, _ = bridge_event_symbols_to_layout(layout, ir, events)
    nodes = new_layout["nodes"]
    # Symbol must remain unbridged — fallback gates rejected the
    # under-specified file path.
    assert "stale" not in nodes


def test_rekey_layout_idempotent_without_ir():
    """Empty / missing IR is a no-op and returns no warnings."""
    layout = {
        "viewport": {"width": 0, "height": 0},
        "nodes": {"x": {"x": 0, "y": 0}},
        "clusters": [],
    }
    new_layout, warns = rekey_layout_to_lkm_ids(layout, {})
    assert new_layout is layout
    assert warns == []


def test_annotate_layout_with_kinds_marks_strategies_and_operators():
    """annotate_layout_with_kinds stamps `kind` + subtype on every entry the.

    IR can identify, so the replay frontend renders strategies as ellipses
    and operators as hexagons (red for contradictions) at their pinned
    positions — matching the static DOT output.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0},
            "gcn_b": {"x": 2.0, "y": 2.0},
            "local:pkg::__helper": {"x": 3.0, "y": 3.0},
            "strat_0": {"x": 10.0, "y": 10.0},
            "strat_1": {"x": 11.0, "y": 11.0},
            "oper_0": {"x": 20.0, "y": 20.0},
            "oper_1": {"x": 21.0, "y": 21.0},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {
                "id": "ns:a",
                "title": "Claim A",
                "type": "claim",
                "exported": True,
                "metadata": {"lkm_id": "gcn_a", "prior": 0.42},
            },
            {
                "id": "ns:b",
                "title": "Claim B",
                "type": "claim",
                "metadata": {"lkm_id": "gcn_b"},
            },
            {
                "id": "local:pkg::__helper",
                "title": "implication helper",
                "type": "claim",
                "metadata": {},
            },
        ],
        "strategies": [
            {"type": "deduction", "premises": ["ns:a"], "conclusion": "ns:b"},
            {"type": "support", "premises": ["ns:a"], "conclusion": "ns:b"},
        ],
        "operators": [
            {"operator": "contradiction", "variables": ["ns:a", "ns:b"]},
            {"operator": "equivalence", "variables": ["ns:a", "ns:b"]},
        ],
    }
    annotate_layout_with_kinds(layout, ir)
    nodes = layout["nodes"]

    # Strategy entries: kind=strategy + strategy_type carried through.
    assert nodes["strat_0"]["kind"] == "strategy"
    assert nodes["strat_0"]["strategy_type"] == "deduction"
    assert nodes["strat_0"]["label"] == "deduction"
    assert nodes["strat_1"]["strategy_type"] == "support"

    # Operator entries: kind=operator + operator_type with the right glyph
    # in `label`. Contradictions carry the red ⊗; other operators ⊙.
    assert nodes["oper_0"]["kind"] == "operator"
    assert nodes["oper_0"]["operator_type"] == "contradiction"
    assert nodes["oper_0"]["label"] == "⊗ contradiction"
    assert nodes["oper_1"]["operator_type"] == "equivalence"
    assert nodes["oper_1"]["label"] == "⊙ equivalence"

    # Knowledge entries: kind=knowledge + sub_kind reflects the static DOT
    # node-class rules. Exported claim → ★-prefixed label + sub_kind=exported.
    assert nodes["gcn_a"]["kind"] == "knowledge"
    assert nodes["gcn_a"]["sub_kind"] == "exported"
    assert nodes["gcn_a"]["exported"] is True
    assert nodes["gcn_a"]["label"].startswith("★ ")
    assert nodes["gcn_a"]["prior"] == 0.42
    # Conclusion of deduction / support → derived; non-conclusion → claim.
    assert nodes["gcn_b"]["sub_kind"] == "derived"
    # Helper without lkm_id keeps namespaced key and gets annotated by IR id.
    assert nodes["local:pkg::__helper"]["kind"] == "knowledge"


def test_annotate_layout_idempotent_without_ir():
    """Empty IR is a no-op."""
    layout = {
        "viewport": {"width": 0, "height": 0},
        "nodes": {"x": {"x": 0, "y": 0}},
        "clusters": [],
    }
    out = annotate_layout_with_kinds(layout, {})
    assert out is layout
    # No kind stamped when IR is empty.
    assert "kind" not in layout["nodes"]["x"]


# ── v4 fix: orphan-tick detection (survives_to_final) ──────────────────────


def test_annotate_ticks_with_survival_flags_orphan_deduction():
    """Verify annotate ticks with survival flags orphan deduction.

    A deduction action whose symbol the bridge could not alias to a `strat_<i>` (because the IR
    doesn't have a strategy with that `(premises, conclusion)` signature) is flagged orphan.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            # Surviving strategy entry (canonical) — bridges itself.
            "strat_0": {
                "x": 10.0,
                "y": 10.0,
                "kind": "strategy",
                "canonical_id": "strat_0",
            },
            # Bridged event-side alias for strat_0.
            "gfac_alive": {
                "x": 10.0,
                "y": 10.0,
                "kind": "strategy",
                "canonical_id": "strat_0",
            },
            # Knowledge entry that survives — keyed by lkm_id.
            "gcn_a": {"x": 1.0, "y": 2.0, "kind": "knowledge"},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "metadata": {"lkm_id": "gcn_a"}},
        ],
        "strategies": [{"type": "deduction", "premises": ["ns:a"], "conclusion": "ns:a"}],
        "operators": [],
    }
    events = [
        {
            "event_id": "e1",
            "gaia_actions": [
                {"action": "claim", "symbol": "gcn_a"},
                {"action": "deduction", "symbol": "gfac_alive"},
                # Orphan — no `gfac_orphan` entry in the layout because
                # the bridge couldn't match its signature against any IR
                # strategy (it was admitted mid-run but later merged away).
                {"action": "deduction", "symbol": "gfac_orphan"},
                # Orphan claim — symbol references a knowledge the final
                # IR doesn't carry.
                {"action": "claim", "symbol": "gcn_orphan"},
            ],
            "graph_delta": {"nodes_added": [], "edges_added": []},
        },
    ]
    ticks = split_into_ir_ticks(events)
    out_ticks, warnings = annotate_ticks_with_survival(ticks, events, layout, ir)
    survives = {t["tick_index"]: t["survives_to_final"] for t in out_ticks}
    # claim gcn_a → True (its lkm_id is in the IR).
    assert survives[0] is True
    # deduction gfac_alive → True (bridges to surviving strat_0).
    assert survives[1] is True
    # deduction gfac_orphan → False (not in layout post-bridge).
    assert survives[2] is False
    # claim gcn_orphan → False (not in IR's knowledge id/lkm_id set).
    assert survives[3] is False
    # Two orphans → two warning lines.
    orphan_warns = [w for w in warnings if "orphan IR-tick" in w]
    assert len(orphan_warns) == 2
    assert any("gfac_orphan" in w for w in orphan_warns)
    assert any("gcn_orphan" in w for w in orphan_warns)


def test_annotate_ticks_with_survival_defaults_true_without_ir_or_layout():
    """Without IR or layout, every tick defaults to surviving (no warnings)."""
    events = [
        {
            "event_id": "e1",
            "gaia_actions": [
                {"action": "claim", "symbol": "anything"},
                {"action": "deduction", "symbol": "gfac_x"},
            ],
        },
    ]
    ticks = split_into_ir_ticks(events)
    out, warns = annotate_ticks_with_survival(ticks, events, None, None)
    assert all(t["survives_to_final"] is True for t in out)
    assert warns == []


def test_annotate_ticks_with_survival_treats_symbol_less_deduction_as_surviving():
    """Verify annotate ticks with survival treats symbol less deduction as surviving.

    Symbol-less deductions (skip-pivot collapse: one action covers many edges) are treated as
    surviving — the reconcile-final-layout pass on the frontend admits the IR strategies anyway.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {"strat_0": {"x": 0.0, "y": 0.0, "kind": "strategy", "canonical_id": "strat_0"}},
        "clusters": [],
    }
    ir = {
        "knowledges": [],
        "strategies": [{"type": "deduction", "premises": ["x"], "conclusion": "x"}],
        "operators": [],
    }
    events = [
        {
            "event_id": "e1",
            "gaia_actions": [{"action": "deduction"}],  # no symbol
        },
    ]
    ticks = split_into_ir_ticks(events)
    out, warns = annotate_ticks_with_survival(ticks, events, layout, ir)
    assert out[0]["survives_to_final"] is True
    assert warns == []


# ── v4 fix: topo reorder by IR-dependency ───────────────────────────────────


def test_topo_reorder_promotes_dependent_after_dependency():
    """Verify topo reorder promotes dependent after dependency.

    A contradiction action whose variable claim hasn't been admitted yet in chronological order
    must be reordered after the claim.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0, "kind": "knowledge"},
            "gcn_b": {"x": 2.0, "y": 2.0, "kind": "knowledge"},
            "oper_0": {
                "x": 10.0,
                "y": 10.0,
                "kind": "operator",
                "operator_type": "contradiction",
                "canonical_id": "oper_0",
            },
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [],
        "operators": [
            {"operator": "contradiction", "variables": ["ns:a", "ns:b"]},
        ],
    }
    # Chronologically: claim_a, contradiction(oper_0), claim_b. The
    # contradiction depends on gcn_a *and* gcn_b — its second variable
    # isn't admitted yet. Topo reorder must push the contradiction
    # after claim_b.
    events = [
        {
            "event_id": "e1",
            "gaia_actions": [{"action": "claim", "symbol": "gcn_a"}],
        },
        {
            "event_id": "e2",
            "gaia_actions": [{"action": "contradiction", "symbol": "oper_0"}],
        },
        {
            "event_id": "e3",
            "gaia_actions": [{"action": "claim", "symbol": "gcn_b"}],
        },
    ]
    ticks = split_into_ir_ticks(events)
    ticks, _ = annotate_ticks_with_survival(ticks, events, layout, ir)
    out, warnings = topo_reorder_ticks(ticks, events, layout, ir)
    # After reorder: claim_a (0), claim_b (1), contradiction (2).
    sequence = [(t["action"]["action"], t["action"].get("symbol")) for t in out]
    assert sequence == [
        ("claim", "gcn_a"),
        ("claim", "gcn_b"),
        ("contradiction", "oper_0"),
    ]
    # tick_index re-stamped 0..N-1.
    assert [t["tick_index"] for t in out] == [0, 1, 2]
    # event_id provenance preserved (caller can still introspect origin).
    assert [t["event_id"] for t in out] == ["e1", "e3", "e2"]
    # Build warning records the swap count.
    assert any("topo_reorder: moved" in w for w in warnings)


def test_topo_reorder_preserves_chronology_when_no_dependency():
    """Verify topo reorder preserves chronology when no dependency.

    Independent claims keep their original chronological order — the tiebreak on tick_index
    leaves a no-op when no dep forces a swap.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0, "kind": "knowledge"},
            "gcn_b": {"x": 2.0, "y": 2.0, "kind": "knowledge"},
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [],
        "operators": [],
    }
    events = [
        {
            "event_id": "e1",
            "gaia_actions": [{"action": "claim", "symbol": "gcn_a"}],
        },
        {
            "event_id": "e2",
            "gaia_actions": [{"action": "claim", "symbol": "gcn_b"}],
        },
    ]
    ticks = split_into_ir_ticks(events)
    ticks, _ = annotate_ticks_with_survival(ticks, events, layout, ir)
    # Cache the original (event_id, action) ordering.
    original = [(t["event_id"], t["action"]["symbol"]) for t in ticks]
    out, warnings = topo_reorder_ticks(ticks, events, layout, ir)
    after = [(t["event_id"], t["action"]["symbol"]) for t in out]
    assert after == original
    assert [t["tick_index"] for t in out] == [0, 1]
    # No swap → no swap-count warning.
    assert not any("topo_reorder: moved" in w for w in warnings)


def test_topo_reorder_handles_cross_round():
    """Verify topo reorder handles cross round.

    A strategy in round_0 whose premise is a claim from round_2 must be pushed past the round_2
    claim by topo reorder. Dependency wins over round membership; we do NOT preserve round
    boundaries as a constraint.
    """
    layout = {
        "viewport": {"width": 100, "height": 100},
        "nodes": {
            "gcn_a": {"x": 1.0, "y": 1.0, "kind": "knowledge"},
            "gcn_b": {"x": 2.0, "y": 2.0, "kind": "knowledge"},
            "strat_0": {
                "x": 10.0,
                "y": 10.0,
                "kind": "strategy",
                "strategy_type": "support",
                "canonical_id": "strat_0",
            },
        },
        "clusters": [],
    }
    ir = {
        "knowledges": [
            {"id": "ns:a", "metadata": {"lkm_id": "gcn_a"}},
            {"id": "ns:b", "metadata": {"lkm_id": "gcn_b"}},
        ],
        "strategies": [
            # support: gcn_a (premise) supports gcn_b (conclusion).
            {"type": "support", "premises": ["ns:a"], "conclusion": "ns:b"},
        ],
        "operators": [],
    }
    # Chronologically: round_0 claims gcn_a then emits the support
    # strategy (referencing gcn_b which doesn't exist yet); round_2
    # finally claims gcn_b. After topo reorder the support tick must
    # land *after* the gcn_b claim, even though that claim sits in a
    # later round.
    events = [
        {
            "event_id": "e1",
            "round_id": "round_0",
            "gaia_actions": [{"action": "claim", "symbol": "gcn_a"}],
        },
        {
            "event_id": "e2",
            "round_id": "round_0",
            "gaia_actions": [{"action": "support", "symbol": "strat_0"}],
        },
        {
            "event_id": "e3",
            "round_id": "round_2",
            "gaia_actions": [{"action": "claim", "symbol": "gcn_b"}],
        },
    ]
    ticks = split_into_ir_ticks(events)
    ticks, _ = annotate_ticks_with_survival(ticks, events, layout, ir)
    out, warnings = topo_reorder_ticks(ticks, events, layout, ir)
    sequence = [(t["round_id"], t["action"]["action"], t["action"].get("symbol")) for t in out]
    # Expect: round_0 claim_a, round_2 claim_b, round_0 support (moved across rounds).
    assert sequence == [
        ("round_0", "claim", "gcn_a"),
        ("round_2", "claim", "gcn_b"),
        ("round_0", "support", "strat_0"),
    ]
    assert [t["tick_index"] for t in out] == [0, 1, 2]
    assert any("topo_reorder: moved" in w for w in warnings)


def _simulate_store_admission(payload: dict) -> dict:
    """Replicate `viz/src/replay/store.ts::applyTick` admission rules in.

    Python so we can assert the final-tick node set matches the static DOT
    rendering without spinning up a browser. Returns a dict counting the
    admitted node kinds (knowledge/strategy/operator/contradiction/
    equivalence) plus admitted edges.
    """
    layout = payload.get("final_layout") or {}
    layout_nodes: dict[str, dict] = layout.get("nodes") or {}

    admitted_ids: set[str] = set()
    admitted_edges: set[tuple] = set()

    def _co_admit_linked(anchor_id: str) -> None:
        entry = layout_nodes.get(anchor_id) or {}
        for k in ("conclusion_id",):
            v = entry.get(k)
            if isinstance(v, str) and v in layout_nodes:
                admitted_ids.add(v)
        for k in ("premise_ids", "variable_ids"):
            for v in entry.get(k) or []:
                if v in layout_nodes:
                    admitted_ids.add(v)

    def _canonical_of(sym: str | None) -> str | None:
        """Resolve action symbol → canonical layout id (strat_<i>/oper_<i>)."""
        if not sym:
            return None
        entry = layout_nodes.get(sym) or {}
        cid = entry.get("canonical_id")
        if cid and cid in layout_nodes:
            return cid
        return sym

    events = payload.get("events", [])
    for tick in payload.get("ticks", []):
        # Mirror the frontend's orphan-tick guard: ticks that don't
        # survive to the final IR are skipped entirely (no node, no
        # edge admission). The CLI flagged these on `survives_to_final`.
        if tick.get("survives_to_final") is False:
            continue
        ev_idx = tick["event_index"]
        if ev_idx >= len(events):
            continue
        ev = events[ev_idx]
        action = tick["action"]
        kind = action.get("action")
        symbol = action.get("symbol")
        canonical_symbol = _canonical_of(symbol)
        delta = ev.get("graph_delta") or {}
        edges = delta.get("edges_added") or []
        nodes_added = {n["id"]: n for n in (delta.get("nodes_added") or [])}

        if kind == "claim":
            if symbol:
                admitted_ids.add(symbol)
            for n in delta.get("nodes_added") or []:
                if (n.get("kind") or "claim") != "claim":
                    continue
                if n["id"].startswith("inquiry:"):
                    continue
                admitted_ids.add(n["id"])
        elif kind == "deduction":
            if canonical_symbol:
                admitted_ids.add(canonical_symbol)
                _co_admit_linked(canonical_symbol)
            for e in edges:
                if e.get("kind") != "deduction":
                    continue
                if not (canonical_symbol and canonical_symbol in layout_nodes):
                    continue
                # Some lkm-to-gaia worker variants emit two-leg edges
                # already (gcn_premise → gfac → gcn_conclusion); others
                # emit a single direct edge (gcn_premise → gcn_conclusion).
                # Translate either form to the canonical
                # (premise → strat → conclusion) by replacing the gfac-
                # endpoint with the canonical symbol.
                src = e["from"]
                tgt = e["to"]
                src_canon = _canonical_of(src) or src
                tgt_canon = _canonical_of(tgt) or tgt
                if src_canon == canonical_symbol:
                    # Outgoing leg (hub → conclusion).
                    admitted_edges.add((canonical_symbol, tgt, "deduction"))
                elif tgt_canon == canonical_symbol:
                    # Incoming leg (premise → hub).
                    admitted_edges.add((src, canonical_symbol, "deduction"))
                else:
                    # Single-leg form: split into two routed legs.
                    admitted_edges.add((src, canonical_symbol, "deduction"))
                    admitted_edges.add((canonical_symbol, tgt, "deduction"))
        elif kind in ("support", "contradiction", "equivalence"):
            if canonical_symbol:
                admitted_ids.add(canonical_symbol)
                _co_admit_linked(canonical_symbol)
            kind_edges = [e for e in edges if e.get("kind") == kind]
            pos = -1
            for a in ev.get("gaia_actions") or []:
                if a.get("action") == kind:
                    pos += 1
                if a is action:
                    break
            if 0 <= pos < len(kind_edges) and kind == "support":
                e = kind_edges[pos]
                if canonical_symbol and canonical_symbol in layout_nodes:
                    src = e["from"]
                    tgt = e["to"]
                    src_canon = _canonical_of(src) or src
                    tgt_canon = _canonical_of(tgt) or tgt
                    if src_canon == canonical_symbol:
                        admitted_edges.add((canonical_symbol, tgt, kind))
                    elif tgt_canon == canonical_symbol:
                        admitted_edges.add((src, canonical_symbol, kind))
                    else:
                        admitted_edges.add((src, canonical_symbol, kind))
                        admitted_edges.add((canonical_symbol, tgt, kind))
        # `prior` admits no node/edge; metadata-only updates ignored.
        _ = nodes_added  # silence linter; kept for parity with store.ts

    # Final-state reconciliation: mirror `store.ts::reconcileFinalLayout`
    # — at the last tick, force-admit every layout-known strat_/oper_
    # entry plus its linked knowledge. The canonical_id collapse already
    # happened at tick time, so we just walk strat_/oper_ entries and
    # admit any that haven't been admitted yet (lossy events, etc.).
    if payload.get("ticks"):
        for nid, entry in layout_nodes.items():
            if entry.get("kind") not in ("strategy", "operator"):
                continue
            if not (nid.startswith("strat_") or nid.startswith("oper_")):
                continue
            if nid in admitted_ids:
                continue
            admitted_ids.add(nid)
            _co_admit_linked(nid)
        # Edge reconciliation: ensure every strat_/oper_ has its
        # premise/variable + conclusion edges admitted, anchored on the
        # canonical layout id (matching the static DOT). Idempotent —
        # duplicates are de-duped by the set semantics.
        for nid, entry in layout_nodes.items():
            if entry.get("kind") not in ("strategy", "operator"):
                continue
            if not (nid.startswith("strat_") or nid.startswith("oper_")):
                continue
            if nid not in admitted_ids:
                continue
            edge_kind = (
                entry.get("operator_type") or "contradiction"
                if entry.get("kind") == "operator"
                else entry.get("strategy_type") or "deduction"
            )
            concl = entry.get("conclusion_id")
            if concl and concl in admitted_ids:
                admitted_edges.add((nid, concl, edge_kind))
            incoming = (
                entry.get("variable_ids")
                if entry.get("kind") == "operator"
                else entry.get("premise_ids")
            )
            for upstream in incoming or []:
                if upstream in admitted_ids:
                    admitted_edges.add((upstream, nid, edge_kind))

    # Bucket admitted ids by what the layout entry says they are. Strategy
    # and operator entries are deduped by `canonical_id` (set by the
    # bridge): each strat_<i>/oper_<i> contributes at most one
    # ellipse/hexagon to the final canvas, regardless of how many event-
    # symbol aliases the bridge admitted at the same coordinates.
    counts = {
        "knowledge": 0,
        "strategy": 0,
        "operator": 0,
        "contradiction": 0,
        "equivalence": 0,
        "unknown": 0,
        "edges": len(admitted_edges),
    }
    for nid in admitted_ids:
        entry = layout_nodes.get(nid) or {}
        ekind = entry.get("kind")
        if ekind == "strategy":
            # Only canonical (strat_<i>) entries contribute; bridged
            # event-symbol aliases would over-count.
            if not nid.startswith("strat_"):
                continue
            counts["strategy"] += 1
        elif ekind == "operator":
            if not nid.startswith("oper_"):
                continue
            otype = entry.get("operator_type")
            counts["operator"] += 1
            if otype == "contradiction":
                counts["contradiction"] += 1
            elif otype == "equivalence":
                counts["equivalence"] += 1
        elif ekind == "knowledge":
            counts["knowledge"] += 1
        else:
            # Inquiry hypotheses, helper claims with no IR mapping, etc.
            # The static DOT excludes inquiry:* nodes too.
            if not nid.startswith("inquiry:"):
                counts["unknown"] += 1
    return counts


def _count_static_dot_shapes(dot_source: str) -> dict:
    """Verify count static dot shapes.

    Parse a Graphviz DOT source and count node shapes / edges. Used to establish the ground-
    truth node set the replay's final state must match.
    """
    box = ellipse = hexagon = 0
    contradiction = equivalence = 0
    for line in dot_source.splitlines():
        if "shape=box" in line:
            box += 1
        elif "shape=ellipse" in line:
            ellipse += 1
        elif "shape=hexagon" in line:
            hexagon += 1
            if "⊗" in line:
                contradiction += 1
            elif "⊙" in line:
                equivalence += 1
    edges = sum(
        1
        for line in dot_source.splitlines()
        if "->" in line and ("[" in line or line.strip().endswith(";"))
    )
    return {
        "knowledge": box,
        "strategy": ellipse,
        "operator": hexagon,
        "contradiction": contradiction,
        "equivalence": equivalence,
        "edges": edges,
    }


def _real_pkg_dir(name: str) -> Path | None:
    """Resolve a real Gaia knowledge package directory for parity tests.

    Returns None when the package isn't present — the caller skips the
    test. We probe a couple of likely locations for the dev packages.
    """
    candidates = [
        Path.home() / "ThisIsDP" / "dev" / name,
    ]
    for p in candidates:
        if (p / "pyproject.toml").is_file():
            return p
    return None


def _final_state_parity(pkg_dir: Path) -> tuple[dict, dict]:
    """Return (static_counts, replay_counts) for *pkg_dir*."""
    from gaia.cli._packages import (
        apply_package_priors,
        compile_loaded_package_artifact,
        ensure_package_env,
        load_gaia_package,
    )
    from gaia.cli.commands._dot import to_dot
    from gaia.cli.commands._graph_json import generate_graph_json
    from gaia.cli.commands._render_priors import param_data_from_ir_metadata
    from gaia.cli.commands.starmap_replay import (
        _read_jsonl,
        _is_replayable,
        ARTIFACTS_SUBDIR,
        GROWTH_LOG_NAME,
        RETRIEVAL_LOG_NAME,
    )

    ensure_package_env(pkg_dir)
    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()
    param_data = param_data_from_ir_metadata(ir)
    exported_ids = {k["id"] for k in ir.get("knowledges", []) if k.get("exported")}
    graph_json = generate_graph_json(
        ir, beliefs_data=None, param_data=param_data, exported_ids=exported_ids
    )
    static_dot = to_dot(graph_json)
    static_counts = _count_static_dot_shapes(static_dot)

    artifacts = pkg_dir / ARTIFACTS_SUBDIR
    retrievals = _read_jsonl(artifacts / RETRIEVAL_LOG_NAME)
    growths = _read_jsonl(artifacts / GROWTH_LOG_NAME)
    retrievals = [e for e in retrievals if _is_replayable(e)]
    growths = [e for e in growths if _is_replayable(e)]

    payload = build_timeline_payload(
        retrievals, growths, package_name=pkg_dir.name, pkg_dir=pkg_dir
    )
    replay_counts = _simulate_store_admission(payload)
    return static_counts, replay_counts


def test_final_state_matches_static_dot_for_2dheg():
    """Verify final state matches static dot for 2dheg.

    Load-bearing parity check: the replay's final-tick node set has the same count of knowledge
    boxes / strategy ellipses / operator hexagons (and the same contradiction-vs-equivalence
    split) as the static DOT from `gaia starmap --format dot` for the 2dheg package.

    Skipped silently when the dev package isn't present locally — this is
    a developer-environment integration test.
    """
    pkg_dir = _real_pkg_dir("twodheg-effective-mass-gaia")
    if pkg_dir is None:
        import pytest as _p

        _p.skip("twodheg-effective-mass-gaia not found at ~/ThisIsDP/dev/")
    static_counts, replay_counts = _final_state_parity(pkg_dir)
    # Final-state parity: counts must match exactly.
    for key in ("knowledge", "strategy", "operator", "contradiction", "equivalence", "edges"):
        assert replay_counts[key] == static_counts[key], (
            f"{key} mismatch: static={static_counts[key]} replay={replay_counts[key]}"
        )


def test_final_state_matches_static_dot_for_lcdm():
    """Same parity check for the lcdm package."""
    pkg_dir = _real_pkg_dir("lcdm-hubble-tension-gaia")
    if pkg_dir is None:
        import pytest as _p

        _p.skip("lcdm-hubble-tension-gaia not found at ~/ThisIsDP/dev/")
    static_counts, replay_counts = _final_state_parity(pkg_dir)
    for key in ("knowledge", "strategy", "operator", "contradiction", "equivalence", "edges"):
        assert replay_counts[key] == static_counts[key], (
            f"{key} mismatch: static={static_counts[key]} replay={replay_counts[key]}"
        )


def test_final_state_matches_static_dot_for_perovskite():
    """Verify final state matches static dot for perovskite.

    Parity check for the perovskite package — the canonical orphan-tick repro. Without
    `survives_to_final`, the seq=39 deduction ticks (`gfac_c33c62750055451d` +
    `gfac_5e7aa7aa12474862`) would pile up at the canvas centre and break parity.
    """
    pkg_dir = _real_pkg_dir("perovskite-arpes-polaron-gaia")
    if pkg_dir is None:
        import pytest as _p

        _p.skip("perovskite-arpes-polaron-gaia not found at ~/ThisIsDP/dev/")
    static_counts, replay_counts = _final_state_parity(pkg_dir)
    for key in ("knowledge", "strategy", "operator", "contradiction", "equivalence", "edges"):
        assert replay_counts[key] == static_counts[key], (
            f"{key} mismatch: static={static_counts[key]} replay={replay_counts[key]}"
        )


def test_build_timeline_payload_drops_retry_and_failure_events():
    retrievals = [
        _ev("a", 1, "2026-05-05T00:00:00.000Z", channel="support", response_code=0),
        # Failure: response_code != 0 — must be dropped.
        _ev("a", 2, "2026-05-05T00:00:01.000Z", channel="support", response_code=500),
        # Retry: retry_of_event_id set — must be dropped.
        _ev(
            "a",
            3,
            "2026-05-05T00:00:02.000Z",
            channel="support",
            response_code=0,
            retry_of_event_id="2026-05-05T00:00:01.000Z__a__support__2",
        ),
    ]
    growths = [
        _ev("b", 1, "2026-05-05T00:00:00.500Z", decision="round_open"),
        # Explicit decision == "retry" sentinel.
        _ev("b", 2, "2026-05-05T00:00:01.500Z", decision="retry"),
    ]
    payload = build_timeline_payload(retrievals, growths, package_name="syn")
    assert payload["retrieval_count"] == 1
    assert payload["growth_count"] == 1
    assert payload["package_name"] == "syn"
    # The two surviving events must round-trip into the merged stream,
    # ordered by timestamp (a@0.000 before b@0.500).
    merged_seqs = [(e["actor_id"], e["seq"]) for e in payload["events"]]
    assert merged_seqs == [("a", 1), ("b", 1)]
