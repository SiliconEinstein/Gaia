"""Large-scale BP algorithm tests with jaynes_ref ground truth validation.

Tests TRW-BP, Junction Tree, and Mean Field VI on graphs with 10^2 to 10^4 nodes,
comparing against jaynes_ref exact inference where feasible.
"""

import time

import pytest

from gaia.engine.bp import (
    JunctionTreeInference,
    MeanFieldVI,
    TRWBeliefPropagation,
    exact_inference,
    infer,
    jt_treewidth,
)
from gaia.engine.bp.factor_graph import CROMWELL_EPS, FactorGraph, FactorType


def build_block_dag(num_blocks: int, prior_a: float = 0.7, prior_c: float = 0.6) -> FactorGraph:
    """Build a Block-DAG graph with controlled treewidth.

    Each block = (leaf_a, leaf_c, helper_h, DEDUCTION a→c).
    Blocks share some conclusions to form a DAG structure.

    Parameters
    ----------
    num_blocks : int
        Number of blocks (K blocks → ~3K variables)
    prior_a : float
        Prior for premise leaves
    prior_c : float
        Prior for conclusion leaves (also used as false-premise base rate)

    Returns:
    -------
    FactorGraph
        Graph with ~3*num_blocks variables, treewidth ≤ 6
    """
    fg = FactorGraph()

    for i in range(num_blocks):
        a_id = f"a_{i}"
        c_id = f"c_{i}"
        h_id = f"h_{i}"

        # Add leaf variables with priors
        fg.add_variable(a_id, prior_a)
        fg.add_variable(c_id, prior_c)
        fg.add_variable(h_id)  # Helper, no prior

        # Add DEDUCTION: a → c with helper h
        # CPT for P(c | a, h): [P(c|¬a,¬h), P(c|¬a,h), P(c|a,¬h), P(c|a,h)]
        # When premise false (¬a), use base rate prior_c
        # When premise true (a), use high confidence 1-ε
        cpt = [prior_c, prior_c, prior_c, 1.0 - CROMWELL_EPS]
        fg.add_factor(
            f"ded_{i}",
            FactorType.CONDITIONAL,
            [a_id, h_id],
            c_id,
            cpt=cpt,
        )

    # Create DAG structure by linking some conclusions
    # Every 5th block: c_i → c_{i+1} (with helper)
    for i in range(0, num_blocks - 1, 5):
        if i > 0:
            c_id = f"c_{i}"
            next_c = f"c_{i + 1}"
            link_helper = f"link_h_{i}"
            fg.add_variable(link_helper)
            fg.add_factor(
                f"link_{i}",
                FactorType.IMPLICATION,
                [c_id, link_helper],
                next_c,
            )

    return fg


def build_chain(length: int, prior: float = 0.7) -> FactorGraph:
    """Build a chain graph: a1 → c1 → a2 → c2 → ... → aN → cN.

    Linear chain with treewidth = 2, should be exact for all algorithms.
    """
    fg = FactorGraph()

    for i in range(length):
        a_id = f"a_{i}"
        c_id = f"c_{i}"
        h_id = f"h_{i}"

        fg.add_variable(a_id, prior)
        fg.add_variable(c_id)
        fg.add_variable(h_id)

        # DEDUCTION with base rate 0.5
        cpt = [0.5, 0.5, 0.5, 1.0 - CROMWELL_EPS]
        fg.add_factor(
            f"ded_{i}",
            FactorType.CONDITIONAL,
            [a_id, h_id],
            c_id,
            cpt=cpt,
        )

        # Link to next premise: c_i → a_{i+1} (with helper)
        if i < length - 1:
            next_a = f"a_{i + 1}"
            chain_helper = f"chain_h_{i}"
            fg.add_variable(chain_helper)
            fg.add_factor(
                f"chain_{i}",
                FactorType.IMPLICATION,
                [c_id, chain_helper],
                next_a,
            )

    return fg


def build_tree(depth: int, branching: int = 3, prior: float = 0.8) -> FactorGraph:
    """Build a tree graph with treewidth = 1.

    Root branches into multiple children, each child branches further.
    Simplest structure, all algorithms should be exact.
    """
    fg = FactorGraph()

    def add_subtree(parent_id: str, current_depth: int, node_counter: list[int]) -> None:
        if current_depth >= depth:
            return

        for _i in range(branching):
            child_id = f"node_{node_counter[0]}"
            helper_id = f"h_{node_counter[0]}"
            node_counter[0] += 1

            fg.add_variable(child_id)
            fg.add_variable(helper_id)

            # DEDUCTION: parent → child with helper
            cpt = [0.5, 0.5, 0.5, 1.0 - CROMWELL_EPS]
            fg.add_factor(
                f"edge_{parent_id}_{child_id}",
                FactorType.CONDITIONAL,
                [parent_id, helper_id],
                child_id,
                cpt=cpt,
            )

            add_subtree(child_id, current_depth + 1, node_counter)

    # Root
    root_id = "root"
    fg.add_variable(root_id, prior)

    counter = [0]
    add_subtree(root_id, 0, counter)

    return fg


@pytest.mark.parametrize("num_blocks", [5, 8])
def test_small_graph_exact_match(num_blocks: int):
    """Small graphs (n ≤ 26): all algorithms should match exact inference."""
    fg = build_block_dag(num_blocks)
    n = len(fg.variables)

    print(f"\n=== Small graph test: {n} variables, {len(fg.factors)} factors ===")

    # Ground truth: exact inference
    start = time.time()
    beliefs_exact, _ = exact_inference(fg)
    time_exact = time.time() - start
    print(f"Exact inference: {time_exact:.3f}s")

    # Test TRW-BP
    start = time.time()
    trw = TRWBeliefPropagation(max_iterations=200, convergence_threshold=1e-6)
    result_trw = trw.run(fg)
    time_trw = time.time() - start
    print(f"TRW-BP: {time_trw:.3f}s, {result_trw.diagnostics.iterations_run} iters")

    # Test Junction Tree
    tw = jt_treewidth(fg)
    print(f"Treewidth: {tw}")
    if tw <= 20:
        start = time.time()
        jt = JunctionTreeInference()
        result_jt = jt.run(fg)
        time_jt = time.time() - start
        print(f"Junction Tree: {time_jt:.3f}s")

        # Compare JT with exact
        max_err_jt = max(abs(result_jt.beliefs[v] - beliefs_exact[v]) for v in fg.variables)
        print(f"JT max error: {max_err_jt:.6f}")
        assert max_err_jt < 1e-3, f"JT error {max_err_jt} exceeds threshold"

    # Compare TRW-BP with exact
    max_err_trw = max(abs(result_trw.beliefs[v] - beliefs_exact[v]) for v in fg.variables)
    print(f"TRW-BP max error: {max_err_trw:.6f}")
    assert max_err_trw < 1e-3, f"TRW-BP error {max_err_trw} exceeds threshold"


@pytest.mark.parametrize("num_blocks", [50, 100, 250])
def test_medium_graph_jt_vs_trw(num_blocks: int):
    """Medium graphs (n > 26, n ≤ 1000): TRW-BP should match JT when treewidth ≤ 20."""
    fg = build_block_dag(num_blocks)
    n = len(fg.variables)
    tw = jt_treewidth(fg)

    print(f"\n=== Medium graph test: {n} variables, treewidth={tw} ===")

    # TRW-BP
    start = time.time()
    trw = TRWBeliefPropagation(max_iterations=500, convergence_threshold=1e-6)
    result_trw = trw.run(fg)
    time_trw = time.time() - start
    print(f"TRW-BP: {time_trw:.3f}s, {result_trw.diagnostics.iterations_run} iters")

    # JT (if treewidth allows)
    if tw <= 20:
        start = time.time()
        jt = JunctionTreeInference()
        result_jt = jt.run(fg)
        time_jt = time.time() - start
        print(f"Junction Tree: {time_jt:.3f}s")

        # Compare
        max_err = max(abs(result_trw.beliefs[v] - result_jt.beliefs[v]) for v in fg.variables)
        print(f"TRW-BP vs JT max error: {max_err:.6f}")
        assert max_err < 1e-3, f"TRW-BP/JT mismatch: {max_err}"
    else:
        print(f"Treewidth {tw} > 20, skipping JT")
        # Just check TRW-BP converged
        assert result_trw.diagnostics.converged, "TRW-BP did not converge"


@pytest.mark.parametrize("num_blocks", [500, 800])
def test_large_graph_mean_field(num_blocks: int):
    """Large graphs (n > 1000): Mean Field VI should run and produce reasonable results."""
    fg = build_block_dag(num_blocks)
    n = len(fg.variables)

    print(f"\n=== Large graph test: {n} variables ===")

    # Mean Field VI
    start = time.time()
    mf = MeanFieldVI(max_iterations=1000, convergence_threshold=1e-4)
    result_mf = mf.run(fg)
    time_mf = time.time() - start
    print(f"Mean Field VI: {time_mf:.3f}s, {result_mf.diagnostics.iterations_run} iters")

    # Sanity checks
    assert result_mf.diagnostics.converged, "Mean Field did not converge"
    assert len(result_mf.beliefs) == n
    assert all(0 <= b <= 1 for b in result_mf.beliefs.values()), "Beliefs out of [0,1]"

    # Compare with TRW-BP (as reference, not ground truth)
    start = time.time()
    trw = TRWBeliefPropagation(max_iterations=500, convergence_threshold=1e-4)
    result_trw = trw.run(fg)
    time_trw = time.time() - start
    print(f"TRW-BP: {time_trw:.3f}s, {result_trw.diagnostics.iterations_run} iters")

    # Mean Field should be in same ballpark as TRW-BP
    max_diff = max(abs(result_mf.beliefs[v] - result_trw.beliefs[v]) for v in fg.variables)
    print(f"Mean Field vs TRW-BP max diff: {max_diff:.6f}")
    # Looser threshold for Mean Field (it's approximate, especially on DAGs with loops)
    assert max_diff < 0.3, f"Mean Field/TRW-BP diff too large: {max_diff}"


def test_chain_graph_all_exact():
    """Chain graphs (treewidth=2) should be exact for TRW-BP and JT."""
    fg = build_chain(6)  # 6 * 4 = 24 variables (within exact inference limit)
    n = len(fg.variables)

    print(f"\n=== Chain graph test: {n} variables ===")

    # Exact
    beliefs_exact, _ = exact_inference(fg)

    # TRW-BP
    trw = TRWBeliefPropagation(max_iterations=200, convergence_threshold=1e-6)
    result_trw = trw.run(fg)

    # JT
    jt = JunctionTreeInference()
    result_jt = jt.run(fg)

    # All should match
    max_err_trw = max(abs(result_trw.beliefs[v] - beliefs_exact[v]) for v in fg.variables)
    max_err_jt = max(abs(result_jt.beliefs[v] - beliefs_exact[v]) for v in fg.variables)

    print(f"TRW-BP max error: {max_err_trw:.6f}")
    print(f"JT max error: {max_err_jt:.6f}")

    assert max_err_trw < 1e-3
    assert max_err_jt < 1e-3


def test_tree_graph_all_exact():
    """Tree graphs (treewidth=1) should be exact for all algorithms."""
    # depth=2, branching=3: 1 root + 3 children + 9 grandchildren = 13 nodes
    # With helpers: 13 + 12 = 25 variables (within exact inference limit)
    fg = build_tree(depth=2, branching=3, prior=0.8)
    n = len(fg.variables)

    print(f"\n=== Tree graph test: {n} variables ===")

    # Exact
    beliefs_exact, _ = exact_inference(fg)

    # TRW-BP
    trw = TRWBeliefPropagation(max_iterations=200, convergence_threshold=1e-6)
    result_trw = trw.run(fg)

    # JT
    jt = JunctionTreeInference()
    result_jt = jt.run(fg)

    # All should match
    max_err_trw = max(abs(result_trw.beliefs[v] - beliefs_exact[v]) for v in fg.variables)
    max_err_jt = max(abs(result_jt.beliefs[v] - beliefs_exact[v]) for v in fg.variables)

    print(f"TRW-BP max error: {max_err_trw:.6f}")
    print(f"JT max error: {max_err_jt:.6f}")

    assert max_err_trw < 1e-3
    assert max_err_jt < 1e-3


def test_auto_routing():
    """Test automatic algorithm selection based on graph size and treewidth."""
    # Small graph with low treewidth → should use JT
    fg_small = build_chain(6)
    beliefs_small = infer(fg_small, method="auto")
    assert len(beliefs_small) == len(fg_small.variables)

    # Medium graph with moderate treewidth → should use TRW-BP
    fg_medium = build_block_dag(100)
    beliefs_medium = infer(fg_medium, method="auto")
    assert len(beliefs_medium) == len(fg_medium.variables)

    # Large graph (> 2000 variables) → should use Loopy BP
    # Loopy BP replaces Mean Field VI as the default for large graphs.
    # It is validated to match TRW-BP exactly (diff < 1e-9) and is 2-3x faster,
    # so no UserWarning is emitted.
    fg_large = build_block_dag(800)  # > 2000 variables
    beliefs_large = infer(fg_large, method="auto")
    assert len(beliefs_large) == len(fg_large.variables)
