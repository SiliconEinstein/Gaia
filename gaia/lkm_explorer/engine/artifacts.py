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
SOP_SCHEMA_V2 = "gaia.sop.artifact.v2"

FOCUS_SYNTHESIS_INSTRUCTIONS = [
    "Propose only focuses grounded in evidence refs.",
    "Prefer 2-5 assessment questions.",
    "Separate paper-level material from claim-level conclusions.",
    "Do not state a tension as established unless the refs support it.",
    "For each focus, list missing evidence needed before assessment.",
]


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


def collect_landscape_grounding_refs(landscape_rounds: Sequence[dict[str, Any]]) -> set[str]:
    """Return paper and LKM node ids that are grounded by landscape rounds."""
    refs: set[str] = set()
    for payload in landscape_rounds:
        for lead in payload.get("paper_leads", []) or []:
            if not isinstance(lead, dict):
                continue
            for ref in _lead_evidence_refs(lead):
                refs.add(ref["id"])
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
                "level": "focus",
                "text": text,
                "question": text,
                "why_it_matters": (
                    "Landscape paper leads are the breadth-first bridge from Explore "
                    "into evidence assessment."
                ),
                "evidence_refs": evidence_refs,
                "recommended_next": "assess",
                "status": "ready_for_assess",
                "coverage": {
                    "status": "ready_for_assess",
                    "evidence_families": ["paper_lead"],
                    "support_refs": len(paper_ids),
                    "oppose_or_harm_refs": 0,
                    "limitation_refs": 0,
                    "missing_dimensions": [],
                    "grounded_ref_count": len(evidence_refs),
                    "stop_reason": "paper leads are grounded for downstream assessment",
                },
                "candidate_claims": [],
                "next_landscape_queries": [],
                "confidence": "medium",
                "provenance": {
                    "paper_ids": paper_ids,
                    "titles": titles[:5],
                    "queries": queries,
                },
            }
        )

    return {
        "schema": SOP_SCHEMA_V2,
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


def build_focus_context_artifact(
    pkg: str | Path,
    *,
    scope_path: Path | None,
    scope: dict[str, Any] | None,
    landscape_rounds: Sequence[tuple[Path, dict[str, Any]]],
    existing_focuses_path: Path | None,
    existing_focuses: dict[str, Any] | None,
    map_round: int,
) -> dict[str, Any]:
    """Build the grounded packet for LLM/human focus synthesis."""
    round_refs: list[dict[str, Any]] = []
    paper_leads: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    for path, payload in landscape_rounds:
        round_number = _landscape_round_number(path)
        if round_number is None:
            continue
        rel_path = rel_artifact_path(pkg, path)
        leads = [lead for lead in payload.get("paper_leads", []) if isinstance(lead, dict)]
        round_refs.append(
            {
                "round": round_number,
                "path": rel_path,
                "purpose": "broad_initial_survey" if round_number == 0 else "focus_gap_followup",
                "paper_leads": len(leads),
            }
        )
        for query in payload.get("queries", []) or []:
            if isinstance(query, dict):
                queries.append({"round": round_number, "path": rel_path, **query})
        for lead in leads:
            paper_leads.append(
                {
                    "round": round_number,
                    "path": rel_path,
                    "paper_id": lead.get("paper_id"),
                    "title": lead.get("title"),
                    "doi": lead.get("doi"),
                    "index_id": lead.get("index_id"),
                    "best_rank": lead.get("best_rank"),
                    "queries": list(lead.get("queries", []) or []),
                    "lkm_node_ids": list(lead.get("lkm_node_ids", []) or []),
                }
            )
    focus_rows = _focus_list(existing_focuses)
    return {
        "schema": SOP_SCHEMA_V2,
        "kind": "focus_synthesis_context",
        "id": artifact_id("focus_context"),
        "created_at": utcnow(),
        "inputs": {
            "pkg": str(Path(pkg).resolve()),
            "scope": rel_artifact_path(pkg, scope_path),
            "existing_focuses": rel_artifact_path(pkg, existing_focuses_path),
            "map_round": map_round,
        },
        "scope": scope or {},
        "landscape_rounds": round_refs,
        "paper_leads": paper_leads,
        "queries": queries,
        "existing_focuses": focus_rows,
        "coverage_gaps": [],
        "instructions": list(FOCUS_SYNTHESIS_INSTRUCTIONS),
        "audit": {
            "allowed_next_steps": ["focuses", "artifact", "gate"],
        },
    }


def _optional_artifact(pkg: str | Path, path: Path) -> str | None:
    return rel_artifact_path(pkg, path) if path.exists() else None


def _focus_list(focuses: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(focuses, dict):
        return []
    rows = focuses.get("focuses")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _focus_status(row: dict[str, Any]) -> str:
    status = row.get("status")
    if isinstance(status, str) and status:
        return status
    if row.get("recommended_next") == "assess":
        return "ready_for_assess"
    return "needs_more_landscape"


def _focus_ref_ids(row: dict[str, Any]) -> set[str]:
    refs: set[str] = set()
    for ref in row.get("evidence_refs", []) or []:
        if isinstance(ref, dict) and isinstance(ref.get("id"), str):
            refs.add(ref["id"])
    return refs


def _focus_status_summaries(focuses: dict[str, Any] | None) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for row in _focus_list(focuses):
        focus_id = row.get("id")
        if not isinstance(focus_id, str) or not focus_id:
            continue
        status = _focus_status(row)
        summaries.append(
            {
                "id": focus_id,
                "status": status,
                "recommended_next": "assess" if status == "ready_for_assess" else "landscape",
                "evidence_refs": len(_focus_ref_ids(row)),
            }
        )
    return summaries


def _ready_focus_contract_ok(row: dict[str, Any]) -> bool:
    has_prompt = isinstance(row.get("question"), str) or isinstance(row.get("text"), str)
    return (
        has_prompt
        and isinstance(row.get("coverage"), dict)
        and isinstance(row.get("provenance"), dict)
        and bool(_focus_ref_ids(row))
    )


def _unready_focus_has_next_step(row: dict[str, Any]) -> bool:
    coverage = row.get("coverage")
    missing = coverage.get("missing_dimensions") if isinstance(coverage, dict) else None
    next_queries = row.get("next_landscape_queries")
    return bool(missing) or bool(next_queries)


def _exploration_coverage_summary(artifacts: dict[str, str | None]) -> dict[str, Any]:
    paper_level_gaps: list[str] = []
    if artifacts["landscape"] is None:
        paper_level_gaps.append("landscape missing")

    claim_level_gaps: list[str] = []
    if artifacts["gaia_ir"] is None:
        claim_level_gaps.append("compiled IR missing")
    if artifacts["beliefs"] is None:
        claim_level_gaps.append("beliefs sidecar missing")

    return {
        "paper_level_gaps": paper_level_gaps,
        "claim_level_gaps": claim_level_gaps,
        "budget_exhaustion": "not_evaluated",
    }


def build_exploration_artifact(
    pkg: str | Path,
    *,
    map_round: int,
    map_version: int,
    focuses: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the handoff envelope that links Explore sidecars together."""
    exp = exploration_dir(pkg)
    gaia_dir = Path(pkg).resolve() / ".gaia"
    artifacts = {
        "scope": _optional_artifact(pkg, exp / "scope.json"),
        "landscape": rel_artifact_path(pkg, latest_landscape_path(pkg)),
        "focuses": _optional_artifact(pkg, exp / "focuses.json"),
        "focus_context": _optional_artifact(pkg, exp / "focus_context.json"),
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
    focus_statuses = _focus_status_summaries(focuses)
    ready_focus_ids = [row["id"] for row in focus_statuses if row["status"] == "ready_for_assess"]
    return {
        "schema": SOP_SCHEMA_V2,
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
        "focus_statuses": focus_statuses,
        "audit": {
            "coverage": _exploration_coverage_summary(artifacts),
            "known_limitations": limitations,
            "allowed_next_steps": ["gate"],
        },
        "interface": {
            "assess": {
                "command": "gaia-evidence assess --exploration .gaia/exploration/artifact.json",
                "focus_commands": [
                    "gaia-evidence assess --exploration "
                    f".gaia/exploration/artifact.json --focus {focus_id}"
                    for focus_id in ready_focus_ids
                ],
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


def _has_landscape_round_provenance(artifact: dict[str, Any]) -> bool:
    if artifact.get("schema") != SOP_SCHEMA_V2:
        return False
    rounds = artifact.get("landscape_rounds")
    if not isinstance(rounds, list) or not rounds:
        return False
    return all(isinstance(row, dict) and row.get("path") for row in rounds)


def build_gate_report(
    artifact: dict[str, Any],
    focuses: dict[str, Any] | None,
    *,
    grounding_refs: set[str] | None = None,
) -> dict[str, Any]:
    """Build a deterministic pass/revise/block report for Assess handoff."""
    rows = _focus_list(focuses)
    assessable = [row for row in rows if _focus_status(row) == "ready_for_assess"]
    assessable_with_refs = [
        row
        for row in assessable
        if isinstance(row.get("evidence_refs"), list) and bool(row["evidence_refs"])
    ]
    all_focuses_have_refs = all(
        isinstance(row.get("evidence_refs"), list) and bool(row["evidence_refs"]) for row in rows
    )
    unsupported_refs: set[str] = set()
    if grounding_refs is not None:
        ready_ref_ids = (
            set().union(*[_focus_ref_ids(row) for row in assessable]) if assessable else set()
        )
        unsupported_refs = ready_ref_ids - grounding_refs
    supported_schemas = {SOP_SCHEMA, SOP_SCHEMA_V2}
    ready_focuses_have_contract = all(_ready_focus_contract_ok(row) for row in assessable)
    unready_focuses = [row for row in rows if _focus_status(row) != "ready_for_assess"]
    unready_have_next_steps = all(_unready_focus_has_next_step(row) for row in unready_focuses)
    audit = artifact.get("audit")
    coverage = audit.get("coverage") if isinstance(audit, dict) else None
    v2_coverage_budget_recorded = (
        isinstance(coverage, dict)
        and isinstance(coverage.get("paper_level_gaps"), list)
        and isinstance(coverage.get("claim_level_gaps"), list)
        and coverage.get("budget_exhaustion") is not None
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
            "at least one focus is ready for assess",
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
        "ready_focuses_have_contract": _check(
            "skip" if not assessable else "pass" if ready_focuses_have_contract else "fail",
            "ready focuses carry question/text, coverage, provenance, and evidence refs"
            if assessable
            else "no ready focus to check",
        ),
        "ready_focus_refs_grounded": _check(
            "skip"
            if grounding_refs is None or not assessable
            else "pass"
            if not unsupported_refs
            else "fail",
            "ready focus evidence refs are grounded in landscape rounds"
            if grounding_refs is not None and assessable
            else "no grounding refs or ready focuses to check",
        ),
        "schema_versions_supported": _check(
            "pass"
            if artifact.get("schema") in supported_schemas
            and (focuses is None or focuses.get("schema") in supported_schemas)
            else "fail",
            f"supported schemas are {', '.join(sorted(supported_schemas))}",
        ),
        "coverage_budget_recorded": _check(
            "skip"
            if artifact.get("schema") != SOP_SCHEMA_V2
            else "pass"
            if v2_coverage_budget_recorded
            else "fail",
            "v2 artifact records paper gaps, claim gaps, and budget exhaustion",
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
            "pass"
            if _artifact_ref(artifact, "rounds") or _has_landscape_round_provenance(artifact)
            else "warn",
            "round history or v2 landscape round index is available for provenance",
        ),
        "all_focuses_have_evidence_refs": _check(
            "pass" if all_focuses_have_refs else "warn",
            "all focus rows carry evidence refs",
        ),
        "unready_focuses_have_next_steps": _check(
            "pass" if not unready_focuses or unready_have_next_steps else "warn",
            "unready focuses explain missing dimensions or next landscape queries",
        ),
    }
    required = [
        "scope_present",
        "map_present",
        "landscape_present",
        "focuses_present",
        "has_assessable_focus",
        "focuses_have_evidence_refs",
        "ready_focuses_have_contract",
        "ready_focus_refs_grounded",
        "schema_versions_supported",
        "coverage_budget_recorded",
    ]
    warnings = [
        "compiled_ir_present",
        "beliefs_present",
        "rounds_present",
        "all_focuses_have_evidence_refs",
        "unready_focuses_have_next_steps",
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
        "validation": {
            "ungrounded_refs": sorted(unsupported_refs),
        },
        "audit": {
            "allowed_next_steps": ["assess"] if verdict == "pass" else [],
        },
    }


__all__ = [
    "FOCUS_SYNTHESIS_INSTRUCTIONS",
    "SOP_SCHEMA",
    "SOP_SCHEMA_V2",
    "artifact_id",
    "build_exploration_artifact",
    "build_focus_context_artifact",
    "build_focuses_artifact",
    "build_gate_report",
    "build_scope_artifact",
    "collect_landscape_grounding_refs",
    "exploration_dir",
    "landscape_round_paths",
    "latest_landscape_path",
    "parse_dimensions",
    "rel_artifact_path",
    "utcnow",
]
