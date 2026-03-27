"""Unified inference engine — automatically selects the best algorithm.

Exposes a single InferenceEngine.run() method that chooses among:

  - JunctionTreeInference: exact, O(n * 2^w), best for treewidth ≤ JT_MAX_TREEWIDTH
  - GeneralizedBeliefPropagation: near-exact for graphs with identifiable short
    cycles, best for JT_MAX_TREEWIDTH < treewidth ≤ GBP_MAX_TREEWIDTH
  - BeliefPropagation: loopy BP approximation, always runs but may have errors
    on short cycles; fallback for very large/dense graphs

Decision thresholds (tunable):
  JT_MAX_TREEWIDTH = 15   — JT is exact and fast up to treewidth 15
  GBP_MAX_TREEWIDTH = 30  — GBP handles higher treewidths via region decomposition

For Gaia's factor graphs (typically n ≤ 200, treewidth ≤ 10), JT is almost
always selected, giving exact results in milliseconds.

Usage:
    from libs.inference_v2.engine import InferenceEngine

    engine = InferenceEngine()
    result = engine.run(graph)           # auto-select
    result = engine.run(graph, method="jt")    # force JT
    result = engine.run(graph, method="gbp")   # force GBP
    result = engine.run(graph, method="bp")    # force loopy BP
    result = engine.run(graph, method="exact") # force brute-force (small graphs only)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from libs.inference_v2.bp import BeliefPropagation, BPResult
from libs.inference_v2.exact import exact_inference
from libs.inference_v2.factor_graph import FactorGraph
from libs.inference_v2.gbp import GeneralizedBeliefPropagation
from libs.inference_v2.junction_tree import JunctionTreeInference, jt_treewidth

__all__ = ["InferenceEngine", "EngineConfig", "MethodChoice"]

logger = logging.getLogger(__name__)

MethodChoice = Literal["auto", "jt", "gbp", "bp", "exact"]

# Treewidth thresholds for automatic algorithm selection
JT_MAX_TREEWIDTH: int = 15  # JT exact: 2^15 = 32K states per clique, fast
GBP_MAX_TREEWIDTH: int = 30  # GBP region decomposition covers most practical cases
EXACT_MAX_VARS: int = 26  # Brute-force enumeration limit (2^26 = 67M states)


@dataclass
class EngineConfig:
    """Configuration for the unified inference engine.

    Attributes
    ----------
    jt_max_treewidth:
        Use JT (exact) when estimated treewidth ≤ this value.
    gbp_max_treewidth:
        Use GBP when jt_max_treewidth < treewidth ≤ gbp_max_treewidth.
        Above this threshold, fall back to loopy BP.
    gbp_max_cycle_len:
        Maximum cycle length to detect in GBP's region graph construction.
    bp_damping:
        Damping factor for loopy BP and inter-region GBP.
    bp_max_iter:
        Maximum iterations for loopy BP.
    bp_threshold:
        Convergence threshold for loopy BP.
    exact_max_vars:
        Maximum variables for brute-force exact inference.
    """

    jt_max_treewidth: int = JT_MAX_TREEWIDTH
    gbp_max_treewidth: int = GBP_MAX_TREEWIDTH
    gbp_max_cycle_len: int = 6
    bp_damping: float = 0.5
    bp_max_iter: int = 200
    bp_threshold: float = 1e-8
    exact_max_vars: int = EXACT_MAX_VARS


@dataclass
class InferenceResult:
    """Extended result from InferenceEngine with algorithm metadata.

    Wraps BPResult and adds engine-level diagnostics.

    Attributes
    ----------
    bp_result:
        The underlying BPResult (beliefs + diagnostics).
    method_used:
        Which algorithm was selected: 'jt', 'gbp', 'bp', or 'exact'.
    treewidth:
        Estimated treewidth of the factor graph (-1 if not computed).
    elapsed_ms:
        Wall-clock time for inference in milliseconds.
    is_exact:
        True if the algorithm is guaranteed to return exact marginals.
    """

    bp_result: BPResult
    method_used: str = "unknown"
    treewidth: int = -1
    elapsed_ms: float = 0.0
    is_exact: bool = False

    @property
    def beliefs(self) -> dict[str, float]:
        """Shortcut to beliefs dict."""
        return self.bp_result.beliefs

    @property
    def diagnostics(self):
        """Shortcut to BPDiagnostics."""
        return self.bp_result.diagnostics


class InferenceEngine:
    """Unified inference engine with automatic algorithm selection.

    Chooses the most accurate algorithm that is computationally feasible
    for the given factor graph.

    Priority (when method='auto'):
      1. JT: treewidth ≤ jt_max_treewidth → exact, fastest for small treewidth
      2. GBP: jt_max_treewidth < tw ≤ gbp_max_treewidth → region decomposition
      3. BP: tw > gbp_max_treewidth → loopy BP approximation

    Parameters
    ----------
    config:
        EngineConfig controlling thresholds and algorithm parameters.
        Defaults to EngineConfig() with recommended settings.
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        self._jt = JunctionTreeInference()
        self._gbp = GeneralizedBeliefPropagation(
            max_cycle_len=self._config.gbp_max_cycle_len,
            bp_damping=self._config.bp_damping,
            bp_max_iter=self._config.bp_max_iter,
            bp_threshold=self._config.bp_threshold,
        )
        self._bp = BeliefPropagation(
            damping=self._config.bp_damping,
            max_iterations=self._config.bp_max_iter,
            convergence_threshold=self._config.bp_threshold,
        )

    def run(
        self,
        graph: FactorGraph,
        method: MethodChoice = "auto",
    ) -> InferenceResult:
        """Run inference on *graph* using the specified or auto-selected method.

        Parameters
        ----------
        graph:
            A validated FactorGraph.
        method:
            'auto' (default): automatically select based on treewidth.
            'jt': force Junction Tree (exact, may be slow for high treewidth).
            'gbp': force Generalized BP (region decomposition).
            'bp': force loopy BP (fast but approximate on cyclic graphs).
            'exact': force brute-force enumeration (only feasible for ≤26 vars).

        Returns
        -------
        InferenceResult
            .beliefs: dict[str, float] — posterior P(v=1) per variable
            .method_used: which algorithm ran
            .treewidth: estimated graph treewidth
            .elapsed_ms: wall-clock time
            .is_exact: whether the result is mathematically exact
        """
        cfg = self._config
        t0 = time.perf_counter()

        # Compute treewidth once (fast, O(n^2))
        tw = jt_treewidth(graph) if method in ("auto", "jt", "gbp") else -1

        if method == "exact":
            n = len(graph.variables)
            if n > cfg.exact_max_vars:
                raise ValueError(
                    f"Graph has {n} variables, too many for brute-force "
                    f"exact inference (max {cfg.exact_max_vars}). "
                    "Use method='jt' for exact inference up to treewidth ~15."
                )
            beliefs, Z = exact_inference(graph)
            from libs.inference_v2.bp import BPDiagnostics

            diag = BPDiagnostics()
            diag.converged = True
            for v, b in beliefs.items():
                diag.belief_history[v] = [b]
            bp_result = BPResult(beliefs=beliefs, diagnostics=diag)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: exact, %d vars, %.1fms", n, elapsed)
            return InferenceResult(
                bp_result=bp_result,
                method_used="exact",
                treewidth=-1,
                elapsed_ms=elapsed,
                is_exact=True,
            )

        elif method == "jt" or (method == "auto" and tw <= cfg.jt_max_treewidth):
            bp_result = self._jt.run(graph)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: JT (exact), treewidth=%d, %.1fms", tw, elapsed)
            return InferenceResult(
                bp_result=bp_result,
                method_used="jt",
                treewidth=tw,
                elapsed_ms=elapsed,
                is_exact=True,
            )

        elif method == "gbp" or (method == "auto" and tw <= cfg.gbp_max_treewidth):
            bp_result = self._gbp.run(graph)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: GBP, treewidth=%d, %.1fms", tw, elapsed)
            return InferenceResult(
                bp_result=bp_result,
                method_used="gbp",
                treewidth=tw,
                elapsed_ms=elapsed,
                is_exact=(tw <= cfg.jt_max_treewidth),
            )

        else:
            # method == "bp" or treewidth > gbp_max_treewidth
            bp_result = self._bp.run(graph)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: loopy BP, treewidth=%d, %.1fms", tw, elapsed)
            return InferenceResult(
                bp_result=bp_result,
                method_used="bp",
                treewidth=tw,
                elapsed_ms=elapsed,
                is_exact=False,
            )

    def benchmark(self, graph: FactorGraph) -> dict[str, dict]:
        """Run all feasible methods and return a comparison dict.

        Returns dict: method_name -> {'beliefs': ..., 'elapsed_ms': ..., 'is_exact': ...}
        Skips exact brute-force if graph has > EXACT_MAX_VARS variables.
        """
        results: dict[str, dict] = {}

        for method in ("jt", "gbp", "bp"):
            r = self.run(graph, method=method)  # type: ignore
            results[method] = {
                "beliefs": r.beliefs,
                "elapsed_ms": r.elapsed_ms,
                "is_exact": r.is_exact,
                "treewidth": r.treewidth,
            }

        if len(graph.variables) <= self._config.exact_max_vars:
            r = self.run(graph, method="exact")
            results["exact"] = {
                "beliefs": r.beliefs,
                "elapsed_ms": r.elapsed_ms,
                "is_exact": True,
                "treewidth": -1,
            }

        return results
