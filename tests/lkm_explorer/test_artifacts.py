from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.lkm_explorer.engine.artifacts import (
    SOP_SCHEMA,
    artifact_id,
    build_exploration_artifact,
    build_focuses_artifact,
    build_gate_report,
    build_scope_artifact,
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
    for name in ["landscape-0.json", "landscape-2.json", "landscape-1.json"]:
        (exp / name).write_text("{}", encoding="utf-8")

    assert latest_landscape_path(tmp_path) == exp / "landscape-2.json"


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

    assert artifact["kind"] == "exploration_focuses"
    assert artifact["focuses"]
    focus = artifact["focuses"][0]
    assert focus["kind"] == "paper_lead_cluster"
    assert focus["recommended_next"] == "assess"
    assert focus["evidence_refs"] == [
        {"kind": "paper", "id": "P1"},
        {"kind": "lkm_node", "id": "lkm:1"},
        {"kind": "lkm_node", "id": "lkm:2"},
    ]


def test_build_exploration_artifact_records_present_and_missing_sidecars(tmp_path: Path) -> None:
    exp = tmp_path / ".gaia" / "exploration"
    exp.mkdir(parents=True)
    (exp / "scope.json").write_text("{}", encoding="utf-8")
    (exp / "landscape-0.json").write_text("{}", encoding="utf-8")
    (exp / "map.json").write_text("{}", encoding="utf-8")

    artifact = build_exploration_artifact(tmp_path, map_round=0, map_version=1)

    assert artifact["kind"] == "lkm_exploration"
    assert artifact["artifacts"]["scope"] == ".gaia/exploration/scope.json"
    assert artifact["artifacts"]["landscape"] == ".gaia/exploration/landscape-0.json"
    assert artifact["artifacts"]["focuses"] is None
    assert "missing focuses.json" in artifact["audit"]["known_limitations"]
    assert artifact["audit"]["allowed_next_steps"] == ["gate"]
    assert "gaia-evidence assess" in artifact["interface"]["assess"]["command"]


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
                "recommended_next": "assess",
                "evidence_refs": [{"kind": "paper", "id": "P1"}],
            }
        ],
    }

    report = build_gate_report(artifact, focuses)

    assert report["verdict"] == "pass"
    assert report["audit"]["allowed_next_steps"] == ["assess"]


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
