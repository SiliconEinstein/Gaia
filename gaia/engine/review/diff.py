"""Review diff orchestration for ``gaia review diff``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from gaia.engine.inquiry.review import run_review
from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.review._schemas import ReviewFinding, ReviewReport, ReviewSeverity


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _changed_delta_count(items: list[Any]) -> int:
    return len(items)


def _add_count_finding(
    findings: list[ReviewFinding],
    *,
    label: str,
    count: int,
    detector: str,
) -> None:
    if count == 0:
        return
    findings.append(
        ReviewFinding(
            severity=ReviewSeverity.WARNING,
            category="diff",
            location="global",
            message=f"{count} {label}",
            detector=detector,
        )
    )


def run_diff_review(
    pkg_path: str | Path,
    *,
    since: str | None = "last",
    no_infer: bool = True,
) -> ReviewReport:
    """Run an inquiry review and expose its semantic diff as a ReviewReport."""
    pkg_path = Path(pkg_path).resolve()
    inquiry_report = run_review(pkg_path, mode="diff", no_infer=no_infer, since=since)
    diff = inquiry_report.semantic_diff

    findings: list[ReviewFinding] = []
    _add_count_finding(
        findings,
        label="added claims",
        count=len(diff.added_claims),
        detector="diff_added_claims",
    )
    _add_count_finding(
        findings,
        label="removed claims",
        count=len(diff.removed_claims),
        detector="diff_removed_claims",
    )
    _add_count_finding(
        findings,
        label="changed claims",
        count=_changed_delta_count(diff.changed_claims),
        detector="diff_changed_claims",
    )
    _add_count_finding(
        findings,
        label="changed priors",
        count=_changed_delta_count(diff.changed_priors),
        detector="diff_changed_priors",
    )
    _add_count_finding(
        findings,
        label="changed strategies",
        count=_changed_delta_count(diff.changed_strategies),
        detector="diff_changed_strategies",
    )
    _add_count_finding(
        findings,
        label="changed operators",
        count=_changed_delta_count(diff.changed_operators),
        detector="diff_changed_operators",
    )

    if diff.baseline_review_id is None:
        status: Literal["pass", "warning", "error"] = "pass"
        summary = "No baseline snapshot was available for diff"
    elif diff.is_empty:
        status = "pass"
        summary = f"No semantic changes since {diff.baseline_review_id}"
    else:
        status = "warning"
        summary = f"Semantic changes detected since {diff.baseline_review_id}"

    return ReviewReport(
        review_id=mint_review_id(inquiry_report.ir_hash, "diff"),
        review_type="diff",
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        status=status,
        summary=summary,
        findings=findings,
        recommendations=[],
        metadata={
            "baseline_review_id": diff.baseline_review_id,
            "current_inquiry_review_id": inquiry_report.review_id,
            "semantic_diff": diff.to_dict(),
        },
    )
