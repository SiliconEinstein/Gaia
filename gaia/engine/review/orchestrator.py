"""Review orchestrator — merge inquiry + trace + calibration into unified report.

Design principle: Thin orchestration. Don't rewrite inquiry/trace review logic,
just call them and merge their outputs into ReviewReport format.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from gaia.engine.inquiry.review import ReviewReport as InquiryReviewReport
from gaia.engine.inquiry.review import run_review as run_inquiry_review
from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.review._schemas import (
    ReviewFinding,
    ReviewRecommendation,
    ReviewReport,
    ReviewSeverity,
)
from gaia.engine.review.calibration import run_calibration_review
from gaia.engine.trace.review import run_trace_review


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _inquiry_to_findings(inquiry_report: InquiryReviewReport) -> list[ReviewFinding]:
    """Convert inquiry diagnostics to ReviewFindings."""
    findings: list[ReviewFinding] = []

    for diag in inquiry_report.diagnostics:
        if diag.severity == "error":
            severity = ReviewSeverity.ERROR
        elif diag.severity == "warning":
            severity = ReviewSeverity.WARNING
        else:
            severity = ReviewSeverity.INFO

        findings.append(
            ReviewFinding(
                severity=severity,
                category="inquiry",
                location=diag.target or "global",
                message=diag.message,
                detector=diag.kind,
                details=dict(diag.data) if diag.data else {},
            )
        )

    return findings


def _trace_to_findings(trace_report: Any) -> list[ReviewFinding]:
    """Convert trace diagnostics to ReviewFindings."""
    findings: list[ReviewFinding] = []

    for diag in trace_report.diagnostics:
        if diag.severity == "error":
            severity = ReviewSeverity.ERROR
        elif diag.severity == "warning":
            severity = ReviewSeverity.WARNING
        else:
            severity = ReviewSeverity.INFO

        findings.append(
            ReviewFinding(
                severity=severity,
                category="trace",
                location=diag.target or "global",
                message=diag.message,
                detector=diag.kind,
                details=dict(diag.data) if diag.data else {},
            )
        )

    return findings


def run_package_review(
    pkg_path: str | Path,
    *,
    skip_inference: bool = False,
    skip_calibration: bool = False,
    skip_trace: bool = False,
) -> ReviewReport:
    """Run complete package review: inquiry + trace + calibration.

    Args:
        pkg_path: Path to Gaia package
        skip_inference: Skip BP inference. Because calibration is itself a BP
            run, skipping inference also skips calibration (a "skip BP" flag
            must not silently keep running BP under another name).
        skip_calibration: Skip calibration delta computation independently of
            inference.
        skip_trace: Skip trace review even if trace exists

    Returns:
        Unified ReviewReport aggregating all layers
    """
    pkg_path = Path(pkg_path).resolve()
    review_id = mint_review_id(None, "package")

    # Calibration runs BP, so --no-infer must also disable it. Otherwise the
    # report would still carry metadata.calibration after the user asked to
    # skip inference.
    skip_calibration = skip_calibration or skip_inference

    findings: list[ReviewFinding] = []
    recommendations: list[ReviewRecommendation] = []
    metadata: dict[str, Any] = {}

    # 1. Run inquiry review (reuse existing run_review API)
    inquiry_report = run_inquiry_review(
        pkg_path,
        mode="auto",
        no_infer=skip_inference,
    )

    # Extract inquiry metadata
    metadata["inquiry"] = {
        "review_id": inquiry_report.review_id,
        "compile_status": inquiry_report.compile_status,
        "diagnostics_count": len(inquiry_report.diagnostics),
        "counts": inquiry_report.counts,
    }

    # Convert inquiry diagnostics to unified findings
    findings.extend(_inquiry_to_findings(inquiry_report))

    # 2. Run trace review if trace exists
    trace_paths = [
        pkg_path / ".gaia" / "trace.json",
        pkg_path / ".gaia" / "trace.jsonl",
        pkg_path / "trace.json",
        pkg_path / "trace.jsonl",
    ]

    if not skip_trace:
        for tp in trace_paths:
            if tp.exists():
                try:
                    trace_report = run_trace_review(str(tp))

                    metadata["trace"] = {
                        "trace_review_id": trace_report.trace_review_id,
                        "manifest_status": trace_report.manifest_status,
                        "hash_chain_ok": trace_report.hash_chain.get("ok", False),
                    }

                    findings.extend(_trace_to_findings(trace_report))
                except Exception as e:
                    findings.append(
                        ReviewFinding(
                            severity=ReviewSeverity.WARNING,
                            category="trace",
                            location="global",
                            message=f"Trace review failed: {e}",
                            detector="orchestrator",
                        )
                    )
                break

    # 3. Run calibration review
    if not skip_calibration and inquiry_report.compile_status == "ok":
        try:
            calibration_report = run_calibration_review(pkg_path, top_k=10)

            metadata["calibration"] = {
                "review_id": calibration_report.review_id,
                "converged": calibration_report.converged,
                "top_deltas_count": len(calibration_report.top_deltas),
            }

            # Large deltas are warnings
            for delta in calibration_report.top_deltas:
                if delta.abs_delta > 0.15:
                    findings.append(
                        ReviewFinding(
                            severity=ReviewSeverity.WARNING,
                            category="calibration",
                            location=delta.claim_qid,
                            message=(
                                f"Large belief shift: Δ={delta.delta:+.3f} "
                                f"(prior={delta.prior:.3f} → posterior={delta.posterior:.3f})"
                            ),
                            detector="calibration",
                            details={
                                "prior": delta.prior,
                                "posterior": delta.posterior,
                                "delta": delta.delta,
                            },
                        )
                    )
        except Exception as e:
            findings.append(
                ReviewFinding(
                    severity=ReviewSeverity.INFO,
                    category="calibration",
                    location="global",
                    message=f"Calibration review skipped: {e}",
                    detector="orchestrator",
                )
            )

    # Determine overall status
    has_error = any(f.severity == ReviewSeverity.ERROR for f in findings)
    has_warning = any(f.severity == ReviewSeverity.WARNING for f in findings)

    if has_error:
        status: Literal["pass", "warning", "error"] = "error"
        error_count = sum(1 for f in findings if f.severity == ReviewSeverity.ERROR)
        summary = f"Package review found {error_count} errors"
    elif has_warning:
        status = "warning"
        warn_count = sum(1 for f in findings if f.severity == ReviewSeverity.WARNING)
        summary = f"Package review found {warn_count} warnings"
    else:
        status = "pass"
        summary = "Package review passed with no issues"

    return ReviewReport(
        review_id=review_id,
        review_type="package",
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        status=status,
        summary=summary,
        findings=findings,
        recommendations=recommendations,
        metadata=metadata,
    )
