"""BP v2 — belief propagation aligned with theory and Gaia IR.

Theory: docs/foundations/theory/06-factor-graphs.md, 07-belief-propagation.md
IR lowering: docs/foundations/gaia-ir/07-lowering.md

Factor types: deterministic operators (IR OperatorType), SOFT_ENTAILMENT
(↝ with p1,p2), CONDITIONAL (full CPT for infer), and PAIRWISE_POTENTIAL
(normalized association potential). String variable IDs, Cromwell clamping,
Junction Tree / GBP / loopy BP / exact enumeration, InferenceEngine.
"""

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType
from gaia.bp.bp import BeliefPropagation, BPDiagnostics, BPResult
from gaia.bp.exact import comparison_table, exact_inference, exact_joint_over
from gaia.bp.engine import EngineConfig, InferenceEngine, InferenceResult
from gaia.bp.gbp import GeneralizedBeliefPropagation, detect_short_cycles
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.bp.lowering import lower_local_graph, lower_operator, merge_factor_graphs

__all__ = [
    "BeliefPropagation",
    "BPDiagnostics",
    "BPResult",
    "CROMWELL_EPS",
    "EngineConfig",
    "Factor",
    "FactorGraph",
    "FactorType",
    "GeneralizedBeliefPropagation",
    "InferenceEngine",
    "InferenceResult",
    "JunctionTreeInference",
    "comparison_table",
    "exact_joint_over",
    "detect_short_cycles",
    "exact_inference",
    "jt_treewidth",
    "lower_local_graph",
    "lower_operator",
    "merge_factor_graphs",
]
