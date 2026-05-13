"""Unified inference engine — automatically selects the best algorithm.

Exposes a single InferenceEngine.run() method that chooses among:

  - JunctionTreeInference: exact, O(n * 2^w), best for treewidth ≤ JT_MAX_TREEWIDTH
  - TRWBeliefPropagation: bounded approximate, default for n ≤ MF_NODE_LIMIT
  - MeanFieldVI: fast approximate, for n > MF_NODE_LIMIT

Decision thresholds (tunable):
  JT_MAX_TREEWIDTH = 20   — JT is exact and fast up to treewidth 20
  MF_NODE_LIMIT = 2000    — Mean Field for very large graphs

Usage:
    from gaia.bp.engine import InferenceEngine

    engine = InferenceEngine()
    result = engine.run(graph)              # auto-select
    result = engine.run(graph, method="jt")       # force JT
    result = engine.run(graph, method="trw_bp")   # force TRW-BP
    result = engine.run(graph, method="mean_field") # force Mean Field
    result = engine.run(graph, method="exact")    # force brute-force (small graphs only)
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Literal

from gaia.bp.exact import exact_inference
from gaia.bp.factor_graph import FactorGraph
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth
from gaia.bp.mean_field import MeanFieldVI, MFDiagnostics, MFResult
from gaia.bp.trw_bp import TRWBeliefPropagation, TRWDiagnostics, TRWResult

__all__ = ["EngineConfig", "InferenceEngine", "InferenceResult", "MethodChoice"]

logger = logging.getLogger(__name__)

MethodChoice = Literal["auto", "jt", "trw_bp", "mean_field", "exact"]

# 算法路由阈值
JT_MAX_TREEWIDTH: int = 20   # JT 精确推断上限
MF_NODE_LIMIT: int = 2000    # 超过此节点数用 Mean Field
EXACT_MAX_VARS: int = 26     # 暴力枚举上限（2^26 ≈ 67M 状态）


@dataclass
class EngineConfig:
    """InferenceEngine 的配置参数。

    Attributes:
    jt_max_treewidth:
        treewidth ≤ 此值时使用 JT（精确）。
    mf_node_limit:
        节点数 > 此值时使用 Mean Field VI。
    trw_damping:
        TRW-BP 阻尼系数。
    trw_max_iter:
        TRW-BP 最大迭代次数。
    trw_threshold:
        TRW-BP 收敛阈值。
    mf_max_iter:
        Mean Field 最大迭代次数。
    exact_max_vars:
        暴力枚举最大变量数。
    """

    jt_max_treewidth: int = JT_MAX_TREEWIDTH
    mf_node_limit: int = MF_NODE_LIMIT
    trw_damping: float = 0.5
    trw_max_iter: int = 200
    trw_threshold: float = 1e-8
    mf_max_iter: int = 500
    exact_max_vars: int = EXACT_MAX_VARS


@dataclass
class InferenceResult:
    """InferenceEngine 的返回值，包含推断结果和算法元数据。

    Attributes:
    result:
        底层算法的结果（TRWResult 或 MFResult）。
    method_used:
        实际使用的算法：'jt', 'trw_bp', 'mean_field', 或 'exact'。
    treewidth:
        因子图的估计树宽（未计算时为 -1）。
    elapsed_ms:
        推断耗时（毫秒）。
    is_exact:
        True 表示算法保证返回精确边缘概率。
    """

    result: TRWResult | MFResult
    method_used: str = "unknown"
    treewidth: int = -1
    elapsed_ms: float = 0.0
    is_exact: bool = False

    @property
    def beliefs(self) -> dict[str, float]:
        """快捷访问 beliefs 字典。"""
        return self.result.beliefs

    @property
    def diagnostics(self) -> TRWDiagnostics | MFDiagnostics:
        """快捷访问 diagnostics。"""
        return self.result.diagnostics


class InferenceEngine:
    """统一推断引擎，自动选择最优算法。

    自动路由策略（method='auto'）：
      1. n > mf_node_limit → Mean Field VI（大图快速近似）
      2. treewidth ≤ jt_max_treewidth → JT（精确）
      3. 其他 → TRW-BP（有界近似）

    Args:
    config:
        EngineConfig，控制路由阈值和算法参数。
    """

    def __init__(self, config: EngineConfig | None = None) -> None:
        self._config = config or EngineConfig()
        cfg = self._config
        self._jt = JunctionTreeInference()
        self._trw = TRWBeliefPropagation(
            damping=cfg.trw_damping,
            max_iterations=cfg.trw_max_iter,
            convergence_threshold=cfg.trw_threshold,
        )
        self._mf = MeanFieldVI(max_iterations=cfg.mf_max_iter)

    def run(
        self,
        graph: FactorGraph,
        method: MethodChoice = "auto",
    ) -> InferenceResult:
        """在 graph 上运行推断。

        Args:
        graph:
            已 lower 好的 FactorGraph。
        method:
            'auto'（默认）：按 n 和 treewidth 自动选择。
            'jt'：强制 JT（精确，treewidth ≤ 20）。
            'trw_bp'：强制 TRW-BP。
            'mean_field'：强制 Mean Field VI。
            'exact'：强制暴力枚举（仅适用于小图）。

        Returns:
            InferenceResult，包含边缘概率、算法元数据和耗时。
        """
        cfg = self._config
        t0 = time.perf_counter()

        if method == "exact":
            n = len(graph.variables)
            if n > cfg.exact_max_vars:
                raise ValueError(
                    f"图有 {n} 个变量，超过暴力枚举上限 {cfg.exact_max_vars}。"
                    "请使用 method='jt' 进行精确推断。"
                )
            beliefs, _Z = exact_inference(graph)
            diag = TRWDiagnostics()
            diag.converged = True
            for v, b in beliefs.items():
                diag.belief_history[v] = [b]
            result = TRWResult(beliefs=beliefs, diagnostics=diag)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: exact, %d vars, %.1fms", n, elapsed)
            return InferenceResult(
                result=result, method_used="exact",
                treewidth=-1, elapsed_ms=elapsed, is_exact=True,
            )

        if method == "auto":
            n = len(graph.variables)
            if n > cfg.mf_node_limit:
                method = "mean_field"
            else:
                tw = jt_treewidth(graph)
                method = "jt" if tw <= cfg.jt_max_treewidth else "trw_bp"

        if method == "jt":
            tw = jt_treewidth(graph)
            result = self._jt.run(graph)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: JT (exact), treewidth=%d, %.1fms", tw, elapsed)
            return InferenceResult(
                result=result, method_used="jt",
                treewidth=tw, elapsed_ms=elapsed, is_exact=True,
            )

        if method == "trw_bp":
            tw = jt_treewidth(graph) if len(graph.variables) <= cfg.mf_node_limit else -1
            result = self._trw.run(graph)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: TRW-BP, treewidth=%d, %.1fms", tw, elapsed)
            return InferenceResult(
                result=result, method_used="trw_bp",
                treewidth=tw, elapsed_ms=elapsed, is_exact=False,
            )

        if method == "mean_field":
            result = self._mf.run(graph)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.info("InferenceEngine: Mean Field, %d vars, %.1fms",
                        len(graph.variables), elapsed)
            return InferenceResult(
                result=result, method_used="mean_field",
                treewidth=-1, elapsed_ms=elapsed, is_exact=False,
            )

        raise ValueError(
            f"method 必须是 'auto', 'jt', 'trw_bp', 'mean_field', 或 'exact'；"
            f"收到 {method!r}"
        )

    def benchmark(self, graph: FactorGraph) -> dict[str, dict[str, object]]:
        """运行所有可行算法并返回对比结果。"""
        results: dict[str, dict[str, object]] = {}
        for m in ("jt", "trw_bp", "mean_field"):
            r = self.run(graph, method=m)  # type: ignore[arg-type]
            results[m] = {
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
