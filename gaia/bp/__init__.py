"""BP v2 — belief propagation aligned with theory and Gaia IR.

Theory: docs/foundations/theory/06-factor-graphs.md, 07-belief-propagation.md
IR lowering: docs/foundations/gaia-ir/07-lowering.md

算法路由（infer 自动 dispatch）：
  junction_tree  → treewidth ≤ 20，精确
  trw_bp         → 默认近似，n ≤ 2000
  mean_field     → n > 2000，大图快速近似
"""

import warnings

from gaia.bp.engine import EngineConfig, InferenceEngine, InferenceResult
from gaia.bp.exact import comparison_table, exact_inference, exact_joint_over
from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.bp.lowering import lower_local_graph, lower_operator, merge_factor_graphs
from gaia.bp.mean_field import MeanFieldVI, MFDiagnostics, MFResult
from gaia.bp.trw_bp import TRWBeliefPropagation, TRWDiagnostics, TRWResult

__all__ = [
    "CROMWELL_EPS",
    "EngineConfig",
    "Factor",
    "FactorGraph",
    "FactorType",
    "InferenceEngine",
    "InferenceResult",
    "JunctionTreeInference",
    "MFDiagnostics",
    "MFResult",
    "MeanFieldVI",
    "TRWBeliefPropagation",
    "TRWDiagnostics",
    "TRWResult",
    "comparison_table",
    "exact_inference",
    "exact_joint_over",
    "infer",
    "jt_treewidth",
    "lower_local_graph",
    "lower_operator",
    "merge_factor_graphs",
]

# 路由阈值
_JT_TREEWIDTH_LIMIT = 20
_MF_NODE_LIMIT = 2000


def infer(
    graph: FactorGraph,
    method: str = "auto",
) -> dict[str, float]:
    """推断 FactorGraph 中所有变量的边缘概率。.

    Parameters
    ----------
    graph:
        已 lower 好的 FactorGraph。
    method:
        "auto"        — 按 treewidth / n 自动选择算法
        "junction_tree" — 强制 JT（精确，treewidth ≤ 20）
        "trw_bp"      — 强制 TRW-BP
        "mean_field"  — 强制 Mean Field VI

    Returns:
    -------
    dict[str, float]
        变量 ID → P(x=1) 的边缘概率。
    """
    if method == "auto":
        n = len(graph.variables)
        if n > _MF_NODE_LIMIT:
            # Large-graph inference is under active research. Mean Field VI
            # is the only currently-implemented algorithm capable of scaling
            # past ~2000 nodes, but empirically produces 30%~79% error on
            # Gaia's hard-constraint factor graphs (delta-like IMPLICATION /
            # EQUIVALENCE potentials violate the q(x) = Πq_i(x_i) independence
            # assumption). Until hierarchical / distributed TRW-BP is landed,
            # we fall back to Mean Field with a loud warning so large-graph
            # callers know their beliefs are not production-grade.
            warnings.warn(
                f"Large graph inference (n={n} > {_MF_NODE_LIMIT}) falls back "
                f"to Mean Field VI, which has 30%~79% error on hard-constraint "
                f"graphs (Jaynes Class I + IMPLICATION/EQUIVALENCE). Results "
                f"are NOT production-grade. Planned replacement: hierarchical "
                f"(schema/ground) or distributed TRW-BP. "
                f"Pass method='trw_bp' explicitly to bypass and use TRW-BP "
                f"anyway (slower on large n, but accurate).",
                category=UserWarning,
                stacklevel=2,
            )
            method = "mean_field"
        else:
            tw = jt_treewidth(graph)
            method = "junction_tree" if tw <= _JT_TREEWIDTH_LIMIT else "trw_bp"

    if method == "junction_tree":
        jt = JunctionTreeInference()
        result = jt.run(graph)
        return result.beliefs

    if method == "trw_bp":
        trw = TRWBeliefPropagation()
        result = trw.run(graph)
        return result.beliefs

    if method == "mean_field":
        mf = MeanFieldVI()
        result = mf.run(graph)
        return result.beliefs

    raise ValueError(f"method must be auto, junction_tree, trw_bp, or mean_field; got {method!r}")
