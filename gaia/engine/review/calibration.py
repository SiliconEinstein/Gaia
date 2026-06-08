"""Calibration audit — compute Δ_qid = posterior - prior, rank by |Δ|, check honesty.

Core new functionality for gaia review:
  1. Lower IR to factor graph
  2. Run BP inference to get posteriors
  3. Compute Δ = posterior - prior only for claims with an *explicit* prior
  4. Sort by |Δ| descending
  5. Optional: git diff to check if priors changed after seeing posteriors

Design principle: No new IR/BP logic. Thin wrapper around existing bp.engine.

Prior source (important): a Gaia factor graph stores a neutral 0.5 display
measure for *every* variable in ``FactorGraph.variables`` — including derived
claims, anonymous expression helpers, and claims that were never given a prior.
Those neutral values are not authored priors. The authored class-IV soft priors
(lowered from ``register_prior`` / claim metadata) live in
``FactorGraph.unary_factors``. Calibration therefore reads priors from
``unary_factors`` so it never reports a derived/helper/missing-prior claim as if
it carried an explicit prior=0.5.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from gaia.engine.bp import lower_local_graph
from gaia.engine.bp.engine import InferenceEngine
from gaia.engine.inquiry.review_manifest import load_or_generate_review_manifest
from gaia.engine.inquiry.snapshot import mint_review_id
from gaia.engine.packaging import (
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)
from gaia.engine.review._schemas import CalibrationDelta, CalibrationReport


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


@dataclass
class CalibrationComputation:
    """Result of a calibration computation.

    Attributes:
        deltas: Per-claim prior→posterior deltas, sorted by |Δ| descending,
            truncated to ``top_k`` when requested.
        converged: Whether the inference run reported convergence. Exact
            methods (junction tree / brute force) are always converged.
        iterations: Inference iterations actually run (0 for exact methods).
        method_used: Inference method label (jt / trw_bp / mean_field / exact).
        is_exact: Whether the inference method returns exact marginals.
    """

    deltas: list[CalibrationDelta] = field(default_factory=list)
    converged: bool = False
    iterations: int = 0
    method_used: str = "unknown"
    is_exact: bool = False


def compute_calibration_deltas(
    pkg_path: str | Path,
    top_k: int | None = 20,
) -> CalibrationComputation:
    """Compute Δ_qid = posterior - prior for claims with an explicit prior.

    Args:
        pkg_path: Path to Gaia package
        top_k: How many top deltas to return. Use ``None`` to return all.

    Returns:
        CalibrationComputation with deltas plus real inference metadata.
    """
    pkg_path = Path(pkg_path)

    # Load and compile package
    ensure_package_env(pkg_path)
    loaded = load_gaia_package(str(pkg_path))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)

    # Load review manifest (for lowering)
    review_manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)

    # Lower to factor graph
    factor_graph = lower_local_graph(compiled.graph, review_manifest=review_manifest)

    # Explicit authored priors only — NOT the neutral 0.5 display measure that
    # FactorGraph.variables holds for every node. unary_factors is populated by
    # add_variable(prior=...) which lowering calls only for claims with a
    # register_prior / metadata prior (expression helpers are filtered out).
    explicit_priors: dict[str, float] = dict(factor_graph.unary_factors)

    # Run BP inference
    engine = InferenceEngine()
    result = engine.run(factor_graph)

    # Get posteriors from BP result
    posteriors = result.beliefs

    # Get labels
    labels = {}
    for knowledge in compiled.graph.knowledges:
        if knowledge.id and knowledge.label:
            labels[knowledge.id] = knowledge.label

    # Compute deltas only for claims that carry an explicit prior.
    deltas: list[CalibrationDelta] = []
    for claim_id, prior in explicit_priors.items():
        posterior = posteriors.get(claim_id)
        if posterior is None:
            continue

        delta = posterior - prior
        deltas.append(
            CalibrationDelta(
                claim_qid=claim_id,
                claim_label=labels.get(claim_id, claim_id),
                prior=prior,
                posterior=posterior,
                delta=delta,
                abs_delta=abs(delta),
            )
        )

    # Sort by abs_delta descending
    deltas.sort(key=lambda d: d.abs_delta, reverse=True)

    # Real inference convergence — not a delta heuristic. Exact methods report
    # converged=True and iterations_run=0 because they do not iterate.
    diagnostics = result.diagnostics
    converged = bool(getattr(diagnostics, "converged", False))
    iterations = int(getattr(diagnostics, "iterations_run", 0))

    selected = deltas if top_k is None else deltas[:top_k]
    return CalibrationComputation(
        deltas=selected,
        converged=converged,
        iterations=iterations,
        method_used=result.method_used,
        is_exact=result.is_exact,
    )


def check_honesty(pkg_path: str | Path) -> dict[str, Any] | None:
    """Check if priors were modified after seeing posteriors (git diff scan).

    Args:
        pkg_path: Path to Gaia package

    Returns:
        Dict with git diff results, or None if no git repo or no changes
    """
    pkg_path = Path(pkg_path)

    # Check if this is a git repo
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            cwd=pkg_path,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            return None
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None

    # Scan all Python source diffs instead of assuming a single plan.py file.
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD", "--", "*.py"],
            cwd=pkg_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {"status": "clean", "message": "No prior changes detected"}

        # Parse diff to find prior-related changes and keep file context.
        diff_lines = result.stdout.split("\n")
        prior_changes: list[str] = []
        current_file: str | None = None
        for line in diff_lines:
            if line.startswith("diff --git "):
                current_file = line
                continue
            if line.startswith(("+", "-")) and "prior" in line.lower():
                if current_file is not None and (
                    not prior_changes or prior_changes[-1] != current_file
                ):
                    prior_changes.append(current_file)
                prior_changes.append(line)

        if not prior_changes:
            return {"status": "clean", "message": "No prior changes detected"}

        return {
            "status": "suspicious",
            "message": f"Found {len(prior_changes)} prior-related changes",
            "changes": prior_changes[:20],
        }

    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None


def run_calibration_review(
    pkg_path: str | Path,
    top_k: int = 20,
    check_git_honesty: bool = False,
) -> CalibrationReport:
    """Run full calibration review: compute deltas + optional honesty check.

    Args:
        pkg_path: Path to Gaia package
        top_k: Number of top deltas to report
        check_git_honesty: Whether to run git diff honesty check

    Returns:
        CalibrationReport with top deltas and optional honesty results
    """
    pkg_path = Path(pkg_path)
    review_id = mint_review_id(None, "calibration")

    # Compute deltas + real inference metadata
    computation = compute_calibration_deltas(pkg_path, top_k=top_k)

    # Optional honesty check
    honesty_result = None
    if check_git_honesty:
        honesty_result = check_honesty(pkg_path)

    return CalibrationReport(
        review_id=review_id,
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        converged=computation.converged,
        iterations=computation.iterations,
        method_used=computation.method_used,
        is_exact=computation.is_exact,
        top_deltas=computation.deltas,
        honesty_check=honesty_result,
        metadata={
            "top_k": top_k,
            "explicit_prior_claims": len(computation.deltas),
        },
    )
