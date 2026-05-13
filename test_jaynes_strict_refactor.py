"""增量验证测试：每一步重构后都用 jaynes_ref 验证。

测试策略：
1. 从最简单的图开始（单个 claim）
2. 逐步增加复杂度（operator, strategy）
3. 每次修改后立即运行测试
"""

import sys
sys.path.insert(0, '/root/v0.5/Gaia')

from gaia.ir.graphs import LocalCanonicalGraph
from gaia.ir.knowledge import Knowledge, KnowledgeType
from gaia.ir.operator import Operator, OperatorType
from gaia.bp.lowering import lower_local_graph
from jaynes_ref.adapter import from_local_graph
from jaynes_ref.exact import infer as exact_inference
from gaia.bp.exact import exact_inference as bp_exact_inference
import math


def test_single_claim_no_prior():
    """测试 1：单个 claim，无 prior（Class V，MaxEnt）"""
    print("\n=== Test 1: Single claim, no prior (Class V) ===")

    graph = LocalCanonicalGraph(
        knowledges=[Knowledge(id="A", type=KnowledgeType.CLAIM, label="A")],
        operators=[],
        strategies=[],
        namespace="test",
        package_name="test",
    )

    # jaynes_ref
    info = from_local_graph(graph)
    result_jaynes = exact_inference(info)

    # gaia.bp
    fg = lower_local_graph(graph)
    beliefs_bp, log_Z_bp = bp_exact_inference(fg)

    print(f"jaynes_ref: P(A=1) = {result_jaynes.beliefs['A']:.6f}, log_Z = {result_jaynes.log_Z:.6f}")
    print(f"gaia.bp:    P(A=1) = {beliefs_bp['A']:.6f}, log_Z = {log_Z_bp:.6f}")

    assert math.isclose(result_jaynes.beliefs['A'], beliefs_bp['A'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.log_Z, log_Z_bp, abs_tol=1e-6)
    print("✓ PASS")


def test_single_claim_with_prior():
    """测试 2：单个 claim，有 prior（Class IV）"""
    print("\n=== Test 2: Single claim with prior (Class IV) ===")

    graph = LocalCanonicalGraph(
        knowledges=[Knowledge(id="A", type=KnowledgeType.CLAIM, label="A")],
        operators=[],
        strategies=[],
        namespace="test",
        package_name="test",
    )

    node_priors = {"A": 0.7}

    # jaynes_ref
    info = from_local_graph(graph, node_priors=node_priors)
    result_jaynes = exact_inference(info)

    # gaia.bp
    fg = lower_local_graph(graph, node_priors=node_priors)
    beliefs_bp, log_Z_bp = bp_exact_inference(fg)

    print(f"jaynes_ref: P(A=1) = {result_jaynes.beliefs['A']:.6f}, log_Z = {result_jaynes.log_Z:.6f}")
    print(f"gaia.bp:    P(A=1) = {beliefs_bp['A']:.6f}, log_Z = {log_Z_bp:.6f}")

    assert math.isclose(result_jaynes.beliefs['A'], beliefs_bp['A'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.log_Z, log_Z_bp, abs_tol=1e-6)
    print("✓ PASS")


def test_single_claim_hard_evidence():
    """测试 3：单个 claim，hard evidence（Class I）"""
    print("\n=== Test 3: Single claim with hard evidence (Class I) ===")

    graph = LocalCanonicalGraph(
        knowledges=[Knowledge(id="A", type=KnowledgeType.CLAIM, label="A")],
        operators=[],
        strategies=[],
        namespace="test",
        package_name="test",
    )

    node_priors = {"A": 1.0}  # 边界值 → Class I

    # jaynes_ref
    info = from_local_graph(graph, node_priors=node_priors)
    result_jaynes = exact_inference(info)

    # gaia.bp
    fg = lower_local_graph(graph, node_priors=node_priors)
    beliefs_bp, log_Z_bp = bp_exact_inference(fg)

    print(f"jaynes_ref: P(A=1) = {result_jaynes.beliefs['A']:.6f}, log_Z = {result_jaynes.log_Z:.6f}")
    print(f"gaia.bp:    P(A=1) = {beliefs_bp['A']:.6f}, log_Z = {log_Z_bp:.6f}")

    assert math.isclose(result_jaynes.beliefs['A'], beliefs_bp['A'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.log_Z, log_Z_bp, abs_tol=1e-6)
    print("✓ PASS")


def test_implication_assertional():
    """测试 4：Assertional operator (IMPLICATION)"""
    print("\n=== Test 4: Assertional operator (IMPLICATION) ===")

    graph = LocalCanonicalGraph(
        knowledges=[
            Knowledge(id="A", type=KnowledgeType.CLAIM, label="A"),
            Knowledge(id="B", type=KnowledgeType.CLAIM, label="B"),
        ],
        operators=[
            Operator(
                operator_id="op1",
                operator=OperatorType.IMPLICATION,
                variables=["A"],
                conclusion="B",
            )
        ],
        strategies=[],
        namespace="test",
        package_name="test",
    )

    node_priors = {"A": 0.6}

    # jaynes_ref
    info = from_local_graph(graph, node_priors=node_priors)
    result_jaynes = exact_inference(info)

    # gaia.bp
    fg = lower_local_graph(graph, node_priors=node_priors)
    result_bp = bp_exact_inference(fg)

    print(f"jaynes_ref: P(A=1) = {result_jaynes.beliefs['A']:.6f}, P(B=1) = {result_jaynes.beliefs['B']:.6f}")
    print(f"gaia.bp:    P(A=1) = {beliefs_bp['A']:.6f}, P(B=1) = {beliefs_bp['B']:.6f}")
    print(f"jaynes_ref: log_Z = {result_jaynes.log_Z:.6f}")
    print(f"gaia.bp:    log_Z = {log_Z_bp:.6f}")

    assert math.isclose(result_jaynes.beliefs['A'], beliefs_bp['A'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.beliefs['B'], beliefs_bp['B'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.log_Z, log_Z_bp, abs_tol=1e-6)
    print("✓ PASS")


def test_conjunction_compositional():
    """测试 5：Compositional operator (CONJUNCTION)"""
    print("\n=== Test 5: Compositional operator (CONJUNCTION) ===")

    graph = LocalCanonicalGraph(
        knowledges=[
            Knowledge(id="A", type=KnowledgeType.CLAIM, label="A"),
            Knowledge(id="B", type=KnowledgeType.CLAIM, label="B"),
            Knowledge(id="C", type=KnowledgeType.CLAIM, label="C"),
        ],
        operators=[
            Operator(
                operator_id="op1",
                operator=OperatorType.CONJUNCTION,
                variables=["A", "B"],
                conclusion="C",
            )
        ],
        strategies=[],
        namespace="test",
        package_name="test",
    )

    node_priors = {"A": 0.6, "B": 0.7}

    # jaynes_ref
    info = from_local_graph(graph, node_priors=node_priors)
    result_jaynes = exact_inference(info)

    # gaia.bp
    fg = lower_local_graph(graph, node_priors=node_priors)
    result_bp = bp_exact_inference(fg)

    print(f"jaynes_ref: P(A=1) = {result_jaynes.beliefs['A']:.6f}, P(B=1) = {result_jaynes.beliefs['B']:.6f}, P(C=1) = {result_jaynes.beliefs['C']:.6f}")
    print(f"gaia.bp:    P(A=1) = {beliefs_bp['A']:.6f}, P(B=1) = {beliefs_bp['B']:.6f}, P(C=1) = {beliefs_bp['C']:.6f}")
    print(f"jaynes_ref: log_Z = {result_jaynes.log_Z:.6f}")
    print(f"gaia.bp:    log_Z = {log_Z_bp:.6f}")

    assert math.isclose(result_jaynes.beliefs['A'], beliefs_bp['A'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.beliefs['B'], beliefs_bp['B'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.beliefs['C'], beliefs_bp['C'], abs_tol=1e-6)
    assert math.isclose(result_jaynes.log_Z, log_Z_bp, abs_tol=1e-6)
    print("✓ PASS")


if __name__ == "__main__":
    print("=" * 60)
    print("Jaynes-Strict BP Refactor: Incremental Validation")
    print("=" * 60)

    try:
        test_single_claim_no_prior()
        test_single_claim_with_prior()
        test_single_claim_hard_evidence()
        test_implication_assertional()
        test_conjunction_compositional()

        print("\n" + "=" * 60)
        print("All tests passed! ✓")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
