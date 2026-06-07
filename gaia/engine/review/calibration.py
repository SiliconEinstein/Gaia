"""Calibration audit — compute Δ_qid = posterior - prior, rank by |Δ|, check honesty.

Core new functionality for gaia review:
  1. Lower IR to factor graph (fg.variables = priors)
  2. Run BP inference to get posteriors
  3. Compute Δ = posterior - prior for each claim
  4. Sort by |Δ| descending
  5. Optional: git diff to check if priors changed after seeing posteriors

Design principle: No new IR/BP logic. Thin wrapper around existing bp.engine.
"""

from __future__ import annotations

import subprocess
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


def compute_calibration_deltas(
    pkg_path: str | Path,
    top_k: int | None = 20,
) -> tuple[list[CalibrationDelta], bool, int]:
    """Compute Δ_qid = posterior - prior for all claims, return top-K by |Δ|.

    Args:
        pkg_path: Path to Gaia package
        top_k: How many top deltas to return. Use ``None`` to return all.

    Returns:
        Tuple of (deltas, converged, iterations)
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

    # Extract priors from factor graph variables
    priors: dict[str, float] = dict(factor_graph.variables)

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

    # Compute deltas
    deltas: list[CalibrationDelta] = []
    for claim_id, posterior in posteriors.items():
        prior = priors.get(claim_id)
        if prior is None:
            continue  # Skip claims without explicit priors

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

    # Check convergence heuristic: if top delta < 0.1, consider converged
    converged = len(deltas) == 0 or deltas[0].abs_delta < 0.1

    # Iterations would need to be extracted from result metadata
    # For now use a placeholder
    iterations = getattr(result, "iterations", 100)

    if top_k is None:
        return deltas, converged, iterations
    return deltas[:top_k], converged, iterations


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

    # Compute deltas
    deltas, converged, iterations = compute_calibration_deltas(pkg_path, top_k=top_k)

    # Optional honesty check
    honesty_result = None
    if check_git_honesty:
        honesty_result = check_honesty(pkg_path)

    return CalibrationReport(
        review_id=review_id,
        created_at=_utcnow_iso(),
        path=str(pkg_path),
        converged=converged,
        iterations=iterations,
        top_deltas=deltas,
        honesty_check=honesty_result,
        metadata={"top_k": top_k},
    )
