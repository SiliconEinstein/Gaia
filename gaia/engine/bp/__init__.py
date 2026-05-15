"""BP v2 — belief propagation aligned with theory and Gaia IR.

Theory: docs/foundations/theory/06-factor-graphs.md, 07-belief-propagation.md
IR lowering: docs/foundations/gaia-ir/07-lowering.md

CLI 主路径使用 `InferenceEngine.run()` 自动 dispatch：
  junction_tree  → treewidth ≤ 20，精确
  trw_bp         → n ≤ 2000 且 treewidth > 20，有界近似
  mean_field     → n > 2000，大图快速近似

本模块下方的 `infer()` 是旧的便利函数，仍保留 `loopy_bp` 强制模式和
大图 loopy-BP fallback 以兼容旧调用；新代码需要和 `gaia infer` 一致时，
应直接使用 `InferenceEngine`。
"""

import warnings

# Re-exported for internal use; not in __all__.
# Alpha 0 cut per 协作单 一-❓4: contract is not access. These names remain
# reachable via internal paths under gaia.engine.bp.{bp,mean_field,trw_bp,exact,lowering}.
from gaia.engine.bp.bp import (
    BeliefPropagation,
    BPDiagnostics,
    BPResult,
)
from gaia.engine.bp.engine import EngineConfig, InferenceEngine, InferenceResult
from gaia.engine.bp.exact import (
    comparison_table,
    exact_inference,
    exact_joint_over,
)
from gaia.engine.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType
from gaia.engine.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.engine.bp.lowering import (
    lower_local_graph,
    lower_operator,
    merge_factor_graphs,
)
from gaia.engine.bp.mean_field import (
    MeanFieldVI,
    MFDiagnostics,
    MFResult,
)
from gaia.engine.bp.trw_bp import (
    TRWBeliefPropagation,
    TRWDiagnostics,
    TRWResult,
)

__all__ = [
    "CROMWELL_EPS",
    "BeliefPropagation",
    "EngineConfig",
    "Factor",
    "FactorGraph",
    "FactorType",
    "InferenceEngine",
    "InferenceResult",
    "JunctionTreeInference",
    "MeanFieldVI",
    "TRWBeliefPropagation",
    "exact_inference",
    "exact_joint_over",
    "infer",
    "jt_treewidth",
    "lower_local_graph",
    "merge_factor_graphs",
]

# 旧便利函数的路由阈值；CLI 使用 InferenceEngine.EngineConfig。
_JT_TREEWIDTH_LIMIT = 20
_LOOPY_BP_NODE_LIMIT = 2000  # legacy infer(): n > 2000 使用 Loopy BP fallback


def infer(
    graph: FactorGraph,
    method: str = "auto",
) -> dict[str, float]:
    """Legacy convenience wrapper: infer FactorGraph marginals.

    Prefer :class:`InferenceEngine` for new code and CLI-parity behavior.

    Parameters
    ----------
    graph:
        已 lower 好的 FactorGraph。
    method:
        "auto"        — 按 treewidth / n 自动选择算法
        "junction_tree" — 强制 JT（精确，treewidth ≤ 20）
        "trw_bp"      — 强制 TRW-BP
        "loopy_bp"    — legacy force Loopy BP
        "mean_field"  — force Mean Field VI

    Returns:
    -------
    dict[str, float]
        变量 ID → P(x=1) 的边缘概率。
    """
    if method == "auto":
        n = len(graph.variables)
        if n > _LOOPY_BP_NODE_LIMIT:
            # Legacy convenience fallback. The CLI's InferenceEngine routes
            # n > 2000 to Mean Field VI instead.
            method = "loopy_bp"
        else:
            tw = jt_treewidth(graph)
            method = "junction_tree" if tw <= _JT_TREEWIDTH_LIMIT else "trw_bp"

    result: TRWResult | MFResult | BPResult

    if method == "junction_tree":
        jt = JunctionTreeInference()
        result = jt.run(graph)
        return result.beliefs

    if method == "trw_bp":
        trw = TRWBeliefPropagation()
        result = trw.run(graph)
        return result.beliefs

    if method == "loopy_bp":
        bp = BeliefPropagation(damping=0.5, max_iterations=500, convergence_threshold=1e-6)
        result = bp.run(graph)
        return result.beliefs

    if method == "mean_field":
        mf = MeanFieldVI()
        result = mf.run(graph)
        return result.beliefs

    raise ValueError(
        f"method must be auto, junction_tree, trw_bp, loopy_bp, or mean_field; got {method!r}"
    )
