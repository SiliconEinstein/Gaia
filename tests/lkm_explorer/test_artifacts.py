from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.lkm_explorer.engine.artifacts import (
    SOP_SCHEMA,
    SOP_SCHEMA_V2,
    artifact_id,
    build_exploration_artifact,
    build_focus_context_artifact,
    build_focuses_artifact,
    build_focuses_artifact_from_candidates,
    build_gate_report,
    build_scope_artifact,
    collect_landscape_grounding_refs,
    landscape_round_paths,
    latest_landscape_path,
    parse_dimensions,
    rel_artifact_path,
)


def test_parse_dimensions_groups_repeated_keys() -> None:
    assert parse_dimensions(["population=adults", "population=elderly", "endpoint=mi"]) == {
        "population": ["adults", "elderly"],
        "endpoint": ["mi"],
    }


def test_parse_dimensions_rejects_malformed_items() -> None:
    with pytest.raises(ValueError, match="key=value"):
        parse_dimensions(["population"])


def test_artifact_id_includes_prefix_and_utc_suffix() -> None:
    generated = artifact_id("scope")
    assert generated.startswith("scope_")
    assert generated.endswith("Z")


def test_latest_landscape_path_returns_highest_sorted(tmp_path: Path) -> None:
    exp = tmp_path / ".gaia" / "exploration"
    exp.mkdir(parents=True)
    for name in [
        "landscape-0.json",
        "landscape-2.json",
        "landscape-1.json",
        "landscape-9.json",
        "landscape-10.json",
    ]:
        (exp / name).write_text("{}", encoding="utf-8")

    assert latest_landscape_path(tmp_path) == exp / "landscape-10.json"
    assert landscape_round_paths(tmp_path) == [
        exp / "landscape-0.json",
        exp / "landscape-1.json",
        exp / "landscape-2.json",
        exp / "landscape-9.json",
        exp / "landscape-10.json",
    ]


def test_rel_artifact_path_prefers_package_relative_paths(tmp_path: Path) -> None:
    path = tmp_path / ".gaia" / "exploration" / "scope.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")

    assert rel_artifact_path(tmp_path, path) == ".gaia/exploration/scope.json"
    assert rel_artifact_path(tmp_path, None) is None


def test_build_scope_artifact_records_contract(tmp_path: Path) -> None:
    artifact = build_scope_artifact(
        tmp_path,
        seeds=["aspirin primary prevention"],
        profile="clinical",
        dimensions={"population": ["older adults"]},
        seed_source="cli",
        map_round=3,
    )

    assert artifact["schema"] == SOP_SCHEMA
    assert artifact["kind"] == "exploration_scope"
    assert artifact["inputs"]["pkg"] == str(tmp_path.resolve())
    assert artifact["inputs"]["seeds"] == ["aspirin primary prevention"]
    assert artifact["inputs"]["profile"] == "clinical"
    assert artifact["inputs"]["dimensions"] == {"population": ["older adults"]}
    assert artifact["provenance"]["seed_source"] == "cli"
    assert artifact["provenance"]["map_round"] == 3
    assert artifact["audit"]["allowed_next_steps"] == [
        "landscape",
        "focuses",
        "artifact",
        "gate",
    ]


def test_build_focuses_artifact_uses_landscape_paper_leads(tmp_path: Path) -> None:
    landscape = {
        "kind": "exploration_landscape",
        "paper_leads": [
            {
                "paper_id": "P1",
                "title": "Aspirin for primary prevention",
                "queries": ["aspirin primary prevention"],
                "lkm_node_ids": ["lkm:1", "lkm:2"],
            }
        ],
    }
    artifact = build_focuses_artifact(
        tmp_path,
        scope_path=tmp_path / ".gaia" / "exploration" / "scope.json",
        landscape_path=tmp_path / ".gaia" / "exploration" / "landscape-0.json",
        landscape=landscape,
        map_round=0,
    )

    assert artifact["schema"] == SOP_SCHEMA_V2
    assert artifact["kind"] == "exploration_focuses"
    assert artifact["focuses"]
    focus = artifact["focuses"][0]
    assert focus["kind"] == "paper_lead_cluster"
    assert focus["level"] == "focus"
    assert focus["status"] == "ready_for_assess"
    assert focus["question"].startswith("Assess the paper-lead cluster")
    assert focus["recommended_next"] == "assess"
    assert focus["coverage"]["status"] == "ready_for_assess"
    assert focus["coverage"]["grounded_ref_count"] == 3
    assert focus["evidence_refs"] == [
        {"kind": "paper", "id": "P1"},
        {"kind": "lkm_node", "id": "lkm:1"},
        {"kind": "lkm_node", "id": "lkm:2"},
    ]


def test_build_focuses_artifact_aggregates_landscape_rounds(tmp_path: Path) -> None:
    round_0 = {
        "kind": "exploration_landscape",
        "paper_leads": [
            {
                "paper_id": "P1",
                "title": "Benefit trial",
                "queries": ["aspirin benefit"],
                "lkm_node_ids": ["lkm:benefit"],
            }
        ],
    }
    round_1 = {
        "kind": "exploration_landscape",
        "paper_leads": [
            {
                "paper_id": "P2",
                "title": "Bleeding trial",
                "queries": ["aspirin bleeding"],
                "lkm_node_ids": ["lkm:harm"],
            }
        ],
    }

    artifact = build_focuses_artifact(
        tmp_path,
        scope_path=tmp_path / ".gaia" / "exploration" / "scope.json",
        landscape_path=tmp_path / ".gaia" / "exploration" / "landscape-1.json",
        landscape=round_1,
        landscape_rounds=[
            (tmp_path / ".gaia" / "exploration" / "landscape-0.json", round_0),
            (tmp_path / ".gaia" / "exploration" / "landscape-1.json", round_1),
        ],
        map_round=1,
    )

    focus = artifact["focuses"][0]
    assert artifact["inputs"]["landscape"] == ".gaia/exploration/landscape-1.json"
    assert artifact["inputs"]["landscape_rounds"] == [
        {
            "round": 0,
            "path": ".gaia/exploration/landscape-0.json",
            "paper_leads": 1,
        },
        {
            "round": 1,
            "path": ".gaia/exploration/landscape-1.json",
            "paper_leads": 1,
        },
    ]
    assert focus["evidence_refs"] == [
        {"kind": "paper", "id": "P1"},
        {"kind": "lkm_node", "id": "lkm:benefit"},
        {"kind": "paper", "id": "P2"},
        {"kind": "lkm_node", "id": "lkm:harm"},
    ]
    assert focus["provenance"]["paper_ids"] == ["P1", "P2"]
    assert focus["provenance"]["queries"] == ["aspirin benefit", "aspirin bleeding"]


def test_build_focus_context_artifact_records_grounded_packet(tmp_path: Path) -> None:
    landscape_path = tmp_path / ".gaia" / "exploration" / "landscape-0.json"
    landscape = {
        "kind": "exploration_landscape",
        "queries": [
            {
                "index": 0,
                "query": "aspirin primary prevention",
                "raw_results": 2,
                "paper_leads": 1,
            }
        ],
        "paper_leads": [
            {
                "paper_id": "P1",
                "title": "Benefit trial",
                "doi": "10.1/demo",
                "index_id": "bohrium",
                "best_rank": 0.1,
                "queries": ["aspirin primary prevention"],
                "lkm_node_ids": ["lkm:benefit"],
            }
        ],
    }
    scope = {"kind": "exploration_scope", "inputs": {"seeds": ["aspirin"]}}

    artifact = build_focus_context_artifact(
        tmp_path,
        scope_path=tmp_path / ".gaia" / "exploration" / "scope.json",
        scope=scope,
        landscape_rounds=[(landscape_path, landscape)],
        existing_focuses_path=None,
        existing_focuses=None,
        map_round=0,
    )

    assert artifact["schema"] == SOP_SCHEMA_V2
    assert artifact["kind"] == "focus_synthesis_context"
    assert artifact["scope"] == scope
    assert artifact["landscape_rounds"] == [
        {
            "round": 0,
            "path": ".gaia/exploration/landscape-0.json",
            "purpose": "broad_initial_survey",
            "paper_leads": 1,
        }
    ]
    assert artifact["paper_leads"] == [
        {
            "round": 0,
            "path": ".gaia/exploration/landscape-0.json",
            "paper_id": "P1",
            "title": "Benefit trial",
            "doi": "10.1/demo",
            "index_id": "bohrium",
            "best_rank": 0.1,
            "queries": ["aspirin primary prevention"],
            "lkm_node_ids": ["lkm:benefit"],
        }
    ]
    assert artifact["queries"][0]["query"] == "aspirin primary prevention"
    assert artifact["existing_focuses"] == []
    assert artifact["allowed_evidence_refs"] == [
        {
            "kind": "paper",
            "id": "P1",
            "round": 0,
            "path": ".gaia/exploration/landscape-0.json",
            "title": "Benefit trial",
        },
        {
            "kind": "lkm_node",
            "id": "lkm:benefit",
            "round": 0,
            "path": ".gaia/exploration/landscape-0.json",
            "paper_id": "P1",
            "title": "Benefit trial",
        },
    ]
    assert artifact["output_contract"]["format"] == "json"
    assert "CandidateFocuses" in artifact["output_contract"]["json_schema"]["title"]
    assert (
        "Every evidence_refs[].id must appear in allowed_evidence_refs."
        in artifact["output_contract"]["rules"]
    )
    assert "Propose only focuses grounded in evidence refs." in artifact["instructions"]


def test_build_focuses_artifact_from_candidates_accepts_grounded_llm_focus(
    tmp_path: Path,
) -> None:
    context_path = tmp_path / ".gaia" / "exploration" / "focus_context.json"
    context = {
        "kind": "focus_synthesis_context",
        "inputs": {"scope": ".gaia/exploration/scope.json"},
        "landscape_rounds": [
            {
                "round": 0,
                "path": ".gaia/exploration/landscape-0.json",
                "purpose": "broad_initial_survey",
                "paper_leads": 2,
            }
        ],
        "paper_leads": [
            {"paper_id": "P1", "lkm_node_ids": ["lkm:1"]},
            {"paper_id": "P2", "lkm_node_ids": ["lkm:2"]},
        ],
    }
    candidates = {
        "focuses": [
            {
                "id": "focus_net_benefit",
                "kind": "benefit_harm_tension",
                "question": "Does aspirin primary prevention have net clinical benefit?",
                "status": "ready_for_assess",
                "coverage": {
                    "status": "ready_for_assess",
                    "evidence_families": ["randomized_trial", "meta_analysis"],
                    "missing_dimensions": [],
                },
                "evidence_refs": [
                    {"kind": "paper", "id": "P1", "role": "benefit"},
                    {"kind": "lkm_node", "id": "lkm:2", "role": "harm"},
                ],
                "candidate_claims": [],
                "next_landscape_queries": [],
            }
        ]
    }

    artifact = build_focuses_artifact_from_candidates(
        tmp_path,
        context_path=context_path,
        context=context,
        candidates=candidates,
        map_round=3,
        generation="llm",
    )

    focus = artifact["focuses"][0]
    assert artifact["schema"] == SOP_SCHEMA_V2
    assert artifact["inputs"]["focus_context"] == ".gaia/exploration/focus_context.json"
    assert artifact["inputs"]["landscape_rounds"][0]["round"] == 0
    assert artifact["provenance"]["generation"] == "llm"
    assert focus["level"] == "focus"
    assert focus["recommended_next"] == "assess"
    assert focus["text"] == focus["question"]
    assert focus["provenance"]["focus_context"] == ".gaia/exploration/focus_context.json"
    assert focus["provenance"]["grounded_ref_count"] == 2
    assert focus["evidence_refs"] == candidates["focuses"][0]["evidence_refs"]


def test_build_focuses_artifact_from_candidates_rejects_ungrounded_refs(
    tmp_path: Path,
) -> None:
    context = {
        "paper_leads": [{"paper_id": "P1", "lkm_node_ids": ["lkm:1"]}],
        "landscape_rounds": [],
    }
    candidates = {
        "focuses": [
            {
                "id": "focus_bad",
                "kind": "unsupported_tension",
                "question": "Is this grounded?",
                "status": "ready_for_assess",
                "coverage": {"status": "ready_for_assess"},
                "evidence_refs": [{"kind": "paper", "id": "P2"}],
                "candidate_claims": [],
                "next_landscape_queries": [],
            }
        ]
    }

    with pytest.raises(ValueError, match="ungrounded evidence refs"):
        build_focuses_artifact_from_candidates(
            tmp_path,
            context_path=tmp_path / ".gaia" / "exploration" / "focus_context.json",
            context=context,
            candidates=candidates,
            map_round=0,
            generation="llm",
        )


def test_build_exploration_artifact_records_present_and_missing_sidecars(tmp_path: Path) -> None:
    exp = tmp_path / ".gaia" / "exploration"
    exp.mkdir(parents=True)
    (exp / "scope.json").write_text("{}", encoding="utf-8")
    (exp / "landscape-0.json").write_text("{}", encoding="utf-8")
    (exp / "landscape-1.json").write_text("{}", encoding="utf-8")
    (exp / "map.json").write_text("{}", encoding="utf-8")

    artifact = build_exploration_artifact(tmp_path, map_round=0, map_version=1)

    assert artifact["kind"] == "lkm_exploration"
    assert artifact["artifacts"]["scope"] == ".gaia/exploration/scope.json"
    assert artifact["artifacts"]["landscape"] == ".gaia/exploration/landscape-1.json"
    assert artifact["landscape_rounds"] == [
        {
            "round": 0,
            "path": ".gaia/exploration/landscape-0.json",
            "purpose": "broad_initial_survey",
        },
        {
            "round": 1,
            "path": ".gaia/exploration/landscape-1.json",
            "purpose": "focus_gap_followup",
        },
    ]
    assert artifact["artifacts"]["focuses"] is None
    assert artifact["artifacts"]["focus_context"] is None
    assert artifact["schema"] == SOP_SCHEMA_V2
    assert artifact["focus_statuses"] == []
    assert artifact["audit"]["coverage"]["budget_exhaustion"] == "not_evaluated"
    assert artifact["audit"]["coverage"]["paper_level_gaps"] == []
    assert artifact["audit"]["coverage"]["claim_level_gaps"] == [
        "compiled IR missing",
        "beliefs sidecar missing",
    ]
    assert "missing focuses.json" in artifact["audit"]["known_limitations"]
    assert artifact["audit"]["allowed_next_steps"] == ["gate"]
    assert "gaia-evidence assess" in artifact["interface"]["assess"]["command"]
    assert artifact["interface"]["assess"]["focus_commands"] == []


def test_build_exploration_artifact_records_focus_statuses_and_assess_commands(
    tmp_path: Path,
) -> None:
    exp = tmp_path / ".gaia" / "exploration"
    exp.mkdir(parents=True)
    (exp / "scope.json").write_text("{}", encoding="utf-8")
    (exp / "landscape-0.json").write_text("{}", encoding="utf-8")
    (exp / "map.json").write_text("{}", encoding="utf-8")
    focuses = {
        "schema": SOP_SCHEMA_V2,
        "focuses": [
            {
                "id": "focus_1",
                "status": "ready_for_assess",
                "question": "What is the net clinical benefit?",
                "coverage": {"status": "ready_for_assess"},
                "provenance": {},
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
            },
            {
                "id": "focus_2",
                "status": "needs_more_landscape",
                "question": "What is missing in older adults?",
                "coverage": {"missing_dimensions": ["older adults"]},
                "next_landscape_queries": ["aspirin primary prevention older adults"],
                "evidence_refs": [],
            },
        ],
    }

    artifact = build_exploration_artifact(
        tmp_path,
        map_round=2,
        map_version=1,
        focuses=focuses,
    )

    assert artifact["focus_statuses"] == [
        {
            "id": "focus_1",
            "status": "ready_for_assess",
            "recommended_next": "assess",
            "evidence_refs": 1,
        },
        {
            "id": "focus_2",
            "status": "needs_more_landscape",
            "recommended_next": "landscape",
            "evidence_refs": 0,
        },
    ]
    assert artifact["interface"]["assess"]["focus_commands"] == [
        "gaia-evidence assess --exploration .gaia/exploration/artifact.json --focus focus_1"
    ]


def test_collect_landscape_grounding_refs_indexes_all_round_refs() -> None:
    refs = collect_landscape_grounding_refs(
        [
            {
                "paper_leads": [
                    {"paper_id": "P1", "lkm_node_ids": ["lkm:1", "lkm:2"]},
                    {"paper_id": "P2", "lkm_node_ids": []},
                ]
            },
            {"paper_leads": [{"paper_id": "P3", "lkm_node_ids": ["lkm:3"]}]},
        ]
    )

    assert refs == {"P1", "P2", "P3", "lkm:1", "lkm:2", "lkm:3"}


def test_build_gate_report_blocks_without_focuses() -> None:
    artifact = {
        "schema": SOP_SCHEMA,
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-0.json",
            "focuses": None,
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": ".gaia/ir.json",
            "beliefs": ".gaia/beliefs.json",
            "rounds": ".gaia/exploration/rounds.jsonl",
        },
    }

    report = build_gate_report(artifact, focuses=None)

    assert report["kind"] == "exploration_gate_report"
    assert report["verdict"] == "block"
    assert report["checks"]["focuses_present"]["status"] == "fail"
    assert report["checks"]["focuses_have_evidence_refs"]["status"] == "skip"
    assert "artifact_present" not in report["checks"]
    assert report["audit"]["allowed_next_steps"] == []


def test_build_gate_report_passes_with_supported_schema_and_backed_focus() -> None:
    artifact = {
        "schema": SOP_SCHEMA,
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-0.json",
            "focuses": ".gaia/exploration/focuses.json",
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": ".gaia/ir.json",
            "beliefs": ".gaia/beliefs.json",
            "rounds": ".gaia/exploration/rounds.jsonl",
        },
    }
    focuses = {
        "schema": SOP_SCHEMA,
        "focuses": [
            {
                "id": "focus_1",
                "status": "ready_for_assess",
                "question": "Should this paper cluster enter assessment?",
                "coverage": {"status": "ready_for_assess"},
                "provenance": {},
                "recommended_next": "assess",
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
            }
        ],
    }

    report = build_gate_report(artifact, focuses, grounding_refs={"P1"})

    assert report["verdict"] == "pass"
    assert report["checks"]["ready_focuses_have_contract"]["status"] == "pass"
    assert report["checks"]["ready_focus_refs_grounded"]["status"] == "pass"
    assert report["checks"]["coverage_budget_recorded"]["status"] == "skip"
    assert report["audit"]["allowed_next_steps"] == ["assess"]


def test_build_gate_report_blocks_ungrounded_ready_focus() -> None:
    artifact = {
        "schema": SOP_SCHEMA_V2,
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-0.json",
            "focuses": ".gaia/exploration/focuses.json",
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": ".gaia/ir.json",
            "beliefs": ".gaia/beliefs.json",
            "rounds": ".gaia/exploration/rounds.jsonl",
        },
    }
    focuses = {
        "schema": SOP_SCHEMA_V2,
        "focuses": [
            {
                "id": "focus_1",
                "status": "ready_for_assess",
                "question": "Should this paper cluster enter assessment?",
                "coverage": {"status": "ready_for_assess"},
                "provenance": {},
                "evidence_refs": [{"kind": "paper", "id": "P2"}],
            }
        ],
    }

    report = build_gate_report(artifact, focuses, grounding_refs={"P1"})

    assert report["verdict"] == "block"
    assert report["checks"]["ready_focus_refs_grounded"]["status"] == "fail"
    assert report["validation"]["ungrounded_refs"] == ["P2"]


def test_build_gate_report_requires_v2_coverage_budget_record() -> None:
    artifact = {
        "schema": SOP_SCHEMA_V2,
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-0.json",
            "focuses": ".gaia/exploration/focuses.json",
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": ".gaia/ir.json",
            "beliefs": ".gaia/beliefs.json",
            "rounds": ".gaia/exploration/rounds.jsonl",
        },
        "audit": {"coverage": {}},
    }
    focuses = {
        "schema": SOP_SCHEMA_V2,
        "focuses": [
            {
                "id": "focus_1",
                "status": "ready_for_assess",
                "question": "Should this paper cluster enter assessment?",
                "coverage": {"status": "ready_for_assess"},
                "provenance": {},
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
            }
        ],
    }

    report = build_gate_report(artifact, focuses, grounding_refs={"P1"})

    assert report["verdict"] == "block"
    assert report["checks"]["coverage_budget_recorded"]["status"] == "fail"


def test_build_gate_report_accepts_v2_landscape_rounds_as_provenance() -> None:
    artifact = {
        "schema": SOP_SCHEMA_V2,
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-1.json",
            "focuses": ".gaia/exploration/focuses.json",
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": ".gaia/ir.json",
            "beliefs": ".gaia/beliefs.json",
            "rounds": None,
        },
        "landscape_rounds": [
            {
                "round": 0,
                "path": ".gaia/exploration/landscape-0.json",
                "purpose": "broad_initial_survey",
            },
            {
                "round": 1,
                "path": ".gaia/exploration/landscape-1.json",
                "purpose": "focus_gap_followup",
            },
        ],
        "audit": {
            "coverage": {
                "paper_level_gaps": [],
                "claim_level_gaps": [],
                "budget_exhaustion": "not_evaluated",
            }
        },
    }
    focuses = {
        "schema": SOP_SCHEMA_V2,
        "focuses": [
            {
                "id": "focus_1",
                "status": "ready_for_assess",
                "question": "Should this paper cluster enter assessment?",
                "coverage": {"status": "ready_for_assess"},
                "provenance": {},
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
            }
        ],
    }

    report = build_gate_report(artifact, focuses, grounding_refs={"P1"})

    assert report["verdict"] == "pass"
    assert report["checks"]["rounds_present"]["status"] == "pass"


def test_build_gate_report_revises_when_warning_artifacts_are_missing() -> None:
    artifact = {
        "schema": SOP_SCHEMA,
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-0.json",
            "focuses": ".gaia/exploration/focuses.json",
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": None,
            "beliefs": None,
            "rounds": None,
        },
    }
    focuses = {
        "schema": SOP_SCHEMA,
        "focuses": [
            {
                "id": "focus_1",
                "status": "ready_for_assess",
                "question": "Should this paper cluster enter assessment?",
                "coverage": {"status": "ready_for_assess"},
                "provenance": {},
                "recommended_next": "assess",
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
            }
        ],
    }

    report = build_gate_report(artifact, focuses)

    assert report["verdict"] == "revise"
    assert report["checks"]["compiled_ir_present"]["status"] == "warn"


def test_build_gate_report_blocks_unsupported_schema() -> None:
    artifact = {
        "schema": "future.schema",
        "kind": "lkm_exploration",
        "artifacts": {
            "scope": ".gaia/exploration/scope.json",
            "landscape": ".gaia/exploration/landscape-0.json",
            "focuses": ".gaia/exploration/focuses.json",
            "map": ".gaia/exploration/map.json",
            "artifact": ".gaia/exploration/artifact.json",
            "gaia_ir": ".gaia/ir.json",
            "beliefs": ".gaia/beliefs.json",
            "rounds": ".gaia/exploration/rounds.jsonl",
        },
    }
    focuses = {"schema": SOP_SCHEMA, "focuses": []}

    report = build_gate_report(artifact, focuses)

    assert report["verdict"] == "block"
    assert report["checks"]["schema_versions_supported"]["status"] == "fail"


def test_gate_report_is_json_serializable() -> None:
    report = build_gate_report(
        {
            "schema": SOP_SCHEMA,
            "kind": "lkm_exploration",
            "artifacts": {},
        },
        focuses=None,
    )

    json.dumps(report)
