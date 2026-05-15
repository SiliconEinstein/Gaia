# ruff: noqa: D415, E501
"""测试 Loopy BP 在有环图上的表现

使用 CONDITIONAL 因子创建双向依赖，形成真正的环。
"""

import time

from gaia.engine.bp.bp import BeliefPropagation
from gaia.engine.bp.factor_graph import CROMWELL_EPS, FactorGraph, FactorType
from gaia.engine.bp.trw_bp import TRWBeliefPropagation


def build_cycle_graph(cycle_length: int) -> FactorGraph:
    """构建环形图：v0 → v1 → v2 → ... → v_{n-1} → v0

    使用 CONDITIONAL 因子创建循环依赖。
    每个节点既是前一个节点的结论，又是后一个节点的前提。
    """
    fg = FactorGraph()

    # 添加变量
    for i in range(cycle_length):
        fg.add_variable(f"v_{i}", prior=0.5 + 0.1 * (i % 3))  # 不同的先验

    # 添加 CONDITIONAL 因子形成环
    for i in range(cycle_length):
        next_i = (i + 1) % cycle_length
        helper = f"h_{i}"
        fg.add_variable(helper)

        fg.add_factor(
            f"cond_{i}",
            FactorType.CONDITIONAL,
            [f"v_{i}", helper],
            f"v_{next_i}",
            cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.85),
        )

    return fg


def build_diamond_cycles(num_diamonds: int) -> FactorGraph:
    """构建菱形结构，每个菱形内部有环

    每个菱形：
        a → b ← c → d ← a  (形成环)
    """
    fg = FactorGraph()

    for i in range(num_diamonds):
        a = f"a_{i}"
        b = f"b_{i}"
        c = f"c_{i}"
        d = f"d_{i}"

        # 添加变量
        fg.add_variable(a, prior=0.7)
        fg.add_variable(b, prior=0.5)
        fg.add_variable(c, prior=0.5)
        fg.add_variable(d, prior=0.5)

        # a → b
        h_ab = f"h_ab_{i}"
        fg.add_variable(h_ab)
        fg.add_factor(
            f"f_ab_{i}",
            FactorType.CONDITIONAL,
            [a, h_ab],
            b,
            cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.8),
        )

        # c → b (两个前提指向同一结论，形成汇聚)
        h_cb = f"h_cb_{i}"
        fg.add_variable(h_cb)
        fg.add_factor(
            f"f_cb_{i}",
            FactorType.CONDITIONAL,
            [c, h_cb],
            b,
            cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.8),
        )

        # b → d
        h_bd = f"h_bd_{i}"
        fg.add_variable(h_bd)
        fg.add_factor(
            f"f_bd_{i}",
            FactorType.CONDITIONAL,
            [b, h_bd],
            d,
            cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.8),
        )

        # d → c (形成环：c → b → d → c)
        h_dc = f"h_dc_{i}"
        fg.add_variable(h_dc)
        fg.add_factor(
            f"f_dc_{i}",
            FactorType.CONDITIONAL,
            [d, h_dc],
            c,
            cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.8),
        )

    return fg


def test_simple_cycles():
    """测试简单环"""
    print("=" * 70)
    print("简单环测试")
    print("=" * 70)

    for cycle_len in [3, 5, 10, 20]:
        print(f"\n{'=' * 70}")
        print(f"环长度: {cycle_len}")
        print(f"{'=' * 70}")

        fg = build_cycle_graph(cycle_len)
        n_vars = len(fg.variables)

        print(f"变量数: {n_vars}, 因子数: {len(fg.factors)}")

        # TRW-BP
        print("\n[1/2] TRW-BP...")
        t0 = time.time()
        trw = TRWBeliefPropagation(max_iterations=500, convergence_threshold=1e-6)
        trw_result = trw.run(fg)
        trw_time = time.time() - t0
        print(
            f"  耗时: {trw_time:.3f}s, 迭代: {trw_result.diagnostics.iterations_run}, "
            f"收敛: {trw_result.diagnostics.converged}"
        )

        # Loopy BP
        print("\n[2/2] Loopy BP...")
        t0 = time.time()
        bp = BeliefPropagation(damping=0.5, max_iterations=500, convergence_threshold=1e-6)
        bp_result = bp.run(fg)
        bp_time = time.time() - t0
        print(
            f"  耗时: {bp_time:.3f}s, 迭代: {bp_result.diagnostics.iterations_run}, "
            f"收敛: {bp_result.diagnostics.converged}"
        )

        # 对比
        max_diff = 0.0
        for var in fg.variables:
            diff = abs(trw_result.beliefs[var] - bp_result.beliefs[var])
            max_diff = max(max_diff, diff)

        print(f"\n最大差异: {max_diff:.9f}")
        print(f"加速比: {trw_time / bp_time:.2f}x")

        # 检查信念值
        beliefs = [bp_result.beliefs[f"v_{i}"] for i in range(cycle_len)]
        print(f"信念值范围: [{min(beliefs):.4f}, {max(beliefs):.4f}]")
        print(
            f"信念值标准差: {(sum((b - sum(beliefs) / len(beliefs)) ** 2 for b in beliefs) / len(beliefs)) ** 0.5:.6f}"
        )


def test_diamond_cycles():
    """测试菱形环"""
    print("\n" + "=" * 70)
    print("菱形环测试")
    print("=" * 70)

    for num_diamonds in [10, 50, 100]:
        print(f"\n{'=' * 70}")
        print(f"{num_diamonds} 个菱形")
        print(f"{'=' * 70}")

        fg = build_diamond_cycles(num_diamonds)
        n_vars = len(fg.variables)

        print(f"变量数: {n_vars}, 因子数: {len(fg.factors)}")

        # Loopy BP
        print("\nLoopy BP...")
        t0 = time.time()
        bp = BeliefPropagation(damping=0.5, max_iterations=500, convergence_threshold=1e-6)
        bp_result = bp.run(fg)
        bp_time = time.time() - t0
        print(
            f"  耗时: {bp_time:.3f}s, 迭代: {bp_result.diagnostics.iterations_run}, "
            f"收敛: {bp_result.diagnostics.converged}"
        )

        # 检查信念值范围
        beliefs = list(bp_result.beliefs.values())
        print(f"  信念范围: [{min(beliefs):.4f}, {max(beliefs):.4f}]")


def main():
    """主测试流程"""
    print("=" * 70)
    print("Loopy BP 有环图测试")
    print("=" * 70)
    print("\n使用 CONDITIONAL 因子创建循环依赖")

    # 1. 简单环
    test_simple_cycles()

    # 2. 菱形环
    test_diamond_cycles()

    print("\n" + "=" * 70)
    print("总结")
    print("=" * 70)
    print("\n关键发现：")
    print("1. CONDITIONAL 因子可以产生循环依赖")
    print("2. Loopy BP 在有环图上的收敛性")
    print("3. 与 TRW-BP 的差异")


if __name__ == "__main__":
    main()
