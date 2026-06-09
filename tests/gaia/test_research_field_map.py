"""Unit tests for research field-map artifacts."""

from __future__ import annotations

import pytest

from gaia.engine.research.field_map import (
    FieldMapSchemaError,
    build_field_map_artifact,
)


def test_build_field_map_artifact_validates_review_buckets() -> None:
    artifact = build_field_map_artifact(
        topic="DQCP evidence assessment",
        landscapes=[{"kind": "research_landscape", "action": "explore.scan"}],
        language="zh",
        analysis={
            "domain_thesis": "DQCP 证据横跨晶格数值、场论约束和实验近邻体系。",
            "buckets": [
                {
                    "id": "canonical_lattice_models",
                    "title": "Canonical lattice models",
                    "role": "historical and numerical backbone",
                    "required_for_review": True,
                    "coverage_status": "partial",
                    "evidence_refs": [{"kind": "query", "query_index": 0}],
                    "recommended_queries": ["square lattice J-Q scaling violations"],
                }
            ],
            "controversy_axes": ["continuous DQCP versus weak first-order"],
            "coverage_gaps": [
                {
                    "kind": "missing_experiment",
                    "description": "实验近邻 DQCP 体系尚未覆盖。",
                    "recommended_queries": ["SrCu2(BO3)2 proximate DQCP"],
                }
            ],
            "recommended_expansions": ["SrCu2(BO3)2 proximate DQCP"],
            "synthesis_notes": ["先建领域地图，再选择 focus。"],
        },
    )

    assert artifact["kind"] == "field_map"
    assert artifact["topic"] == "DQCP evidence assessment"
    assert artifact["buckets"][0]["id"] == "canonical_lattice_models"
    assert artifact["coverage_gaps"][0]["kind"] == "missing_experiment"


def test_build_field_map_artifact_rejects_empty_buckets() -> None:
    with pytest.raises(FieldMapSchemaError, match="buckets must not be empty"):
        build_field_map_artifact(
            topic="DQCP evidence assessment",
            landscapes=[],
            language="zh",
            analysis={
                "domain_thesis": "No map.",
                "buckets": [],
                "controversy_axes": [],
                "coverage_gaps": [],
                "recommended_expansions": [],
                "synthesis_notes": [],
            },
        )
