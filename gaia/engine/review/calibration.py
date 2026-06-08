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
Those neutral values are not authored priors. Calibration therefore takes the
prior baseline from the authored value Gaia's prior resolver writes onto each
claim (``Knowledge.metadata["prior"]``), restricted to reviewable ``CLAIM``
knowledges, and only for claims the lowering actually installed as a live
class-IV soft prior (membership in ``FactorGraph.unary_factors``). This excludes,
by construction:

  - MaxEnt-baseline claims (no authored prior, not in unary_factors),
  - derived claims and anonymous / structural expression helpers,
  - structural relation defaults (≈1-ε, asserted via hard evidence, not metadata),
  - hard-evidence-pinned claims (popped out of unary_factors).
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
from gaia.engine.ir.knowledge import KnowledgeType, is_structural_expression_helper
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
        deltas: Per-claim prior→posterior deltas for claims with an authored
            prior, sorted by |Δ| descending, truncated to ``top_k`` when
            requested.
        posteriors: Full posterior belief map for every variable, so callers
            can show posterior context even for claims without an authored prior.
        converged: Whether the inference run reported convergence. Exact
            methods (junction tree / brute force) are always converged.
        iterations: Inference iterations actually run (0 for exact methods).
        method_used: Inference method label (jt / trw_bp / mean_field / exact).
        is_exact: Whether the inference method returns exact marginals.
    """

    deltas: list[CalibrationDelta] = field(default_factory=list)
    posteriors: dict[str, float] = field(default_factory=dict)
    converged: bool = False
    iterations: int = 0
    method_used: str = "unknown"
    is_exact: bool = False

    @property
    def reliable(self) -> bool:
        """True when deltas can be trusted: exact, or approximate-but-converged.

        An approximate run that did not converge produces unreliable marginals,
        so the deltas derived from it must not be presented as authoritative.
        """
        return self.is_exact or self.converged


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

    # Authored priors: the value Gaia's prior resolver wrote onto each reviewable
    # CLAIM (metadata["prior"]). Gate on unary_factors membership so we only keep
    # claims the lowering actually installed as a live class-IV soft prior —
    # this drops structural relation defaults, MaxEnt baselines, deliberately
    # ignored helper priors, and hard-evidence-pinned claims.
    labels: dict[str, str] = {}
    authored_priors: dict[str, float] = {}
    for knowledge in compiled.graph.knowledges:
        if not knowledge.id:
            continue
        if knowledge.label:
            labels[knowledge.id] = knowledge.label
        if knowledge.type != KnowledgeType.CLAIM:
            continue
        if is_structural_expression_helper(knowledge):
            continue
        meta = knowledge.metadata or {}
        prior_value = meta.get("prior")
        if prior_value is None or knowledge.id not in factor_graph.unary_factors:
            continue
        authored_priors[knowledge.id] = float(prior_value)

    # Run BP inference
    engine = InferenceEngine()
    result = engine.run(factor_graph)
    posteriors = dict(result.beliefs)

    # Compute deltas only for claims that carry an authored prior.
    deltas: list[CalibrationDelta] = []
    for claim_id, prior in authored_priors.items():
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
        posteriors=posteriors,
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
            "authored_prior_claims": len(computation.deltas),
            "reliable": computation.reliable,
        },
    )
