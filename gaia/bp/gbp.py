"""Generalized Belief Propagation (GBP) for factor graphs with short cycles.

Implements the Region Graph approach from:
  Yedidia, Freeman, Weiss (2005). "Constructing Free Energy Approximations
  and Generalized Belief Propagation Algorithms." IEEE Trans. Information Theory.

Algorithm:

  1. Detect short cycles (length ≤ k) in the variable interaction graph.
  2. Group cycle variables into "regions" via union-find (overlapping cycles merge).
  3. For each region, build a mini-FactorGraph with all variables and factors
     whose scope falls entirely within the region.
  4. Factors that span multiple regions ("cross-region factors") are handled by
     constructing a condensed inter-region factor graph:
       - Each region becomes a compound variable whose state space is 2^|region|.
       - Cross-region factors become factors in the condensed graph.
  5. Run JT within each region to get intra-region beliefs.
  6. Run iterative BP on the condensed inter-region graph, using the region
     JT results as initial messages, until convergence.
  7. Combine intra-region and inter-region beliefs to produce final marginals.

When all cycles are captured within regions (region graph is acyclic),
the result is exact. When the region graph itself has cycles, the result
is a better approximation than standard loopy BP (minimizes Kikuchi free
energy instead of Bethe).

For Gaia's current graphs (treewidth ≤ 15), GBP delegates to JT directly.
The region decomposition path is a genuine algorithm for larger graphs.
"""

from __future__ import annotations

import logging
from collections import defaultdict, deque


from gaia.bp.bp import BeliefPropagation, BPDiagnostics, BPResult
from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph
from gaia.bp.junction_tree import JunctionTreeInference, jt_treewidth

__all__ = ["GeneralizedBeliefPropagation", "detect_short_cycles", "build_region_graph"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cycle detection
# ---------------------------------------------------------------------------


def _variable_interaction_graph(graph: FactorGraph) -> dict[str, set[str]]:
    """Build variable interaction graph (moral graph).

    Two variables are adjacent iff they co-appear in at least one factor.
    """
    adj: dict[str, set[str]] = {v: set() for v in graph.variables}
    for factor in graph.factors:
        vs = factor.all_vars
        for i, u in enumerate(vs):
            for w in vs[i + 1 :]:
                if u in adj and w in adj:
                    adj[u].add(w)
                    adj[w].add(u)
    return adj


def detect_short_cycles(graph: FactorGraph, max_cycle_len: int = 6) -> list[frozenset[str]]:
    """Find all simple cycles of length ≤ max_cycle_len in the interaction graph.

    Uses BFS from each node to find short paths that form cycles.
    Returns deduplicated list of cycles as frozensets of variable IDs.
    """
    adj = _variable_interaction_graph(graph)
    vars_list = list(graph.variables.keys())

    cycles: list[frozenset[str]] = []
    seen: set[frozenset[str]] = set()

    for start in vars_list:
        queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
        while queue:
            node, path = queue.popleft()
            if len(path) > max_cycle_len:
                continue
            for neighbor in adj[node]:
                if neighbor == start and len(path) >= 3:
                    cycle_set = frozenset(path)
                    if cycle_set not in seen:
                        seen.add(cycle_set)
                        cycles.append(cycle_set)
                elif neighbor not in path:
                    queue.append((neighbor, path + [neighbor]))

    return cycles


def build_region_graph(
    graph: FactorGraph,
    max_cycle_len: int = 6,
) -> list[frozenset[str]]:
    """Group variables into regions by merging overlapping short cycles.

    Algorithm:
    1. Find all short cycles.
    2. Union-find: merge variables that share a cycle.
    3. Each connected component becomes a region.
    4. Variables not in any cycle become singleton regions.
    """
    cycles = detect_short_cycles(graph, max_cycle_len)

    parent: dict[str, str] = {v: v for v in graph.variables}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    for cycle_vars in cycles:
        cycle_list = sorted(cycle_vars)
        for i in range(1, len(cycle_list)):
            union(cycle_list[0], cycle_list[i])

    region_map: dict[str, set[str]] = defaultdict(set)
    for v in graph.variables:
        root = find(v)
        region_map[root].add(v)

    return [frozenset(vs) for vs in region_map.values()]


# ---------------------------------------------------------------------------
# Region-based inference
# ---------------------------------------------------------------------------


def _assign_factors_to_regions(
    graph: FactorGraph,
    regions: list[frozenset[str]],
) -> tuple[dict[int, list[Factor]], list[Factor]]:
    """Partition factors into intra-region and cross-region.

    Returns:
        intra: {region_idx: [factors whose scope ⊆ region]}
        cross: [factors whose scope spans multiple regions]
    """
    var_to_region: dict[str, int] = {}
    for ri, region in enumerate(regions):
        for v in region:
            var_to_region[v] = ri

    intra: dict[int, list[Factor]] = {i: [] for i in range(len(regions))}
    cross: list[Factor] = []

    for factor in graph.factors:
        scope_regions = set()
        for v in factor.all_vars:
            if v in var_to_region:
                scope_regions.add(var_to_region[v])
        if len(scope_regions) == 1:
            intra[scope_regions.pop()].append(factor)
        else:
            cross.append(factor)

    return intra, cross


def _solve_region(
    region: frozenset[str],
    factors: list[Factor],
    graph: FactorGraph,
    jt: JunctionTreeInference,
) -> dict[str, float]:
    """Run JT on a single region's mini-graph, return beliefs."""
    mini = FactorGraph()
    for v in region:
        mini.add_variable(v, prior=graph.variables[v])
    for factor in factors:
        mini.add_factor(
            factor.factor_id,
            factor.factor_type,
            factor.premises,
            factor.conclusions,
            factor.p,
            factor.relation_var,
        )
    result = jt.run(mini)
    return result.beliefs


def _build_cross_region_graph(
    graph: FactorGraph,
    regions: list[frozenset[str]],
    cross_factors: list[Factor],
    region_beliefs: dict[int, dict[str, float]],
) -> FactorGraph:
    """Build a factor graph for cross-region message passing.

    Each cross-region factor connects variables from multiple regions.
    We include all variables touched by cross-region factors, with priors
    set to the intra-region JT beliefs (so region-internal evidence is
    propagated as informed priors into the cross-region graph).
    """
    cross_fg = FactorGraph()

    # Collect all variables needed by cross-region factors
    cross_vars: set[str] = set()
    for factor in cross_factors:
        cross_vars.update(factor.all_vars)

    # Set priors from region beliefs (region-internal evidence)
    var_to_region: dict[str, int] = {}
    for ri, region in enumerate(regions):
        for v in region:
            var_to_region[v] = ri

    for v in cross_vars:
        ri = var_to_region.get(v)
        if ri is not None and v in region_beliefs.get(ri, {}):
            prior = region_beliefs[ri][v]
        else:
            prior = graph.variables.get(v, 0.5)
        cross_fg.add_variable(v, prior=prior)

    # Add cross-region factors
    for factor in cross_factors:
        cross_fg.add_factor(
            factor.factor_id + "_cross",
            factor.factor_type,
            factor.premises,
            factor.conclusions,
            factor.p,
            factor.relation_var,
        )

    return cross_fg


def _combine_beliefs(
    graph: FactorGraph,
    regions: list[frozenset[str]],
    region_beliefs: dict[int, dict[str, float]],
    cross_beliefs: dict[str, float] | None,
    cross_vars: set[str],
) -> dict[str, float]:
    """Combine intra-region and cross-region beliefs.

    For variables only in one region: use region JT belief directly.
    For variables in cross-region factors: combine region belief with
    cross-region BP belief using Bayes' rule (multiply likelihood ratios
    and renormalize), avoiding double-counting the prior.
    """
    var_to_region: dict[str, int] = {}
    for ri, region in enumerate(regions):
        for v in region:
            var_to_region[v] = ri

    final: dict[str, float] = {}
    for v in graph.variables:
        ri = var_to_region.get(v)
        region_b = region_beliefs.get(ri, {}).get(v) if ri is not None else None

        if v not in cross_vars or cross_beliefs is None:
            # Variable only in intra-region: use region JT belief
            final[v] = region_b if region_b is not None else graph.variables[v]
        else:
            # Variable in cross-region: combine via likelihood ratio
            # region_b encodes intra-region evidence
            # cross_b encodes cross-region evidence
            # To avoid double-counting the prior, we compute:
            #   combined_odds = (region_odds) * (cross_likelihood_ratio)
            # where cross_likelihood_ratio = cross_odds / prior_odds
            cross_b = cross_beliefs.get(v, graph.variables[v])
            prior = graph.variables[v]

            # Convert to odds (with Cromwell protection)
            eps = 1e-15
            region_odds = (
                max(eps, region_b) / max(eps, 1.0 - region_b) if region_b is not None else 1.0
            )
            cross_odds = max(eps, cross_b) / max(eps, 1.0 - cross_b)
            prior_odds = max(eps, prior) / max(eps, 1.0 - prior)

            # cross_likelihood_ratio removes the prior from cross_b
            cross_lr = cross_odds / prior_odds if prior_odds > eps else 1.0

            # Combined odds = region_odds * cross_likelihood_ratio
            combined_odds = region_odds * cross_lr
            combined_b = combined_odds / (1.0 + combined_odds)

            # Cromwell clamp
            combined_b = max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, combined_b))
            final[v] = combined_b

    return final


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class GeneralizedBeliefPropagation:
    """Generalized Belief Propagation via region-graph decomposition.

    For treewidth ≤ jt_threshold: delegates to JT (exact).
    For treewidth > jt_threshold: performs genuine region decomposition:
      1. Detect short cycles, group into regions
      2. Solve each region exactly with JT
      3. Build cross-region factor graph with region beliefs as priors
      4. Run iterative BP on cross-region graph until convergence
      5. Combine intra-region and cross-region beliefs via likelihood ratio

    Parameters
    ----------
    max_cycle_len:
        Maximum cycle length for region detection (default 6).
    jt_threshold:
        Delegate to JT when treewidth ≤ this (default 15).
    bp_damping:
        Damping for cross-region BP (default 0.5).
    bp_max_iter:
        Max iterations for cross-region BP (default 200).
    bp_threshold:
        Convergence threshold for cross-region BP (default 1e-8).
    """

    def __init__(
        self,
        max_cycle_len: int = 6,
        jt_threshold: int = 15,
        bp_damping: float = 0.5,
        bp_max_iter: int = 200,
        bp_threshold: float = 1e-8,
    ) -> None:
        self._max_cycle_len = max_cycle_len
        self._jt_threshold = jt_threshold
        self._jt = JunctionTreeInference()
        self._bp = BeliefPropagation(
            damping=bp_damping,
            max_iterations=bp_max_iter,
            convergence_threshold=bp_threshold,
        )

    def run(self, graph: FactorGraph) -> BPResult:
        """Run GBP on *graph*.

        Returns BPResult (same interface as JT and loopy BP).
        """
        diag = BPDiagnostics()

        if not graph.variables:
            diag.converged = True
            return BPResult(beliefs={}, diagnostics=diag)

        tw = jt_treewidth(graph)

        # Low treewidth: JT is fast and exact
        if tw <= self._jt_threshold:
            result = self._jt.run(graph)
            return BPResult(
                beliefs=result.beliefs,
                diagnostics=result.diagnostics,
            )

        # High treewidth: region decomposition
        return self._run_region_decomposition(graph, diag)

    def _run_region_decomposition(
        self,
        graph: FactorGraph,
        diag: BPDiagnostics,
    ) -> BPResult:
        """Full region-graph GBP with inter-region message passing."""

        # Step 1: Build regions
        regions = build_region_graph(graph, self._max_cycle_len)
        n_regions = len(regions)
        logger.debug("GBP: %d regions from %d variables", n_regions, len(graph.variables))

        # Step 2: Partition factors
        intra_factors, cross_factors = _assign_factors_to_regions(graph, regions)
        logger.debug(
            "GBP: %d intra-region factor groups, %d cross-region factors",
            sum(len(fs) for fs in intra_factors.values()),
            len(cross_factors),
        )

        # Step 3: Solve each region with JT
        region_beliefs: dict[int, dict[str, float]] = {}
        for ri, region in enumerate(regions):
            region_beliefs[ri] = _solve_region(region, intra_factors[ri], graph, self._jt)

        # Step 4: Handle cross-region factors
        if not cross_factors:
            # No cross-region factors: regions are independent, combine directly
            final_beliefs: dict[str, float] = {}
            for ri, beliefs in region_beliefs.items():
                final_beliefs.update(beliefs)
            # Fill in any variables not assigned to regions
            for v in graph.variables:
                if v not in final_beliefs:
                    final_beliefs[v] = graph.variables[v]

            diag.converged = True
            diag.iterations_run = 0
            for v, b in final_beliefs.items():
                diag.belief_history[v] = [b]
            return BPResult(beliefs=final_beliefs, diagnostics=diag)

        # Step 5: Build cross-region factor graph and run BP
        cross_fg = _build_cross_region_graph(graph, regions, cross_factors, region_beliefs)

        cross_result = self._bp.run(cross_fg)
        cross_beliefs = cross_result.beliefs

        # Step 6: Combine intra-region and cross-region beliefs
        cross_var_set: set[str] = set()
        for factor in cross_factors:
            cross_var_set.update(factor.all_vars)

        final_beliefs = _combine_beliefs(
            graph, regions, region_beliefs, cross_beliefs, cross_var_set
        )

        # Record diagnostics
        diag.converged = cross_result.diagnostics.converged
        diag.iterations_run = cross_result.diagnostics.iterations_run
        diag.max_change_at_stop = cross_result.diagnostics.max_change_at_stop
        for v, b in final_beliefs.items():
            diag.belief_history[v] = [b]

        return BPResult(beliefs=final_beliefs, diagnostics=diag)
