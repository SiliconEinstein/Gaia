"""Unit tests for research artifact persistence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gaia.engine.research.artifacts import (
    ResearchPackage,
    append_research_event,
    ensure_research_manifest,
    write_research_artifact,
)


def _pkg(path: Path) -> ResearchPackage:
    return ResearchPackage(
        path=path,
        project_name="research-demo-gaia",
        import_name="research_demo",
        namespace="research_demo",
    )


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
