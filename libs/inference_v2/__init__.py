"""BP v2 — theory-compliant belief propagation engine.

This package implements sum-product loopy Belief Propagation strictly
following the formalized theory in docs/foundations/theory/:

  belief-propagation.md  — algorithm specification (§3) and potentials (§2)
  reasoning-hypergraph.md — operator types (§7.3) and factor graph (§5)
  plausible-reasoning.md  — four weak syllogisms (§1.3) that the model satisfies

Key differences from libs/inference (v1):
  - ENTAILMENT uses silence model (bp.md §2.6: C4 = "通常沉默")
  - INDUCTION/ABDUCTION use noisy-AND + leak (bp.md §2.1: C4 ✓)
  - CONTRADICTION/EQUIVALENCE use fixed-eps strength (not a free parameter)
  - Relation variables are full BP participants (no gate_var hack)
  - Five explicit FactorTypes (ENTAILMENT/INDUCTION/ABDUCTION/CONTRADICTION/EQUIVALENCE)
  - String variable IDs throughout
  - BPDiagnostics always populated
  - Junction Tree for exact inference, GBP for region decomposition
  - Unified InferenceEngine auto-selects best algorithm by treewidth

Public API:
  FactorGraph      — bipartite factor graph construction
  FactorType       — enum of five operator types
  CROMWELL_EPS     — system constant ε = 1e-3 (Cromwell's rule)
  BeliefPropagation — loopy BP runner
  BPDiagnostics    — per-variable belief history and convergence info
  BPResult         — return value of BeliefPropagation.run()
"""

from libs.inference_v2.factor_graph import CROMWELL_EPS, FactorGraph, FactorType
from libs.inference_v2.bp import BeliefPropagation, BPDiagnostics, BPResult
from libs.inference_v2.exact import exact_inference, comparison_table
from libs.inference_v2.junction_tree import JunctionTreeInference, jt_treewidth
from libs.inference_v2.gbp import GeneralizedBeliefPropagation, detect_short_cycles
from libs.inference_v2.engine import InferenceEngine, EngineConfig, InferenceResult

__all__ = [
    "FactorGraph",
    "FactorType",
    "CROMWELL_EPS",
    "BeliefPropagation",
    "BPDiagnostics",
    "BPResult",
    "exact_inference",
    "comparison_table",
    "JunctionTreeInference",
    "jt_treewidth",
    "GeneralizedBeliefPropagation",
    "detect_short_cycles",
    "InferenceEngine",
    "EngineConfig",
    "InferenceResult",
]
