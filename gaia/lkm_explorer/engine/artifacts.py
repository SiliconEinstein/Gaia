"""Deterministic Explore SOP sidecar artifacts.

This module is intentionally pure: it builds typed JSON-compatible payloads and
does filesystem discovery for already-written sidecars, but it does not write
files, call LKM, invoke an LLM, or mutate the exploration map.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SOP_SCHEMA = "gaia.sop.artifact.v1"


def utcnow() -> str:
    """Return the current UTC timestamp as a compact JSON-friendly string."""
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def artifact_id(prefix: str) -> str:
    """Create a deterministic-shape artifact id with a UTC suffix."""
    safe_prefix = prefix.strip().replace(" ", "_") or "artifact"
    return f"{safe_prefix}_{utcnow()}"


def parse_dimensions(items: list[str] | None) -> dict[str, list[str]]:
    """Parse repeated ``key=value`` CLI options into grouped dimension lists."""
    dimensions: dict[str, list[str]] = {}
    for item in items or []:
        if "=" not in item:
            raise ValueError(f"dimension must be key=value, got {item!r}")
        key, value = item.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key or not value:
            raise ValueError(f"dimension must be key=value, got {item!r}")
        dimensions.setdefault(key, []).append(value)
    return dimensions


def exploration_dir(pkg: str | Path) -> Path:
    """Return ``<pkg>/.gaia/exploration`` as an absolute path."""
    return Path(pkg).resolve() / ".gaia" / "exploration"


def latest_landscape_path(pkg: str | Path) -> Path | None:
    """Return the highest-round ``landscape-*.json`` sidecar, if any."""
    matches = landscape_round_paths(pkg)
    return matches[-1] if matches else None


def landscape_round_paths(pkg: str | Path) -> list[Path]:
    """Return all ``landscape-*.json`` sidecars sorted by numeric round."""
    exp = exploration_dir(pkg)
    if not exp.exists():
        return []
    return sorted(exp.glob("landscape-*.json"), key=_landscape_sort_key)


def _landscape_sort_key(path: Path) -> tuple[int, str]:
    suffix = path.stem.removeprefix("landscape-")
    try:
        return (int(suffix), "")
    except ValueError:
        return (-1, suffix)


def rel_artifact_path(pkg: str | Path, path: Path | None) -> str | None:
    """Render artifact paths package-relative when they live under ``pkg``."""
    if path is None:
        return None
    resolved_pkg = Path(pkg).resolve()
    resolved_path = Path(path).resolve()
    try:
        return resolved_path.relative_to(resolved_pkg).as_posix()
    except ValueError:
        return str(resolved_path)


def build_scope_artifact(
    pkg: str | Path,
    *,
    seeds: list[str],
    profile: str | None,
    dimensions: dict[str, list[str]],
    seed_source: str,
    map_round: int,
) -> dict[str, Any]:
    """Build an ``exploration_scope`` artifact from explicit or map-derived seeds."""
    payload: dict[str, Any] = {
        "schema": SOP_SCHEMA,
        "kind": "exploration_scope",
        "id": artifact_id("scope"),
        "created_at": utcnow(),
        "inputs": {
            "pkg": str(Path(pkg).resolve()),
            "seeds": list(seeds),
            "profile": profile,
            "dimensions": {k: list(v) for k, v in dimensions.items()},
        },
        "provenance": {
            "seed_source": seed_source,
            "map_round": map_round,
        },
        "audit": {
            "allowed_next_steps": ["landscape", "focuses", "artifact", "gate"],
        },
    }
    return payload


def _lead_evidence_refs(lead: dict[str, Any]) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    paper_id = lead.get("paper_id")
    if isinstance(paper_id, str) and paper_id:
        refs.append({"kind": "paper", "id": paper_id})
    for node_id in lead.get("lkm_node_ids", []) or []:
        if isinstance(node_id, str) and node_id:
            refs.append({"kind": "lkm_node", "id": node_id})
    return refs


def build_focuses_artifact(
    pkg: str | Path,
    *,
    scope_path: Path | None,
    landscape_path: Path | None,
    landscape: dict[str, Any],
    landscape_rounds: Sequence[tuple[Path | None, dict[str, Any]]] | None = None,
    map_round: int,
) -> dict[str, Any]:
    """Build deterministic focus suggestions from paper-level landscape rounds."""
    rounds = landscape_rounds or [(landscape_path, landscape)]
    paper_leads = [
        lead
        for _, round_payload in rounds
        for lead in round_payload.get("paper_leads", [])
        if isinstance(lead, dict)
    ]
    round_refs = [
        {
            "round": round_number,
            "path": rel_artifact_path(pkg, path),
            "paper_leads": len(
                [lead for lead in payload.get("paper_leads", []) if isinstance(lead, dict)]
            ),
        }
        for path, payload in rounds
        if path is not None and (round_number := _landscape_round_number(path)) is not None
    ]
    focuses: list[dict[str, Any]] = []
    if paper_leads:
        evidence_refs: list[dict[str, str]] = []
        paper_ids: list[str] = []
        titles: list[str] = []
        queries: list[str] = []
        for lead in paper_leads:
            paper_id = lead.get("paper_id")
            if isinstance(paper_id, str) and paper_id and paper_id not in paper_ids:
                paper_ids.append(paper_id)
            title = lead.get("title")
            if isinstance(title, str) and title and title not in titles:
                titles.append(title)
            for query in lead.get("queries", []) or []:
                if isinstance(query, str) and query and query not in queries:
                    queries.append(query)
            for ref in _lead_evidence_refs(lead):
                if ref not in evidence_refs:
                    evidence_refs.append(ref)
        label = ", ".join(paper_ids[:3]) or f"{len(paper_leads)} paper lead(s)"
        text = f"Assess the paper-lead cluster surfaced by the landscape pass: {label}."
        focuses.append(
            {
                "id": artifact_id("focus"),
                "kind": "paper_lead_cluster",
                "text": text,
                "why_it_matters": (
                    "Landscape paper leads are the breadth-first bridge from Explore "
                    "into evidence assessment."
                ),
                "evidence_refs": evidence_refs,
                "recommended_next": "assess",
                "confidence": "medium",
                "provenance": {
                    "paper_ids": paper_ids,
                    "titles": titles[:5],
                    "queries": queries,
                },
            }
        )

    return {
        "schema": SOP_SCHEMA,
        "kind": "exploration_focuses",
        "id": artifact_id("focuses"),
        "created_at": utcnow(),
        "inputs": {
            "pkg": str(Path(pkg).resolve()),
            "scope": rel_artifact_path(pkg, scope_path),
            "landscape": rel_artifact_path(pkg, landscape_path),
            "landscape_rounds": round_refs,
        },
        "provenance": {"map_round": map_round},
        "focuses": focuses,
        "audit": {"allowed_next_steps": ["artifact", "gate", "assess"]},
    }


def _optional_artifact(pkg: str | Path, path: Path) -> str | None:
    return rel_artifact_path(pkg, path) if path.exists() else None


def build_exploration_artifact(
    pkg: str | Path,
    *,
    map_round: int,
    map_version: int,
) -> dict[str, Any]:
    """Build the handoff envelope that links Explore sidecars together."""
    exp = exploration_dir(pkg)
    gaia_dir = Path(pkg).resolve() / ".gaia"
    artifacts = {
        "scope": _optional_artifact(pkg, exp / "scope.json"),
        "landscape": rel_artifact_path(pkg, latest_landscape_path(pkg)),
        "focuses": _optional_artifact(pkg, exp / "focuses.json"),
        "map": _optional_artifact(pkg, exp / "map.json"),
        "artifact": _optional_artifact(pkg, exp / "artifact.json"),
        "rounds": _optional_artifact(pkg, exp / "rounds.jsonl"),
        "gaia_ir": _optional_artifact(pkg, gaia_dir / "ir.json"),
        "beliefs": _optional_artifact(pkg, gaia_dir / "beliefs.json"),
    }
    landscape_rounds = [
        {
            "round": round_number,
            "path": rel_artifact_path(pkg, path),
            "purpose": "broad_initial_survey" if round_number == 0 else "focus_gap_followup",
        }
        for path in landscape_round_paths(pkg)
        if (round_number := _landscape_round_number(path)) is not None
    ]
    core_names = {
        "scope": "scope.json",
        "landscape": "landscape-*.json",
        "focuses": "focuses.json",
        "map": "map.json",
    }
    limitations = [f"missing {name}" for key, name in core_names.items() if artifacts[key] is None]
    return {
        "schema": SOP_SCHEMA,
        "kind": "lkm_exploration",
        "id": artifact_id("exploration"),
        "created_at": utcnow(),
        "inputs": {
            "pkg": str(Path(pkg).resolve()),
            "map_round": map_round,
            "map_version": map_version,
        },
        "artifacts": artifacts,
        "landscape_rounds": landscape_rounds,
        "audit": {
            "known_limitations": limitations,
            "allowed_next_steps": ["gate"],
        },
        "interface": {
            "assess": {
                "command": "gaia-evidence assess --exploration .gaia/exploration/artifact.json"
            }
        },
    }


def _landscape_round_number(path: Path) -> int | None:
    suffix = path.stem.removeprefix("landscape-")
    try:
        return int(suffix)
    except ValueError:
        return None


def _check(status: str, detail: str) -> dict[str, str]:
    return {"status": status, "detail": detail}


def _artifact_ref(artifact: dict[str, Any], name: str) -> Any:
    artifacts = artifact.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    return artifacts.get(name)


def _focus_list(focuses: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(focuses, dict):
        return []
    rows = focuses.get("focuses")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def build_gate_report(
    artifact: dict[str, Any],
    focuses: dict[str, Any] | None,
) -> dict[str, Any]:
    """Build a deterministic pass/revise/block report for Assess handoff."""
    rows = _focus_list(focuses)
    assessable = [row for row in rows if row.get("recommended_next") == "assess"]
    assessable_with_refs = [
        row
        for row in assessable
        if isinstance(row.get("evidence_refs"), list) and bool(row["evidence_refs"])
    ]
    all_focuses_have_refs = all(
        isinstance(row.get("evidence_refs"), list) and bool(row["evidence_refs"]) for row in rows
    )
    checks = {
        "scope_present": _check(
            "pass" if _artifact_ref(artifact, "scope") else "fail",
            "scope artifact reference is present",
        ),
        "map_present": _check(
            "pass" if _artifact_ref(artifact, "map") else "fail",
            "exploration map reference is present",
        ),
        "landscape_present": _check(
            "pass" if _artifact_ref(artifact, "landscape") else "fail",
            "landscape artifact reference is present",
        ),
        "focuses_present": _check(
            "pass" if _artifact_ref(artifact, "focuses") and focuses else "fail",
            "focuses artifact is present and readable",
        ),
        "has_assessable_focus": _check(
            "pass" if assessable else "fail",
            "at least one focus recommends assess",
        ),
        "focuses_have_evidence_refs": _check(
            "skip"
            if not assessable
            else "pass"
            if len(assessable_with_refs) == len(assessable)
            else "fail",
            "assessable focuses carry evidence refs"
            if assessable
            else "no assessable focus to check for evidence refs",
        ),
        "schema_versions_supported": _check(
            "pass"
            if artifact.get("schema") == SOP_SCHEMA
            and (focuses is None or focuses.get("schema") == SOP_SCHEMA)
            else "fail",
            f"supported schema is {SOP_SCHEMA}",
        ),
        "compiled_ir_present": _check(
            "pass" if _artifact_ref(artifact, "gaia_ir") else "warn",
            "compiled IR is available for downstream assessment context",
        ),
        "beliefs_present": _check(
            "pass" if _artifact_ref(artifact, "beliefs") else "warn",
            "beliefs sidecar is available for downstream assessment context",
        ),
        "rounds_present": _check(
            "pass" if _artifact_ref(artifact, "rounds") else "warn",
            "round history is available for provenance",
        ),
        "all_focuses_have_evidence_refs": _check(
            "pass" if all_focuses_have_refs else "warn",
            "all focus rows carry evidence refs",
        ),
    }
    required = [
        "scope_present",
        "map_present",
        "landscape_present",
        "focuses_present",
        "has_assessable_focus",
        "focuses_have_evidence_refs",
        "schema_versions_supported",
    ]
    warnings = [
        "compiled_ir_present",
        "beliefs_present",
        "rounds_present",
        "all_focuses_have_evidence_refs",
    ]
    if any(checks[name]["status"] == "fail" for name in required):
        verdict = "block"
    elif any(checks[name]["status"] == "warn" for name in warnings):
        verdict = "revise"
    else:
        verdict = "pass"
    return {
        "schema": SOP_SCHEMA,
        "kind": "exploration_gate_report",
        "id": artifact_id("gate"),
        "created_at": utcnow(),
        "verdict": verdict,
        "checks": checks,
        "audit": {
            "allowed_next_steps": ["assess"] if verdict == "pass" else [],
        },
    }


__all__ = [
    "SOP_SCHEMA",
    "artifact_id",
    "build_exploration_artifact",
    "build_focuses_artifact",
    "build_gate_report",
    "build_scope_artifact",
    "exploration_dir",
    "landscape_round_paths",
    "latest_landscape_path",
    "parse_dimensions",
    "rel_artifact_path",
    "utcnow",
]
