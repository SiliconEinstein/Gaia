"""Integration tests for the `gaia-lkm-explore` engine verbs (SCHEMA.md §7c).

These run the real client CLI (via Typer's ``CliRunner``) against the
hand-authored ``examples/galileo-v0-5-gaia`` fixture — claims + derives + a
``contradict``, no LKM needed — copied into a tmp dir, compiled and inferred
(via the ``gaia`` CLI), then explored. As of build 7 (CLIENT.md "Unified
surface") the engine verbs live on the ``gaia-lkm-explore`` client, not the
removed ``gaia explore`` sub-app.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app as gaia_app
from gaia.lkm_explorer.client.cli import app
from gaia.lkm_explorer.engine.state import load_map, read_rounds

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

    compile_result = runner.invoke(gaia_app, ["build", "compile", str(pkg)])
    assert compile_result.exit_code == 0, compile_result.output

    infer_result = runner.invoke(gaia_app, ["run", "infer", str(pkg)])
    assert infer_result.exit_code == 0, infer_result.output

    assert (pkg / ".gaia" / "ir.json").exists()
    assert (pkg / ".gaia" / "beliefs.json").exists()
    return pkg


def test_explore_init_creates_map(galileo_pkg: Path):
    result = runner.invoke(
        app,
        [
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
        ["init", str(galileo_pkg), "--seed", "x", "--doctrine", "Nonsense"],
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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    result = runner.invoke(app, ["frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "frontier empty" in result.output
    assert load_map(galileo_pkg).frontier == []


def test_explore_frontier_ranks_contacts(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    contact_qid = _inject_depends_on_manifest(
        galileo_pkg, "unmaterialized_factor", "aristotle_model"
    )

    result = runner.invoke(app, ["frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Frontier:" in result.output
    assert contact_qid in result.output
    assert "why:" in result.output

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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    _inject_depends_on_manifest(galileo_pkg, "unmaterialized_factor", "aristotle_model")
    result = runner.invoke(app, ["frontier", str(galileo_pkg), "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    assert isinstance(rows, list)
    assert rows, "expected at least one ranked contact in JSON output"
    for row in rows:
        # Build 11 steer 4: the agent-facing frontier JSON keeps the non-belief
        # surface but hides the belief math — no raw ``score`` row key, and no
        # ``belief_entropy`` inside ``score_features``.
        assert {"id", "ref", "score_features", "sources", "recommendation"} <= set(row)
        assert "score" not in row
        assert "belief_entropy" not in row["score_features"]
        assert row["recommendation"]


def test_explore_frontier_applies_obligations_like_turn(galileo_pkg: Path):
    """Build 12 (CLIENT.md steer 3): the `frontier` verb agrees with `turn`.

    Mirrors ``test_idle_turn_loads_obligations_and_boosts_matching_contact`` in
    test_orchestrator.py but for the standalone verb: a contact whose ref QID
    matches an open synthetic obligation's ``target_qid`` must score
    ``obligation_pressure == 1.0`` (not ``0.0``), so the verb does not mislead.
    """
    from gaia.engine.inquiry.state import (
        InquiryState,
        SyntheticObligation,
        save_state,
    )

    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    contact_qid = _inject_depends_on_manifest(
        galileo_pkg, "unmaterialized_factor", "aristotle_model"
    )

    # An open obligation about the contact's QID — persisted via the real inquiry
    # state writer (no hand-parsed JSON), exactly as the orchestrator test does.
    save_state(
        galileo_pkg,
        InquiryState(
            synthetic_obligations=[
                SyntheticObligation(
                    qid="oblig_frontier",
                    target_qid=contact_qid,
                    content="show the keystone holds",
                )
            ]
        ),
    )

    # Non-JSON path: the contact is scored with obligation_pressure folded in.
    result = runner.invoke(app, ["frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    m = load_map(galileo_pkg)
    contact = next(c for c in m.frontier if c.ref["value"] == contact_qid)
    assert contact.score_features["obligation_pressure"] == 1.0

    # --json path: obligation_pressure stays in the agent-facing score_features
    # (it is NOT a belief key — it must survive sanitization).
    json_result = runner.invoke(app, ["frontier", str(galileo_pkg), "--json"])
    assert json_result.exit_code == 0, json_result.output
    rows = json.loads(json_result.output)
    row = next(r for r in rows if r["ref"]["value"] == contact_qid)
    assert row["score_features"]["obligation_pressure"] == 1.0


def test_status_reflects_closed_obligation_without_re_rank(galileo_pkg: Path):
    """`status` must not show a just-closed obligation as still pressing.

    After `frontier` scored a contact's obligation_pressure to 1.0, closing the
    obligation (removing it from inquiry state) and running `status` — WITHOUT a
    re-run of `frontier` — must report 0 pressed contacts and drop the
    "[discharges open obligation]" tag, because `status` recomputes pressure
    against the current open obligations on display.
    """
    from gaia.engine.inquiry.state import (
        InquiryState,
        SyntheticObligation,
        save_state,
    )

    runner.invoke(app, ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")])
    contact_qid = _inject_depends_on_manifest(
        galileo_pkg, "unmaterialized_factor", "aristotle_model"
    )
    save_state(
        galileo_pkg,
        InquiryState(
            synthetic_obligations=[
                SyntheticObligation(qid="oblig_x", target_qid=contact_qid, content="show it holds")
            ]
        ),
    )

    # Frontier scores the contact pressed; status reflects it.
    runner.invoke(app, ["frontier", str(galileo_pkg)])
    pressed_status = runner.invoke(app, ["status", str(galileo_pkg)]).output
    assert "1 pressed contact(s)" in pressed_status
    assert "[discharges open obligation]" in pressed_status

    # Close the obligation (delete the row, as `inquiry obligation close` does) —
    # do NOT re-run frontier; the stored score_features still say pressed.
    save_state(galileo_pkg, InquiryState(synthetic_obligations=[]))
    m = load_map(galileo_pkg)
    stale = next(c for c in m.frontier if c.ref["value"] == contact_qid)
    assert stale.score_features["obligation_pressure"] == 1.0  # stale on disk

    # status recomputes pressure on display → no longer pressed.
    closed_status = runner.invoke(app, ["status", str(galileo_pkg)]).output
    assert "0 pressed contact(s)" in closed_status
    assert "[discharges open obligation]" not in closed_status


def test_explore_round_appends_and_detects_keystone(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])

    result = runner.invoke(app, ["round", str(galileo_pkg)])
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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])

    # Round 0 snapshots the real beliefs as the baseline for round 1.
    runner.invoke(app, ["round", str(galileo_pkg)])

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

    result = runner.invoke(app, ["round", str(galileo_pkg)])
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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    contact_qid = _inject_depends_on_manifest(
        galileo_pkg, "unmaterialized_factor", "aristotle_model"
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])

    # Survey the contact QID.
    result = runner.invoke(app, ["round", str(galileo_pkg), "--surveyed", contact_qid])
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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])
    bare_qid = _galileo_qid("some_freshly_authored_claim")
    result = runner.invoke(app, ["round", str(galileo_pkg), "--surveyed", bare_qid])
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
        ["init", str(galileo_pkg), "--seed", "aristotle_model"],
    )
    m0 = load_map(galileo_pkg)
    assert m0.seeds[0]["qid"] is None
    assert m0.seeds[0]["kind"] == "question"

    result = runner.invoke(app, ["frontier", str(galileo_pkg)])
    assert result.exit_code == 0, result.output

    m1 = load_map(galileo_pkg)
    assert m1.seeds[0]["qid"] == _galileo_qid("aristotle_model")


def test_explore_status_summarizes(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["frontier", str(galileo_pkg)])
    runner.invoke(app, ["round", str(galileo_pkg)])

    result = runner.invoke(app, ["status", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "Exploration status" in result.output
    assert "open frontier:" in result.output
    assert "recent rounds:" in result.output
    assert "discovery tallies:" in result.output


def test_status_and_render_agree_on_frontier_vocabulary(galileo_pkg: Path):
    # `status` and `render` must label the open frontier with the same
    # paper/claim split so the two surfaces never appear to disagree.
    runner.invoke(app, ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")])
    runner.invoke(app, ["frontier", str(galileo_pkg)])

    status_out = runner.invoke(app, ["status", str(galileo_pkg)]).output
    assert "open frontier:" in status_out
    assert "paper" in status_out and "claim" in status_out

    render_out = runner.invoke(app, ["render", str(galileo_pkg)]).output
    assert "open frontier contact(s) drawn in fog" in render_out
    assert "paper" in render_out and "claim" in render_out
    # `render` no longer mislabels the fog as "frontier paper(s)".
    assert "frontier paper(s) in fog" not in render_out


def test_explore_frontier_without_init_fails_gracefully(galileo_pkg: Path):
    result = runner.invoke(app, ["frontier", str(galileo_pkg)])
    assert result.exit_code == 1
    assert "no exploration map" in result.output


def test_explore_help_lists_all_verbs():
    # The unified `gaia-lkm-explore` client lists the migrated engine verbs
    # alongside the orchestrator `turn` (CLIENT.md "Unified surface", build 7).
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for verb in (
        "init",
        "scope",
        "observe",
        "landscape",
        "focuses",
        "artifact",
        "gate",
        "frontier",
        "round",
        "status",
        "render",
        "turn",
    ):
        assert verb in result.output


def test_gaia_cli_no_longer_lists_explore():
    # `gaia explore` is removed from the gaia CLI (build 7): `gaia --help` must
    # not list it, and `gaia explore` must error as an unknown command.
    help_result = runner.invoke(gaia_app, ["--help"])
    assert help_result.exit_code == 0
    assert "explore" not in help_result.output
    unknown = runner.invoke(gaia_app, ["explore", "status", "."])
    assert unknown.exit_code != 0


# --------------------------------------------------------------------------- #
# observe — lkm_related ingestion (SCHEMA.md §7f, build 4d)                    #
# --------------------------------------------------------------------------- #

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "lkm_search_free_fall.json"


def test_explore_observe_records_lkm_contacts_from_fixture(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    result = runner.invoke(
        app,
        [
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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    payload = _FIXTURE.read_text(encoding="utf-8")
    result = runner.invoke(
        app,
        ["observe", str(galileo_pkg), "--source", _galileo_qid("aristotle_model")],
        input=payload,
    )
    assert result.exit_code == 0, result.output
    m = load_map(galileo_pkg)
    assert len([c for c in m.frontier if c.ref["kind"] == "lkm"]) == 5


def test_explore_landscape_writes_neutral_paper_leads(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    out = galileo_pkg / ".gaia" / "exploration" / "custom-landscape.json"
    result = runner.invoke(
        app,
        [
            "landscape",
            str(galileo_pkg),
            "--search-json",
            str(_FIXTURE),
            "--search-json",
            str(_FIXTURE),
            "--source",
            _galileo_qid("aristotle_model"),
            "--out",
            str(out),
        ],
    )
    assert result.exit_code == 0, result.output
    assert "2 query batch(es)" in result.output
    assert "5 paper lead(s)" in result.output

    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["kind"] == "exploration_landscape"
    assert payload["stats"]["query_batches"] == 2
    assert payload["stats"]["raw_results"] == 10
    assert payload["stats"]["paper_leads"] == 5
    assert len(payload["recommended_pull_order"]) == 5
    assert "Paper leads are topic-neutral" in payload["notes"][0]

    # Landscape is a staging artifact, not observe: it does not mutate the map
    # frontier or import field-specific paper classifications.
    assert load_map(galileo_pkg).frontier == []
    first = payload["paper_leads"][0]
    assert {"paper_id", "best_rank", "queries", "lkm_node_ids"} <= set(first)
    assert "pico" not in first
    assert "evidence_hierarchy" not in first


def test_explore_scope_writes_scope_artifact(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    result = runner.invoke(
        app,
        [
            "scope",
            str(galileo_pkg),
            "--seed",
            "aspirin primary prevention",
            "--profile",
            "clinical",
            "--dimension",
            "population=adults",
            "--dimension",
            "endpoint=mi",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Scope:" in result.output

    payload = json.loads(
        (galileo_pkg / ".gaia" / "exploration" / "scope.json").read_text(encoding="utf-8")
    )
    assert payload["kind"] == "exploration_scope"
    assert payload["inputs"]["seeds"] == ["aspirin primary prevention"]
    assert payload["inputs"]["profile"] == "clinical"
    assert payload["inputs"]["dimensions"] == {
        "population": ["adults"],
        "endpoint": ["mi"],
    }
    assert payload["provenance"]["seed_source"] == "cli"


def test_explore_scope_derives_seeds_from_map(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )

    result = runner.invoke(app, ["scope", str(galileo_pkg)])

    assert result.exit_code == 0, result.output
    payload = json.loads(
        (galileo_pkg / ".gaia" / "exploration" / "scope.json").read_text(encoding="utf-8")
    )
    assert payload["inputs"]["seeds"] == [_galileo_qid("aristotle_model")]
    assert payload["provenance"]["seed_source"] == "map"


def test_explore_scope_rejects_invalid_dimension(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )

    result = runner.invoke(app, ["scope", str(galileo_pkg), "--dimension", "population"])

    assert result.exit_code == 2
    assert "key=value" in result.output


def test_explore_scope_help_lists_options():
    result = runner.invoke(app, ["scope", "--help"])

    assert result.exit_code == 0, result.output
    assert "--seed" in result.output
    assert "--profile" in result.output
    assert "--dimension" in result.output


def test_explore_focuses_writes_focuses_from_landscape(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    landscape_result = runner.invoke(
        app,
        ["landscape", str(galileo_pkg), "--search-json", str(_FIXTURE)],
    )
    assert landscape_result.exit_code == 0, landscape_result.output

    result = runner.invoke(app, ["focuses", str(galileo_pkg)])

    assert result.exit_code == 0, result.output
    assert "Focuses:" in result.output
    payload = json.loads(
        (galileo_pkg / ".gaia" / "exploration" / "focuses.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["kind"] == "exploration_focuses"
    assert payload["focuses"]
    focus = payload["focuses"][0]
    assert focus["kind"] == "paper_lead_cluster"
    assert focus["recommended_next"] == "assess"
    assert focus["evidence_refs"]


def test_explore_focuses_requires_landscape(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )

    result = runner.invoke(app, ["focuses", str(galileo_pkg)])

    assert result.exit_code == 2
    assert "no landscape" in result.output


def test_explore_artifact_writes_handoff_envelope(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["scope", str(galileo_pkg)])
    runner.invoke(app, ["landscape", str(galileo_pkg), "--search-json", str(_FIXTURE)])
    runner.invoke(app, ["focuses", str(galileo_pkg)])

    result = runner.invoke(app, ["artifact", str(galileo_pkg)])

    assert result.exit_code == 0, result.output
    assert "Artifact:" in result.output
    assert "gaia-evidence assess" in result.output
    payload = json.loads(
        (galileo_pkg / ".gaia" / "exploration" / "artifact.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["kind"] == "lkm_exploration"
    assert payload["artifacts"]["scope"] == ".gaia/exploration/scope.json"
    assert payload["artifacts"]["focuses"] == ".gaia/exploration/focuses.json"
    assert payload["artifacts"]["artifact"] == ".gaia/exploration/artifact.json"
    assert payload["interface"]["assess"]["command"].startswith("gaia-evidence assess")


def test_explore_gate_blocks_without_focuses(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["scope", str(galileo_pkg)])
    runner.invoke(app, ["landscape", str(galileo_pkg), "--search-json", str(_FIXTURE)])
    runner.invoke(app, ["artifact", str(galileo_pkg)])

    result = runner.invoke(app, ["gate", str(galileo_pkg)])

    assert result.exit_code == 1
    assert "Gate: block" in result.output
    payload = json.loads(
        (galileo_pkg / ".gaia" / "exploration" / "gate_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["verdict"] == "block"
    assert payload["checks"]["focuses_present"]["status"] == "fail"


def test_explore_gate_passes_with_complete_assessable_artifacts(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(app, ["scope", str(galileo_pkg)])
    runner.invoke(app, ["landscape", str(galileo_pkg), "--search-json", str(_FIXTURE)])
    runner.invoke(app, ["focuses", str(galileo_pkg)])
    (galileo_pkg / ".gaia" / "exploration" / "rounds.jsonl").write_text(
        "{}\n", encoding="utf-8"
    )
    runner.invoke(app, ["artifact", str(galileo_pkg)])

    result = runner.invoke(app, ["gate", str(galileo_pkg)])

    assert result.exit_code == 0, result.output
    assert "Gate: pass" in result.output
    payload = json.loads(
        (galileo_pkg / ".gaia" / "exploration" / "gate_report.json").read_text(
            encoding="utf-8"
        )
    )
    assert payload["verdict"] == "pass"
    assert payload["audit"]["allowed_next_steps"] == ["assess"]


def test_explore_observe_dedups_and_skips_materialized(galileo_pkg: Path):
    runner.invoke(
        app,
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
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
        ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")],
    )
    runner.invoke(
        app,
        [
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
    result = runner.invoke(app, ["frontier", str(galileo_pkg), "--json"])
    assert result.exit_code == 0, result.output
    rows = json.loads(result.output)
    lkm_rows = [r for r in rows if r["ref"]["kind"] == "lkm"]
    assert lkm_rows, "expected lkm_related contacts ranked in the frontier"
    for r in lkm_rows:
        # Build 11 steer 4: the raw belief-weighted score is hidden, and
        # belief_entropy is stripped from the agent-facing score_features; the
        # non-belief signals survive — including build-12 obligation_pressure,
        # which is intentionally agent-visible (CLIENT.md steer 3).
        assert "score" not in r
        feats = r["score_features"]
        assert set(feats) == {
            "closeness_to_seed",
            "survey_cost",
            "tension_potential",
            "bridge_potential",
            "new_territory",
            "obligation_pressure",
        }
        assert "belief_entropy" not in feats
        # An lkm contact's new_territory is live (>= 0.5) and survey_cost heavier
        # than a qid's flat 1.0 (the bounded LKM_SURVEY_COST — the cost asymmetry
        # was capped so it can't defeat the expansion goal; EXPANSION.md §1).
        from gaia.lkm_explorer.engine.scorer import LKM_SURVEY_COST

        assert feats["new_territory"] >= 0.5
        assert feats["survey_cost"] == LKM_SURVEY_COST
        assert LKM_SURVEY_COST > 1.0


def test_explore_observe_without_init_fails(galileo_pkg: Path):
    result = runner.invoke(
        app,
        ["observe", str(galileo_pkg), "--source", "x", "--search-json", str(_FIXTURE)],
    )
    assert result.exit_code == 1
    assert "no exploration map" in result.output


# --------------------------------------------------------------------------- #
# Phase 3 (EXPANSION.md §3/§4): status connectivity readout                     #
# --------------------------------------------------------------------------- #


def test_status_surfaces_connectivity_and_mode(galileo_pkg: Path):
    """`status` shows mode_select and the MapHealth connectivity readout."""
    runner.invoke(app, ["init", str(galileo_pkg), "--seed", _galileo_qid("aristotle_model")])
    # Build the frontier so there is a joint view + a map to read.
    runner.invoke(app, ["frontier", str(galileo_pkg)])
    result = runner.invoke(app, ["status", str(galileo_pkg)])
    assert result.exit_code == 0, result.output
    assert "mode_select:" in result.output
    assert "connectivity:" in result.output
    # The galileo seed graph is a single connected story → maintainable.
    assert "maintainable" in result.output or "component(s)" in result.output
