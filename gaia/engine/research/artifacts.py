"""Artifact IO for package-native research actions.

This module deliberately stores only audit/provenance state under
``.gaia/research``. Focuses, obligations, and truth-bearing claims stay in the
existing Gaia package and inquiry primitives.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia.engine.inquiry.state import load_state

try:
    import tomllib
except ImportError:  # pragma: no cover - Python <3.11 compatibility.
    import tomli as tomllib  # type: ignore[no-redef]


MANIFEST_SCHEMA_VERSION = 1
EVENT_SCHEMA_VERSION = 1


class ResearchTargetError(RuntimeError):
    """Raised when a target path is not an existing Gaia package."""


@dataclass(frozen=True)
class ResearchPackage:
    """Validated package metadata used by research actions."""

    path: Path
    project_name: str
    import_name: str
    namespace: str


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _derive_import_name(project_name: str) -> str:
    return project_name.removesuffix("-gaia").replace("-", "_")


def scaffold_suggestion(path: str | Path) -> str:
    """Return the Gaia-native scaffold command for a missing package target."""
    target = Path(path)
    name = target.name or "research-package"
    pkg_name = name if name.endswith("-gaia") else f"{name}-gaia"
    return f"gaia pkg scaffold --target {target} --name {pkg_name}"


def load_research_package(path: str | Path) -> ResearchPackage:
    """Validate ``path`` as an existing Gaia package and return metadata."""
    pkg_path = Path(path).resolve()
    pyproject = pkg_path / "pyproject.toml"
    if not pyproject.exists():
        raise ResearchTargetError(
            f"not a Gaia package: {pkg_path}\nNext: {scaffold_suggestion(pkg_path)}"
        )

    with pyproject.open("rb") as f:
        config = tomllib.load(f)

    project = config.get("project", {})
    gaia = config.get("tool", {}).get("gaia", {})
    if gaia.get("type") != "knowledge-package":
        raise ResearchTargetError(
            f"not a Gaia knowledge package: {pkg_path}\nNext: {scaffold_suggestion(pkg_path)}"
        )

    project_name = project.get("name")
    if not isinstance(project_name, str) or not project_name:
        raise ResearchTargetError(
            f"Gaia package is missing [project].name: {pkg_path}\n"
            "Next: fix pyproject.toml, then run gaia build check"
        )

    import_name = _derive_import_name(project_name)
    if not (pkg_path / "src" / import_name).exists() and not (pkg_path / import_name).exists():
        raise ResearchTargetError(
            f"Gaia package source directory for {import_name!r} was not found: {pkg_path}\n"
            "Next: run gaia build check"
        )

    namespace = gaia.get("namespace")
    if not isinstance(namespace, str) or not namespace:
        namespace = import_name

    return ResearchPackage(
        path=pkg_path,
        project_name=project_name,
        import_name=import_name,
        namespace=namespace,
    )


def research_dir(pkg: ResearchPackage) -> Path:
    """Return the package-local research artifact directory."""
    path = pkg.path / ".gaia" / "research"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _manifest_path(pkg: ResearchPackage) -> Path:
    return research_dir(pkg) / "manifest.json"


def _events_path(pkg: ResearchPackage) -> Path:
    return research_dir(pkg) / "events.jsonl"


def _inquiry_snapshot(pkg: ResearchPackage) -> dict[str, Any]:
    state = load_state(pkg.path)
    return {
        "focus": state.focus,
        "focus_kind": state.focus_kind,
        "focus_resolved_id": state.focus_resolved_id,
        "mode": state.mode,
        "open_obligations": len(state.synthetic_obligations),
        "hypotheses": len(state.synthetic_hypotheses),
        "rejections": len(state.synthetic_rejections),
    }


def _package_payload(pkg: ResearchPackage) -> dict[str, Any]:
    return {
        "path": str(pkg.path),
        "project_name": pkg.project_name,
        "import_name": pkg.import_name,
        "namespace": pkg.namespace,
    }


def ensure_research_manifest(pkg: ResearchPackage) -> dict[str, Any]:
    """Create or update the research manifest for ``pkg``."""
    path = _manifest_path(pkg)
    now = _utcnow()
    if path.exists():
        manifest = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(manifest, dict):
            manifest = {}
    else:
        manifest = {
            "schema_version": MANIFEST_SCHEMA_VERSION,
            "created_at": now,
            "events": {"count": 0},
        }

    manifest["schema_version"] = MANIFEST_SCHEMA_VERSION
    manifest["updated_at"] = now
    manifest["package"] = _package_payload(pkg)
    manifest["inquiry"] = _inquiry_snapshot(pkg)
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


def append_research_event(
    pkg: ResearchPackage,
    event: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Append an audit event and update manifest counters."""
    manifest = ensure_research_manifest(pkg)
    record = {
        "schema_version": EVENT_SCHEMA_VERSION,
        "timestamp": _utcnow(),
        "event": event,
        "package": _package_payload(pkg),
        "payload": payload,
    }
    events_path = _events_path(pkg)
    with events_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    count = int(manifest.get("events", {}).get("count", 0)) + 1
    manifest["events"] = {"count": count, "last_event": event}
    manifest["updated_at"] = record["timestamp"]
    manifest["inquiry"] = _inquiry_snapshot(pkg)
    _manifest_path(pkg).write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return record
