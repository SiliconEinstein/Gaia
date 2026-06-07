"""Programmatic query helpers for ``gaia review query``."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from gaia.engine.inquiry.review import run_review
from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.review._schemas import ReviewFinding, ReviewReport, ReviewSeverity
from gaia.engine.review.calibration import compute_calibration_deltas

QueryKind = Literal["weakest-claims", "missing-priors", "large-deltas", "unreviewed"]


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _status_for_findings(findings: list[ReviewFinding]) -> Literal["pass", "warning", "error"]:
    if any(finding.severity == ReviewSeverity.ERROR for finding in findings):
        return "error"
    if findings:
        return "warning"
    return "pass"


def _query_missing_priors(
    pkg_path: Path, top_k: int
) -> tuple[list[ReviewFinding], dict[str, object]]:
    report = run_review(pkg_path, mode="query", no_infer=True)
    holes = report.prior_holes[:top_k]
    findings = [
        ReviewFinding(
            severity=ReviewSeverity.WARNING,
            category="query.missing_priors",
            location=str(hole.get("cid") or hole.get("label") or "unknown"),
            message=f"Claim {hole.get('label')!r} has no explicit prior",
            detector="query_missing_priors",
            details=dict(hole),
        )
        for hole in holes
    ]
    return findings, {
        "inquiry_review_id": report.review_id,
        "total_prior_holes": len(report.prior_holes),
    }


def _delta_message(delta_label: str, posterior: float, delta: float, *, weakest: bool) -> str:
    if weakest:
        return f"Claim {delta_label!r} has low posterior belief {posterior:.3f}"
    return f"Claim {delta_label!r} has large belief shift Δ={delta:+.3f}"


def _query_unreviewed(pkg_path: Path, top_k: int) -> tuple[list[ReviewFinding], dict[str, object]]:
    report = run_review(pkg_path, mode="query", no_infer=True)
    tree = report.inquiry_tree
    unreviewed = int(tree.get("unreviewed_warrants", 0))
    findings: list[ReviewFinding] = []
    if unreviewed:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.WARNING,
                category="query.unreviewed",
                location="global",
                message=f"{unreviewed} warrants are still unreviewed",
                detector="query_unreviewed",
                details={"inquiry_tree": tree, "top_k": top_k},
            )
        )
    return findings, {"inquiry_review_id": report.review_id, "inquiry_tree": tree}


def _query_deltas(
    pkg_path: Path,
    top_k: int,
    *,
    weakest: bool,
) -> tuple[list[ReviewFinding], dict[str, object]]:
    deltas, converged, iterations = compute_calibration_deltas(pkg_path, top_k=None)
    if weakest:
        selected = sorted(deltas, key=lambda delta: delta.posterior)[:top_k]
        category = "query.weakest_claims"
        detector = "query_weakest_claims"
    else:
        selected = [delta for delta in deltas if delta.abs_delta > 0.15][:top_k]
        category = "query.large_deltas"
        detector = "query_large_deltas"

    findings = [
        ReviewFinding(
            severity=ReviewSeverity.WARNING,
            category=category,
            location=delta.claim_qid,
            message=_delta_message(
                delta.claim_label, delta.posterior, delta.delta, weakest=weakest
            ),
            detector=detector,
            details=delta.model_dump(mode="json"),
        )
        for delta in selected
    ]
    return findings, {
        "converged": converged,
        "iterations": iterations,
        "total_deltas": len(deltas),
    }


def run_query_review(pkg_path: str | Path, query: QueryKind, *, top_k: int = 5) -> ReviewReport:
    """Run a structured review query and return matching findings."""
    pkg_path = Path(pkg_path).resolve()
    if query == "missing-priors":
        findings, query_metadata = _query_missing_priors(pkg_path, top_k)
    elif query == "unreviewed":
        findings, query_metadata = _query_unreviewed(pkg_path, top_k)
    elif query == "large-deltas":
        findings, query_metadata = _query_deltas(pkg_path, top_k, weakest=False)
    else:
        findings, query_metadata = _query_deltas(pkg_path, top_k, weakest=True)

    status = _status_for_findings(findings)
    summary = (
        f"Query {query} returned {len(findings)} findings"
        if findings
        else f"Query {query} returned no findings"
    )
    return ReviewReport(
        review_id=mint_review_id(None, f"query-{query}"),
        review_type="query",
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        status=status,
        summary=summary,
        findings=findings,
        recommendations=[],
        metadata={"query": query, "top_k": top_k, **query_metadata},
    )
