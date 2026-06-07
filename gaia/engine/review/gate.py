"""Composable review gates for ``gaia review gate``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.review._schemas import ReviewFinding, ReviewReport, ReviewSeverity
from gaia.engine.review.calibration import run_calibration_review
from gaia.engine.review.redteam import run_redteam_review
from gaia.engine.review.status import run_status_review

GateName = Literal["candidate", "calibration", "completeness", "audit"]


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _severity_status(findings: list[ReviewFinding]) -> Literal["pass", "warning", "error"]:
    if any(f.severity == ReviewSeverity.ERROR for f in findings):
        return "error"
    if any(f.severity == ReviewSeverity.WARNING for f in findings):
        return "warning"
    return "pass"


def _calibration_findings(pkg_path: Path) -> tuple[list[ReviewFinding], dict[str, object]]:
    report = run_calibration_review(pkg_path, top_k=10)
    findings: list[ReviewFinding] = []
    for delta in report.top_deltas:
        if delta.abs_delta > 0.15:
            findings.append(
                ReviewFinding(
                    severity=ReviewSeverity.WARNING,
                    category="gate.calibration",
                    location=delta.claim_qid,
                    message=f"Large calibration delta: Δ={delta.delta:+.3f}",
                    detector="gate_calibration",
                    details=delta.model_dump(mode="json"),
                )
            )
    return findings, {
        "review_id": report.review_id,
        "converged": report.converged,
        "top_deltas": len(report.top_deltas),
    }


def run_gate_review(pkg_path: str | Path, gate: GateName) -> ReviewReport:
    """Run a named read-only gate and return a unified ReviewReport."""
    pkg_path = Path(pkg_path).resolve()
    findings: list[ReviewFinding] = []
    component_statuses: dict[str, str] = {}
    components: dict[str, object] = {}
    metadata: dict[str, object] = {"gate": gate, "components": components}

    if gate in ("candidate", "audit"):
        candidate = run_redteam_review(pkg_path)
        findings.extend(candidate.findings)
        component_statuses["candidate"] = candidate.status
        components["candidate"] = candidate.metadata

    if gate in ("calibration", "audit"):
        calibration_findings, calibration_meta = _calibration_findings(pkg_path)
        findings.extend(calibration_findings)
        component_statuses["calibration"] = _severity_status(calibration_findings)
        components["calibration"] = calibration_meta

    if gate in ("completeness", "audit"):
        completeness = run_status_review(pkg_path)
        findings.extend(
            finding.model_copy(update={"category": f"gate.completeness.{finding.category}"})
            for finding in completeness.findings
        )
        component_statuses["completeness"] = completeness.status
        components["completeness"] = completeness.metadata

    status = _severity_status(findings)
    if status == "error":
        summary = f"Gate {gate} failed"
    elif status == "warning":
        summary = f"Gate {gate} has warnings"
    else:
        summary = f"Gate {gate} passed"

    metadata["component_statuses"] = component_statuses
    return ReviewReport(
        review_id=mint_review_id(None, f"gate-{gate}"),
        review_type="gate",
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        status=status,
        summary=summary,
        findings=findings,
        recommendations=[],
        metadata=metadata,
    )
