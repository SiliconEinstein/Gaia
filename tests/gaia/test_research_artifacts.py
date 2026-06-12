"""Unit tests for research artifact persistence."""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from gaia.engine.inquiry.state import load_state
from gaia.engine.research.artifacts import (
    ResearchPackage,
    append_research_event,
    ensure_research_manifest,
    write_research_artifact,
)
from gaia.engine.research.sync import ResearchSyncSourceError, sync_assessment_artifact


def _pkg(path: Path) -> ResearchPackage:
    return ResearchPackage(
        path=path,
        project_name="research-demo-gaia",
        import_name="research_demo",
        namespace="research_demo",
    )


def _assessment_with_obligation(*, actionable: bool | None = None) -> dict[str, object]:
    obligation: dict[str, object] = {
        "kind": "needs_more_evidence",
        "content": "需要更深的纸面核查。",
        "source_refs": [{"kind": "variable", "id": "v1"}],
    }
    if actionable is not None:
        obligation["actionable"] = actionable
    return {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "relations": [],
        "candidate_obligations": [obligation],
    }


def test_research_manifest_updates_use_atomic_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_write_text = Path.write_text

    def guarded_write_text(self: Path, *args: Any, **kwargs: Any) -> int:
        if self.name == "manifest.json":
            raise AssertionError("manifest.json must be updated through atomic replace")
        return original_write_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", guarded_write_text)
    pkg = _pkg(tmp_path)

    manifest = ensure_research_manifest(pkg)
    append_research_event(pkg, "demo.event", {"ok": True})
    artifact_path = write_research_artifact(pkg, "demos", "demo", {"kind": "demo"})

    manifest_path = tmp_path / ".gaia" / "research" / "manifest.json"
    persisted = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 1
    assert persisted["events"]["last_event"] == "demo.event"
    assert persisted["artifacts"][-1]["path"] == str(artifact_path)


def test_assessment_obligations_default_to_deferred_gaps(tmp_path: Path) -> None:
    result = sync_assessment_artifact(
        _pkg(tmp_path),
        _assessment_with_obligation(),
        source_writes=False,
    )

    assert result.obligations_added == []
    assert len(result.obligations_deferred) == 1
    assert load_state(tmp_path).synthetic_obligations == []


def test_actionable_assessment_obligation_writes_open_inquiry_item(tmp_path: Path) -> None:
    result = sync_assessment_artifact(
        _pkg(tmp_path),
        _assessment_with_obligation(actionable=True),
        source_writes=False,
    )

    assert len(result.obligations_added) == 1
    assert result.obligations_deferred == []
    obligations = load_state(tmp_path).synthetic_obligations
    assert len(obligations) == 1
    assert obligations[0].target_qid == "focus_1"


def test_assessment_sync_rejects_unparseable_authored_source(tmp_path: Path) -> None:
    assessment = {
        "kind": "assessment",
        "focus": {"kind": "focus", "id": "focus_1"},
        "evidence_packet": {"items": []},
        "relations": [
            {
                "id": "bad_foreign_ref",
                "type": "opposes",
                "claim": "An invalid foreign ref must not leave broken authored source.",
                "claim_refs": ["lkm:bad-module::seed", "seed_alt"],
            }
        ],
        "candidate_obligations": [],
    }

    with pytest.raises(ResearchSyncSourceError, match="authored source is not parseable"):
        sync_assessment_artifact(_pkg(tmp_path), assessment)
    authored_source = (tmp_path / "research_demo" / "authored" / "__init__.py").read_text(
        encoding="utf-8"
    )
    ast.parse(authored_source)
    assert "bad-module" not in authored_source
    assert "candidate_relation(" not in authored_source
