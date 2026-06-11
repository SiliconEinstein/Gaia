"""Heuristic adversarial review for Gaia claims and solution artifacts."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.packaging import (
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)
from gaia.engine.review._schemas import ReviewFinding, ReviewReport, ReviewSeverity

_STRONG_SHORTCUTS = ("sorry", "admit", "axiom", "assume without proof")
_WEAK_PROVENANCE = ("obvious", "clearly", "trivial", "self-evident")
_TARGET_WEAKENING = ("there exists", "at least one", "some ", " may ", " could ")


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _matches_target(node_id: str, label: str, target: str | None) -> bool:
    if target is None:
        return True
    return target in (node_id, label) or target in node_id or target in label


def _content_for(obj: Any) -> str:
    values = [
        getattr(obj, "content", None),
        getattr(obj, "rationale", None),
        getattr(obj, "label", None),
    ]
    return "\n".join(str(value) for value in values if value)


def _finding(
    *,
    severity: ReviewSeverity,
    location: str,
    message: str,
    detector: str,
    evidence: str,
) -> ReviewFinding:
    return ReviewFinding(
        severity=severity,
        category="redteam",
        location=location,
        message=message,
        detector=detector,
        details={"evidence": evidence},
    )


def _scan_text(location: str, text: str) -> list[ReviewFinding]:
    findings: list[ReviewFinding] = []
    lowered = f" {text.lower()} "

    for phrase in _STRONG_SHORTCUTS:
        if phrase in lowered:
            findings.append(
                _finding(
                    severity=ReviewSeverity.ERROR,
                    location=location,
                    message=f"Potential proof shortcut detected: {phrase!r}",
                    detector="redteam_shortcut",
                    evidence=phrase,
                )
            )

    for phrase in _WEAK_PROVENANCE:
        if phrase in lowered:
            findings.append(
                _finding(
                    severity=ReviewSeverity.WARNING,
                    location=location,
                    message=f"Weak provenance language detected: {phrase!r}",
                    detector="redteam_weak_provenance",
                    evidence=phrase,
                )
            )

    for phrase in _TARGET_WEAKENING:
        if phrase in lowered:
            findings.append(
                _finding(
                    severity=ReviewSeverity.WARNING,
                    location=location,
                    message=f"Possible target weakening language detected: {phrase.strip()!r}",
                    detector="redteam_target_weakening",
                    evidence=phrase.strip(),
                )
            )

    return findings


def _scan_solution_file(path: Path) -> list[ReviewFinding]:
    if not path.exists():
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return [
            _finding(
                severity=ReviewSeverity.WARNING,
                location=str(path),
                message=f"Could not read solution artifact: {exc}",
                detector="redteam_solution_read",
                evidence=str(exc),
            )
        ]
    return _scan_text(str(path), text)


def run_redteam_review(
    pkg_path: str | Path,
    *,
    target: str | None = None,
    backend: str = "heuristic",
    solution: str | Path | None = None,
) -> ReviewReport:
    """Run adversarial review over a package, node, or solution artifact.

    The shipped backend is intentionally heuristic and deterministic so it can
    run in CI without network access or model credentials. LLM backends can be
    added later behind the same report schema.
    """
    if backend != "heuristic":
        raise ValueError("Only the heuristic red-team backend is available")

    pkg_path = Path(pkg_path).resolve()
    findings: list[ReviewFinding] = []

    ensure_package_env(pkg_path)
    loaded = load_gaia_package(str(pkg_path))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)

    matched_nodes = 0
    for knowledge in getattr(compiled.graph, "knowledges", []) or []:
        node_id = str(getattr(knowledge, "id", "") or "")
        label = str(getattr(knowledge, "label", "") or "")
        if not node_id or not _matches_target(node_id, label, target):
            continue
        matched_nodes += 1
        findings.extend(_scan_text(node_id, _content_for(knowledge)))

    for strategy in getattr(compiled.graph, "strategies", []) or []:
        node_id = str(getattr(strategy, "strategy_id", None) or getattr(strategy, "id", "") or "")
        label = str((getattr(strategy, "metadata", None) or {}).get("action_label", ""))
        if not node_id or not _matches_target(node_id, label, target):
            continue
        matched_nodes += 1
        findings.extend(_scan_text(node_id, _content_for(strategy)))
        premises = list(getattr(strategy, "premises", []) or [])
        if not premises:
            findings.append(
                _finding(
                    severity=ReviewSeverity.WARNING,
                    location=node_id,
                    message="Strategy has no premises; adversarial review treats it as unsupported",
                    detector="redteam_empty_premises",
                    evidence="premises=[]",
                )
            )

    for operator in getattr(compiled.graph, "operators", []) or []:
        node_id = str(getattr(operator, "operator_id", None) or getattr(operator, "id", "") or "")
        label = str(getattr(operator, "kind", "") or "")
        if not node_id or not _matches_target(node_id, label, target):
            continue
        matched_nodes += 1
        findings.extend(_scan_text(node_id, _content_for(operator)))

    solution_path = (
        Path(solution).resolve() if solution is not None else pkg_path / "FINAL_ANSWER.md"
    )
    findings.extend(_scan_solution_file(solution_path))

    if target is not None and matched_nodes == 0:
        findings.append(
            ReviewFinding(
                severity=ReviewSeverity.ERROR,
                category="redteam",
                location=target,
                message=f"No node matched red-team target {target!r}",
                detector="redteam_target_resolution",
            )
        )

    has_error = any(f.severity == ReviewSeverity.ERROR for f in findings)
    has_warning = any(f.severity == ReviewSeverity.WARNING for f in findings)
    if has_error:
        status: Literal["pass", "warning", "error"] = "error"
        verdict = "vulnerable"
        summary = "Red-team review found blocking vulnerabilities"
    elif has_warning:
        status = "warning"
        verdict = "uncertain"
        summary = "Red-team review found non-blocking concerns"
    else:
        status = "pass"
        verdict = "robust"
        summary = "Red-team review found no heuristic vulnerabilities"

    return ReviewReport(
        review_id=mint_review_id(None, "redteam"),
        review_type="redteam",
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        status=status,
        summary=summary,
        findings=findings,
        recommendations=[],
        metadata={
            "backend": backend,
            "target": target,
            "solution": str(solution_path) if solution_path.exists() else None,
            "verdict": verdict,
            "successful_attacks": sum(
                1 for finding in findings if finding.severity == ReviewSeverity.ERROR
            ),
        },
    )
