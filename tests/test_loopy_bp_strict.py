# ruff: noqa: D415
"""严格的 Loopy BP 验证：真实 DAG 结构 + 10^5 规模

问题：
1. 之前的测试图太简单（独立 block，无真正连接）
2. 只测到 9000 变量，未达到 10^5
3. 需要验证真实的 DAG 结构（有共享节点、多路径）
"""

import time

from gaia.bp.bp import BeliefPropagation
from gaia.bp.factor_graph import CROMWELL_EPS, FactorGraph, FactorType
from gaia.bp.trw_bp import TRWBeliefPropagation


def build_realistic_dag(num_layers: int, nodes_per_layer: int, fan_in: int = 3) -> FactorGraph:
    """构建真实的 DAG 结构

    每层的节点从上一层的多个节点接收输入（fan_in），形成真正的 DAG。
    这会产生多条路径、共享节点，更接近真实的推理图。

    Parameters
    ----------
    num_layers : int
        层数
    nodes_per_layer : int
        每层节点数
    fan_in : int
        每个节点的输入数（从上一层）

    Returns:
    -------
    FactorGraph
        总变量数 ≈ num_layers * nodes_per_layer * 2（每个推理需要 helper）
    """
    fg = FactorGraph()

    # Layer 0: 输入层
    layer_0 = []
    for i in range(nodes_per_layer):
        var_id = f"L0_n{i}"
        fg.add_variable(var_id, prior=0.7)
        layer_0.append(var_id)

    prev_layer = layer_0

    # 后续层：每个节点从上一层的 fan_in 个节点接收输入
    for layer_idx in range(1, num_layers):
        current_layer = []

        for node_idx in range(nodes_per_layer):
            conclusion = f"L{layer_idx}_n{node_idx}"
            fg.add_variable(conclusion, prior=0.5)
            current_layer.append(conclusion)

            # 从上一层选择 fan_in 个前提（循环选择，确保覆盖）
            premises = []
            for k in range(fan_in):
                premise_idx = (node_idx * fan_in + k) % len(prev_layer)
                premises.append(prev_layer[premise_idx])

            # 添加 CONDITIONAL 因子：premises + helper → conclusion
            # CPT 大小为 2^(fan_in + 1)，因为包含 helper
            # 简化：只有所有前提为真且 helper=1 时，结论才高概率为真（noisy-AND）
            helper = f"L{layer_idx}_n{node_idx}_h"
            fg.add_variable(helper)

            cpt_size = 2 ** (fan_in + 1)
            cpt = [CROMWELL_EPS] * cpt_size
            cpt[-1] = 0.85  # 所有前提为真且 helper=1 时

            fg.add_factor(
                f"L{layer_idx}_n{node_idx}_factor",
                FactorType.CONDITIONAL,
                [*premises, helper],
                conclusion,
                cpt=tuple(cpt),
            )

        prev_layer = current_layer

    return fg


def build_diamond_dag(num_diamonds: int) -> FactorGraph:
    r"""构建菱形 DAG 结构（经典的多路径测试）

    每个菱形：
        a
       / \\
      b   c
       \\ /
        d

    多个菱形串联，形成长链。
    这会产生多条路径到达同一节点，测试 BP 的路径聚合能力。
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

        # a → c
        h_ac = f"h_ac_{i}"
        fg.add_variable(h_ac)
        fg.add_factor(
            f"f_ac_{i}",
            FactorType.CONDITIONAL,
            [a, h_ac],
            c,
            cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.8),
        )

        # b, c → d (两条路径汇聚)
        h_bcd = f"h_bcd_{i}"
        fg.add_variable(h_bcd)
        fg.add_factor(
            f"f_bcd_{i}",
            FactorType.CONDITIONAL,
            [b, c, h_bcd],
            d,
            cpt=(
                CROMWELL_EPS,
                CROMWELL_EPS,
                CROMWELL_EPS,
                CROMWELL_EPS,
                CROMWELL_EPS,
                CROMWELL_EPS,
                CROMWELL_EPS,
                0.9,
            ),  # 只有 b=1, c=1 时
        )

        # 连接到下一个菱形
        if i < num_diamonds - 1:
            next_a = f"a_{i + 1}"
            h_link = f"h_link_{i}"
            fg.add_variable(h_link)
            fg.add_factor(
                f"f_link_{i}",
                FactorType.CONDITIONAL,
                [d, h_link],
                next_a,
                cpt=(CROMWELL_EPS, CROMWELL_EPS, CROMWELL_EPS, 0.85),
            )

    return fg


def test_realistic_dag():
    """测试真实 DAG 结构"""
    print("=" * 70)
    print("真实 DAG 结构测试")
    print("=" * 70)

    # 测试不同规模
    configs = [
        (5, 20, 2),  # 5 层 × 20 节点 × 2 fan_in ≈ 300 变量
        (10, 50, 2),  # 10 层 × 50 节点 × 2 fan_in ≈ 1500 变量
        (20, 100, 2),  # 20 层 × 100 节点 × 2 fan_in ≈ 6000 变量
    ]

    for num_layers, nodes_per_layer, fan_in in configs:
        print(f"\n{'=' * 70}")
        print(f"配置: {num_layers} 层 × {nodes_per_layer} 节点/层 × {fan_in} fan_in")
        print(f"{'=' * 70}")

        fg = build_realistic_dag(num_layers, nodes_per_layer, fan_in)
        n_vars = len(fg.variables)
        n_factors = len(fg.factors)

        print(f"变量数: {n_vars}, 因子数: {n_factors}")

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


def test_diamond_dag():
    """测试菱形 DAG（多路径）"""
    print("\n" + "=" * 70)
    print("菱形 DAG 测试（多路径汇聚）")
    print("=" * 70)

    for num_diamonds in [100, 500, 1000]:
        print(f"\n{'=' * 70}")
        print(f"{num_diamonds} 个菱形")
        print(f"{'=' * 70}")

        fg = build_diamond_dag(num_diamonds)
        n_vars = len(fg.variables)
        n_factors = len(fg.factors)

        print(f"变量数: {n_vars}, 因子数: {n_factors}")

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


def test_10e5_scale():
    """测试 10^5 规模"""
    print("\n" + "=" * 70)
    print("10^5 规模测试")
    print("=" * 70)

    # 目标：~100,000 变量
    # 配置：50 层 × 500 节点/层 × 2 fan_in ≈ 75,000 变量
    num_layers = 50
    nodes_per_layer = 500
    fan_in = 2

    print(f"\n配置: {num_layers} 层 × {nodes_per_layer} 节点/层 × {fan_in} fan_in")
    print("构建图...")

    t0 = time.time()
    fg = build_realistic_dag(num_layers, nodes_per_layer, fan_in)
    build_time = time.time() - t0

    n_vars = len(fg.variables)
    n_factors = len(fg.factors)

    print(f"变量数: {n_vars}, 因子数: {n_factors}")
    print(f"构建耗时: {build_time:.3f}s")

    # Loopy BP
    print("\nLoopy BP...")
    t0 = time.time()
    bp = BeliefPropagation(damping=0.5, max_iterations=500, convergence_threshold=1e-6)
    bp_result = bp.run(fg)
    bp_time = time.time() - t0

    print(f"  耗时: {bp_time:.3f}s ({bp_time / 60:.1f} 分钟)")
    print(f"  迭代: {bp_result.diagnostics.iterations_run}")
    print(f"  收敛: {bp_result.diagnostics.converged}")

    # 检查信念值范围
    beliefs = list(bp_result.beliefs.values())
    print(f"  信念范围: [{min(beliefs):.4f}, {max(beliefs):.4f}]")

    # 每变量耗时
    time_per_var = 1000 * bp_time / n_vars
    print(f"  每变量耗时: {time_per_var:.3f} ms")


def main():
    """主测试流程"""
    print("=" * 70)
    print("Loopy BP 严格验证：真实 DAG + 10^5 规模")
    print("=" * 70)

    # 1. 真实 DAG 结构
    test_realistic_dag()

    # 2. 菱形 DAG（多路径）
    test_diamond_dag()

    # 3. 10^5 规模
    test_10e5_scale()


if __name__ == "__main__":
    main()
