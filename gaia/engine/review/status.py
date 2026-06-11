"""Read-only review status aggregation for ``gaia review status``."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from gaia.engine.inquiry.review_manifest import latest_reviews, load_or_generate_review_manifest
from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.ir import ReviewStatus as IrReviewStatus
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)
from gaia.engine.review._schemas import ReviewFinding, ReviewReport, ReviewSeverity


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _snapshot_ids(pkg_path: Path) -> list[str]:
    review_dir = pkg_path / ".gaia" / "inquiry" / "reviews"
    if not review_dir.exists():
        return []
    ids = [path.stem for path in review_dir.glob("*.json")]
    ids.sort(reverse=True)
    return ids


def _trace_summary(pkg_path: Path) -> dict[str, Any]:
    candidates = [
        pkg_path / ".gaia" / "trace.json",
        pkg_path / ".gaia" / "trace.jsonl",
        pkg_path / "trace.json",
        pkg_path / "trace.jsonl",
    ]
    existing = next((path for path in candidates if path.exists()), None)
    if existing is None:
        return {"present": False}
    return {"present": True, "path": str(existing)}


def _manifest_metadata(pkg_path: Path) -> tuple[dict[str, Any], list[ReviewFinding]]:
    ensure_package_env(pkg_path)
    loaded = load_gaia_package(str(pkg_path))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)
    reviews = latest_reviews(manifest)

    counts = {status.value: 0 for status in IrReviewStatus}
    for review in reviews:
        counts[review.status.value] += 1

    total = len(reviews)
    reviewed = total - counts[IrReviewStatus.UNREVIEWED.value]
    coverage = (reviewed / total) if total else 1.0

    findings: list[ReviewFinding] = []
    if counts[IrReviewStatus.REJECTED.value]:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.ERROR,
                category="manifest",
                location="global",
                message=f"{counts[IrReviewStatus.REJECTED.value]} review records are rejected",
                detector="review_status",
            )
        )
    if counts[IrReviewStatus.NEEDS_INPUTS.value]:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.WARNING,
                category="manifest",
                location="global",
                message=(f"{counts[IrReviewStatus.NEEDS_INPUTS.value]} review records need inputs"),
                detector="review_status",
            )
        )
    if counts[IrReviewStatus.UNREVIEWED.value]:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.WARNING,
                category="manifest",
                location="global",
                message=f"{counts[IrReviewStatus.UNREVIEWED.value]} review records are unreviewed",
                detector="review_status",
            )
        )

    metadata = {
        "counts": {
            "knowledge": len(getattr(compiled.graph, "knowledges", []) or []),
            "strategies": len(getattr(compiled.graph, "strategies", []) or []),
            "operators": len(getattr(compiled.graph, "operators", []) or []),
        },
        "manifest": {
            "total": total,
            "reviewed": reviewed,
            "coverage": coverage,
            **counts,
        },
    }
    return metadata, findings


def run_status_review(pkg_path: str | Path) -> ReviewReport:
    """Return a read-only status report for all review layers."""
    path = Path(pkg_path).resolve()
    findings: list[ReviewFinding] = []
    metadata: dict[str, Any] = {
        "package": str(path),
        "compile_status": "unknown",
    }

    try:
        manifest_metadata, manifest_findings = _manifest_metadata(path)
    except GaiaPackagingError as exc:
        metadata["compile_status"] = "error"
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.ERROR,
                category="compile",
                location="global",
                message=str(exc),
                detector="review_status",
            )
        )
    except Exception as exc:
        metadata["compile_status"] = "error"
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.ERROR,
                category="compile",
                location="global",
                message=f"compile failed: {exc}",
                detector="review_status",
            )
        )
    else:
        metadata["compile_status"] = "ok"
        metadata.update(manifest_metadata)
        findings.extend(manifest_findings)

    state_path = path / ".gaia" / "inquiry" / "state.json"
    state = _read_json(state_path) or {}
    snapshots = _snapshot_ids(path)
    metadata["inquiry"] = {
        "last_review_id": state.get("last_review_id"),
        "baseline_review_id": state.get("baseline_review_id"),
        "snapshot_count": len(snapshots),
        "latest_snapshot_id": snapshots[0] if snapshots else None,
    }
    metadata["trace"] = _trace_summary(path)

    has_error = any(f.severity == ReviewSeverity.ERROR for f in findings)
    has_warning = any(f.severity == ReviewSeverity.WARNING for f in findings)
    if has_error:
        status: Literal["pass", "warning", "error"] = "error"
        summary = "Review status has blocking errors"
    elif has_warning:
        status = "warning"
        summary = "Review status needs attention"
    else:
        status = "pass"
        summary = "Review status is clean"

    return ReviewReport(
        review_id=mint_review_id(None, "status"),
        review_type="status",
        created_at=_utcnow_iso(),
        path=str(path),
        status=status,
        summary=summary,
        findings=findings,
        recommendations=[],
        metadata=metadata,
    )
