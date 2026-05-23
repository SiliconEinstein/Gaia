"""Integration tests for the `gaia explore` CLI (SCHEMA.md §7c, build 4a).

These run the real CLI (via Typer's ``CliRunner``) against the hand-authored
``examples/galileo-v0-5-gaia`` fixture — claims + derives + a ``contradict``, no
LKM needed — copied into a tmp dir, compiled and inferred, then explored.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.engine.exploration.state import load_map, read_rounds

pytestmark = pytest.mark.pr_gate

runner = CliRunner()

# A real galileo claim QID — `aristotle_model` is the weight-speed model claim
# referenced by several derives, so it makes a meaningful resolved seed.
GALILEO_NS = "example"
GALILEO_PKG = "galileo_v0_5"


def _galileo_qid(label: str) -> str:
    return f"{GALILEO_NS}:{GALILEO_PKG}::{label}"


def _example_root() -> Path:
    # tests/exploration/ -> repo root -> examples/galileo-v0-5-gaia
    return Path(__file__).resolve().parents[2] / "examples" / "galileo-v0-5-gaia"


@pytest.fixture
def galileo_pkg(tmp_path: Path) -> Path:
    """Copy the galileo example into a tmp dir, compile, and infer it."""
    src = _example_root()
    assert src.is_dir(), f"galileo fixture not found at {src}"
    pkg = tmp_path / "galileo-v0-5-gaia"
    shutil.copytree(src, pkg)

    compile_result = runner.invoke(app, ["build", "compile", str(pkg)])
    assert compile_result.exit_code == 0, compile_result.output

    infer_result = runner.invoke(app, ["run", "infer", str(pkg)])
    assert infer_result.exit_code == 0, infer_result.output

    assert (pkg / ".gaia" / "ir.json").exists()
    assert (pkg / ".gaia" / "beliefs.json").exists()
    return pkg


def test_explore_init_creates_map(galileo_pkg: Path):
    result = runner.invoke(
        app,
        [
            "explore",
            "init",
            str(galileo_pkg),
            "--seed",
            _galileo_qid("aristotle_model"),
            "--doctrine",
            "Surveyor",
        ],
    )
    assert result.exit_code == 0, result.output

    map_path = galileo_pkg / ".gaia" / "exploration" / "map.json"
    assert map_path.exists()
    m = load_map(galileo_pkg)
    assert m.policy.doctrine == "Surveyor"
    assert len(m.seeds) == 1
    assert m.seeds[0]["qid"] == _galileo_qid("aristotle_model")


def test_explore_init_rejects_unknown_doctrine(galileo_pkg: Path):
    result = runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", "x", "--doctrine", "Nonsense"],
    )
    assert result.exit_code == 2
    assert "unknown doctrine" in result.output


def _inject_depends_on_manifest(pkg: Path, target_label: str, given_label: str) -> str:
    """Drop a formalization manifest with an unmaterialized depends_on target.

    The galileo fixture is fully hand-authored (every referenced node is
    materialized), so its IR-derived frontier is legitimately empty. To exercise
    the frontier extract→score→rank path end to end we add a single
    ``depends_on`` scaffold whose conclusion QID is *not* a Knowledge node — the
    canonical way a contact appears (SCHEMA.md §7a; ``lkm_materialize`` lowers
    factors here). The materialized ``given`` becomes the contact's source.

    Returns the unmaterialized contact QID.
    """
    contact_qid = _galileo_qid(target_label)
    manifest = {
        "version": 1,
        "dependencies": [
            {
                "kind": "depends_on",
                "conclusion": contact_qid,
                "given": [_galileo_qid(given_label)],
                "background": [],
            }
        ],
        "materializations": [],
    }
    (pkg / ".gaia" / "formalization_manifest.json").write_text(json.dumps(manifest))
    return contact_qid


def test_galileo_frontier_is_empty_when_fully_materialized(galileo_pkg: Path):
    # Sanity-check the fixture's nature: a complete hand-authored package has no
    # unmaterialized references, so the IR-derived frontier is empty.
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    result = runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "frontier empty" in result.output
    assert load_map(galileo_pkg).frontier == []


def test_explore_frontier_ranks_contacts(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    contact_qid = _inject_depends_on_manifest(
        galileo_pkg, "unmaterialized_factor", "aristotle_model"
    )

    result = runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Frontier:" in result.output
    assert contact_qid in result.output

    m = load_map(galileo_pkg)
    contacts = [c for c in m.frontier if c.ref["value"] == contact_qid]
    assert len(contacts) == 1, "expected the injected depends_on target as a contact"
    contact = contacts[0]
    assert contact.status == "open"
    assert contact.score is not None, "open contact must be scored"
    # Reached via the materialized aristotle_model under the depends_on edge.
    assert any(s["edge"] == "depends_on" for s in contact.sources)


def test_explore_frontier_json_output(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    _inject_depends_on_manifest(galileo_pkg, "unmaterialized_factor", "aristotle_model")
    result = runner.invoke(app, ["explore", "frontier", str(galileo_pkg), "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert isinstance(rows, list)
    assert rows, "expected at least one ranked contact in JSON output"
    for row in rows:
        assert {"id", "ref", "score", "score_features", "sources"} <= set(row)


def test_explore_round_appends_and_detects_keystone(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])

    result = runner.invoke(app, ["explore", "round", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Round 0 complete" in result.output

    rounds = read_rounds(galileo_pkg)
    assert len(rounds) == 1
    assert rounds[0]["round"] == 0

    # The map advanced and snapshotted this round's beliefs as the next baseline.
    m = load_map(galileo_pkg)
    assert m.round == 1
    assert (galileo_pkg / ".gaia" / "exploration" / "beliefs-round-0.json").exists()

    # Galileo's `aristotle_model` underlies several derives -> a keystone fires.
    kinds = {d["kind"] for d in rounds[0]["discoveries"]}
    assert "keystone" in kinds


def test_explore_round_detects_contradiction_on_belief_drop(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])

    # Round 0 snapshots the real beliefs as the baseline for round 1.
    runner.invoke(app, ["explore", "round", str(galileo_pkg)])

    # Hand-perturb beliefs.json downward to simulate a survey that pushed a
    # claim's belief down (galileo's authored contradict + new evidence would do
    # this in the live loop); round 1 must then detect a `contradiction`.
    beliefs_path = galileo_pkg / ".gaia" / "beliefs.json"
    payload = json.loads(beliefs_path.read_text())
    assert payload["beliefs"], "expected galileo to have beliefs"
    dropped_label = None
    for entry in payload["beliefs"]:
        if entry["belief"] >= 0.5:
            dropped_label = entry["knowledge_id"]
            entry["belief"] = max(0.0, entry["belief"] - 0.5)
            break
    assert dropped_label is not None
    beliefs_path.write_text(json.dumps(payload))

    result = runner.invoke(app, ["explore", "round", str(galileo_pkg)])
    assert result.exit_code == 0, result.output

    rounds = read_rounds(galileo_pkg)
    assert len(rounds) == 2
    round1 = rounds[1]
    assert round1["round"] == 1
    contradiction_ids = [
        i for d in round1["discoveries"] if d["kind"] == "contradiction" for i in d["ids"]
    ]
    assert dropped_label in contradiction_ids


def test_explore_round_records_surveyed_and_promotes_contact(galileo_pkg: Path):
    # #4 (SCHEMA §7e): `round --surveyed <qid>` must record the QID into
    # map.surveyed and, when it matches an open contact, promote it. After that,
    # `status` surveyed count and the round log agree.
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    contact_qid = _inject_depends_on_manifest(
        galileo_pkg, "unmaterialized_factor", "aristotle_model"
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])

    # Survey the contact QID.
    result = runner.invoke(app, ["explore", "round", str(galileo_pkg), "--surveyed", contact_qid])
    assert result.exit_code == 0, result.output
    assert "1 surveyed" in result.output

    m = load_map(galileo_pkg)
    # Recorded into map.surveyed.
    assert contact_qid in m.surveyed
    assert m.surveyed[contact_qid].survey_round == 0
    # The matching open contact was promoted (status flipped, kept for legibility).
    promoted = [c for c in m.frontier if c.ref["value"] == contact_qid]
    assert len(promoted) == 1
    assert promoted[0].status == "surveyed"
    assert m.surveyed[contact_qid].promoted_from_contact == promoted[0].id

    # The round log and the surveyed count agree.
    rounds = read_rounds(galileo_pkg)
    assert rounds[0]["surveyed"] == [contact_qid]
    assert len(m.surveyed) == 1


def test_explore_round_records_surveyed_without_contact(galileo_pkg: Path):
    # A surveyed QID with no matching open contact still gets a bare SurveyRecord.
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    bare_qid = _galileo_qid("some_freshly_authored_claim")
    result = runner.invoke(app, ["explore", "round", str(galileo_pkg), "--surveyed", bare_qid])
    assert result.exit_code == 0, result.output
    m = load_map(galileo_pkg)
    assert bare_qid in m.surveyed
    assert m.surveyed[bare_qid].promoted_from_contact is None


def test_explore_frontier_resolves_freetext_seed(galileo_pkg: Path):
    # #3 (SCHEMA §7e): a free-text seed (no `::`) is recorded with qid: null at
    # init; `explore frontier` resolves it against the joint graph (by label) and
    # persists the QID so closeness_to_seed can bite.
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", "aristotle_model"],
    )
    m0 = load_map(galileo_pkg)
    assert m0.seeds[0]["qid"] is None
    assert m0.seeds[0]["kind"] == "question"

    result = runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output

    m1 = load_map(galileo_pkg)
    assert m1.seeds[0]["qid"] == _galileo_qid("aristotle_model")


def test_explore_status_summarizes(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    runner.invoke(app, ["explore", "round", str(galileo_pkg)])

    result = runner.invoke(app, ["explore", "status", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Exploration status" in result.output
    assert "open frontier:" in result.output
    assert "recent rounds:" in result.output
    assert "discovery tallies:" in result.output


def test_explore_frontier_without_init_fails_gracefully(galileo_pkg: Path):
    result = runner.invoke(app, ["explore", "frontier", str(galileo_pkg)])
    assert result.exit_code == 1
    assert "no exploration map" in result.output


def test_explore_help_registers_subapp():
    result = runner.invoke(app, ["explore", "--help"])
    assert result.exit_code == 0
    for verb in ("init", "observe", "frontier", "round", "status"):
        assert verb in result.output


# --------------------------------------------------------------------------- #
# observe — lkm_related ingestion (SCHEMA.md §7f, build 4d)                    #
# --------------------------------------------------------------------------- #

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lkm_search_free_fall.json"


def test_explore_observe_records_lkm_contacts_from_fixture(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    result = runner.invoke(
        app,
        [
            "explore",
            "observe",
            str(galileo_pkg),
            "--source",
            _galileo_qid("aristotle_model"),
            "--query",
            "free fall",
            "--search-json",
            str(_FIXTURE),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "5 new" in result.output

    m = load_map(galileo_pkg)
    lkm = [c for c in m.frontier if c.ref["kind"] == "lkm"]
    assert len(lkm) == 5
    for c in lkm:
        assert c.meta["paper_id"] == c.ref["value"]
        assert {"qid": _galileo_qid("aristotle_model"), "edge": "lkm_related"} in c.sources
        assert c.meta["query"] == "free fall"


def test_explore_observe_reads_stdin(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    payload = _FIXTURE.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        ["explore", "observe", str(galileo_pkg), "--source", _galileo_qid("aristotle_model")],
        input=payload,
    )
    assert result.exit_code == 0, result.output
    m = load_map(galileo_pkg)
    assert len([c for c in m.frontier if c.ref["kind"] == "lkm"]) == 5


def test_explore_observe_dedups_and_skips_materialized(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    # Two rows share paper 'P1'; one row has a resolved gaia.qid (skip); one fresh.
    leads = {
        "results": [
            {
                "id": "lkm:bohrium:gcn_1",
                "gaia": {"qid": None},
                "source": {"paper_id": "P1", "index_id": "bohrium"},
                "rank": {"score": 0.1},
            },
            {
                "id": "lkm:bohrium:gcn_2",
                "gaia": {"qid": None},
                "source": {"paper_id": "P1", "index_id": "bohrium"},
                "rank": {"score": 0.8},
            },
            {
                "id": "lkm:bohrium:gcn_3",
                "gaia": {"qid": _galileo_qid("aristotle_model")},
                "source": {"paper_id": "P2", "index_id": "bohrium"},
                "rank": {"score": 0.5},
            },
        ]
    }
    leads_file = galileo_pkg / "leads.json"
    leads_file.write_text(json.dumps(leads))
    result = runner.invoke(
        app,
        [
            "explore",
            "observe",
            str(galileo_pkg),
            "--source",
            _galileo_qid("aristotle_model"),
            "--search-json",
            str(leads_file),
        ],
    )
    assert result.exit_code == 0, result.output
    m = load_map(galileo_pkg)
    lkm = [c for c in m.frontier if c.ref["kind"] == "lkm"]
    # P1 once (deduped, max rank 0.8); P2 skipped (resolved qid).
    assert {c.ref["value"] for c in lkm} == {"P1"}
    assert lkm[0].meta["rank"] == 0.8


def test_explore_frontier_ranks_lkm_contacts(galileo_pkg: Path):
    runner.invoke(
        app,
        ["explore", "init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(
        app,
        [
            "explore",
            "observe",
            str(galileo_pkg),
            "--source",
            _galileo_qid("aristotle_model"),
            "--query",
            "free fall",
            "--search-json",
            str(_FIXTURE),
        ],
    )
    result = runner.invoke(app, ["explore", "frontier", str(galileo_pkg), "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    lkm_rows = [r for r in rows if r["ref"]["kind"] == "lkm"]
    assert lkm_rows, "expected lkm_related contacts ranked in the frontier"
    for r in lkm_rows:
        assert r["score"] is not None
        feats = r["score_features"]
        assert set(feats) == {
            "belief_entropy",
            "closeness_to_seed",
            "survey_cost",
            "tension_potential",
            "bridge_potential",
            "new_territory",
        }
        # An lkm contact's new_territory is live (>= 0.5) and survey_cost heavier.
        assert feats["new_territory"] >= 0.5
        assert feats["survey_cost"] == 2.0


def test_explore_observe_without_init_fails(galileo_pkg: Path):
    result = runner.invoke(
        app,
        ["explore", "observe", str(galileo_pkg), "--source", "x", "--search-json", str(_FIXTURE)],
    )
    assert result.exit_code == 1
    assert "no exploration map" in result.output
