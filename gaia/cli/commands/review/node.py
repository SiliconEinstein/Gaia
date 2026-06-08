"""gaia review node — single-node review (filter diagnostics to one node)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import typer

from gaia.engine.inquiry.review import run_review as run_inquiry_review
from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.packaging import (
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)
from gaia.engine.review._schemas import (
    NodeBeliefContext,
    NodeReviewReport,
    ReviewFinding,
    ReviewSeverity,
)
from gaia.engine.review.calibration import compute_calibration_deltas


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


NodeKind = Literal["claim", "strategy", "operator", "observe"]
NodeStatus = Literal["pass", "warning", "error"]


def _resolve_node(compiled: Any, node_id: str) -> tuple[NodeKind, str, str | None] | None:
    for knowledge in compiled.graph.knowledges:
        if knowledge.id and (
            knowledge.id == node_id
            or (knowledge.label and knowledge.label == node_id)
            or node_id in (knowledge.id or "")
        ):
            return "claim", knowledge.id, knowledge.id

    for strategy in compiled.graph.strategies:
        sid = getattr(strategy, "strategy_id", None)
        meta = getattr(strategy, "metadata", None) or {}
        action_label = meta.get("action_label", "")
        if sid and (sid == node_id or node_id in sid or node_id in action_label):
            return "strategy", sid, getattr(strategy, "conclusion", None)

    for operator in compiled.graph.operators:
        oid = getattr(operator, "operator_id", None)
        if oid and (oid == node_id or node_id in oid):
            return "operator", oid, getattr(operator, "conclusion", None)

    return None


def _severity(value: str) -> ReviewSeverity:
    if value == "error":
        return ReviewSeverity.ERROR
    if value == "warning":
        return ReviewSeverity.WARNING
    return ReviewSeverity.INFO


def _filter_node_findings(
    diagnostics: list[Any],
    *,
    resolved_id: str,
    node_id: str,
) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    for diag in diagnostics:
        target = getattr(diag, "target", None) or ""
        label = getattr(diag, "label", None) or ""
        if resolved_id not in target and node_id not in target and node_id not in label:
            continue
        findings.append(
            ReviewFinding(
                severity=_severity(getattr(diag, "severity", "info")),
                category="inquiry",
                location=target or label,
                message=diag.message,
                detector=getattr(diag, "kind", "unknown"),
            )
        )
    return findings


def _belief_context(
    project_dir: Path,
    belief_claim_id: str | None,
    findings: list[ReviewFinding],
) -> NodeBeliefContext | None:
    if not belief_claim_id:
        return None
    computation = compute_calibration_deltas(project_dir, top_k=None)

    # Δ (prior→posterior) is only meaningful for claims with an authored prior.
    delta = {item.claim_qid: item for item in computation.deltas}.get(belief_claim_id)
    if delta is not None:
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
                    detector="node_calibration",
                    details={
                        "prior": delta.prior,
                        "posterior": delta.posterior,
                        "delta": delta.delta,
                    },
                )
            )
        return NodeBeliefContext(
            claim_qid=delta.claim_qid,
            claim_label=delta.claim_label,
            posterior=delta.posterior,
            has_prior=True,
            prior=delta.prior,
            delta=delta.delta,
            abs_delta=delta.abs_delta,
        )

    # No authored prior: still surface the posterior (always computed) so the
    # reviewer sees the belief, without inventing a prior or a Δ.
    posterior = computation.posteriors.get(belief_claim_id)
    if posterior is None:
        return None
    return NodeBeliefContext(
        claim_qid=belief_claim_id,
        claim_label=belief_claim_id.split("::")[-1],
        posterior=posterior,
        has_prior=False,
    )


def _status(findings: list[ReviewFinding]) -> NodeStatus:
    if any(f.severity == ReviewSeverity.ERROR for f in findings):
        return "error"
    if any(f.severity == ReviewSeverity.WARNING for f in findings):
        return "warning"
    return "pass"


def _render_text(report: NodeReviewReport) -> None:
    status_icon = {"pass": "✓", "warning": "⚠", "error": "✗"}
    icon = status_icon.get(report.status, "·")

    typer.echo("=" * 70)
    typer.echo(f"GAIA NODE REVIEW — {icon} {report.status.upper()}")
    typer.echo("=" * 70)
    typer.echo(f"Node: {report.node_id}")
    typer.echo(f"Kind: {report.node_kind}")
    typer.echo(f"Path: {report.path}")
    belief = report.belief
    if belief and belief.has_prior and belief.prior is not None and belief.delta is not None:
        typer.echo(
            "Belief: "
            f"{belief.prior:.3f} → {belief.posterior:.3f} "
            f"(Δ={belief.delta:+.3f})"
        )
    elif belief:
        typer.echo(f"Belief: posterior={belief.posterior:.3f} (no authored prior)")
    typer.echo("")

    if not report.findings:
        typer.echo("No findings for this node. ✓")
    else:
        typer.echo(f"Findings ({len(report.findings)}):")
        for i, finding in enumerate(report.findings, 1):
            severity_icon = {
                ReviewSeverity.ERROR: "✗",
                ReviewSeverity.WARNING: "⚠",
                ReviewSeverity.INFO: "i",
            }
            s_icon = severity_icon.get(finding.severity, "·")
            typer.echo(f"  {i}. {s_icon} {finding.message}")
            typer.echo(f"     Detector: {finding.detector}")

    typer.echo("=" * 70)


def node_command(
    node_id: str = typer.Argument(..., help="Node ID or label to review"),
    path: str = typer.Option(".", help="Path to Gaia package"),
    format: Literal["text", "json"] = typer.Option(
        "text", "--format", "-f", help="Output format: text or json"
    ),
) -> None:
    """Review a single node — filter diagnostics to one claim/strategy/operator.

    Runs inquiry review and extracts findings related to the specified node.

    Exit codes:
      0  pass / warning
      1  error (blocking findings)
      2  system error

    Example:
        gaia review node aristotle_model
        gaia review node lcs_abc123 --format json
    """
    project_dir = Path(path).resolve()

    if not project_dir.exists():
        typer.echo(f"Error: path does not exist: {project_dir}", err=True)
        raise typer.Exit(2)

    try:
        # Compile package to resolve node
        ensure_package_env(project_dir)
        loaded = load_gaia_package(str(project_dir))
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)

        resolved = _resolve_node(compiled, node_id)
        if resolved is None:
            typer.echo(f"Error: node not found: {node_id}", err=True)
            typer.echo("Available claims:", err=True)
            for k in compiled.graph.knowledges[:10]:
                if k.label:
                    typer.echo(f"  {k.label}", err=True)
            raise typer.Exit(1)
        node_kind, resolved_id, belief_claim_id = resolved

        inquiry_report = run_inquiry_review(project_dir, mode="auto", no_infer=False)
        findings = _filter_node_findings(
            list(inquiry_report.diagnostics),
            resolved_id=resolved_id,
            node_id=node_id,
        )
        belief = _belief_context(project_dir, belief_claim_id, findings)

        report = NodeReviewReport(
            review_id=mint_review_id(None, "node"),
            created_at=_utcnow_iso(),
            path=str(project_dir),
            node_id=resolved_id,
            node_kind=node_kind,
            status=_status(findings),
            belief=belief,
            findings=findings,
            recommendations=[],
            metadata={},
        )

    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(2) from e

    # Render
    if format == "json":
        print(json.dumps(report.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        _render_text(report)

    if report.status == "error":
        raise typer.Exit(1)
