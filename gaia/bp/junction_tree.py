"""Junction Tree (Clique Tree) exact inference for factor graphs.

Implements the classic Junction Tree Algorithm (JTA), also called the
"probability propagation in trees of clusters" (PPTC) algorithm.

References:
  - Lauritzen & Spiegelhalter (1988). Local computations with probabilities on
    graphical structures.
  - Huang & Darwiche (1999). A procedure for computing the probability
    distribution of a belief network in polynomial time.
  - Koller & Friedman (2009). Probabilistic Graphical Models, Chapter 10.

Algorithm outline:
  1. Build the moral graph from the factor graph (connect all pairs of
     variables that share a factor, then drop edge directions).
  2. Triangulate the moral graph using min-fill heuristic (add fill edges
     until graph becomes chordal).
  3. Find all maximal cliques of the triangulated graph.
  4. Build a clique tree (Junction Tree) with maximum-spanning-tree on
     clique separators, verifying the running intersection property.
  5. Assign each factor to exactly one clique that contains all its variables.
  6. Initialize each clique's potential as the product of its assigned factors
     evaluated over all 2^|clique| joint assignments, multiplied by priors.
  7. Run two-pass message passing (collect + distribute) on the clique tree.
  8. Marginalize each variable from the calibrated clique that contains it.

The result is exact: for any factor graph representable as a Junction Tree,
the marginal beliefs are identical to brute-force enumeration, but computed
in O(n * 2^w) time where w is the treewidth.

For Gaia's graphs (25 variables, treewidth ≈ 3-4), this is:
  - 2^25 = 33M states (brute force)
  - vs ~25 * 2^4 = 400 operations (Junction Tree)
  - vs ~58 * 25 * 5 = 7250 operations (loopy BP, but inexact on cyclic graphs)

All binary variables (x ∈ {0, 1}). Compatible with FactorGraph from
gaia.bp.factor_graph.
"""

from __future__ import annotations

import logging
from itertools import product as cartesian_product


from gaia.bp.bp import BPDiagnostics, BPResult
from gaia.bp.factor_graph import Factor, FactorGraph
from gaia.bp.potentials import evaluate_potential

__all__ = ["JunctionTreeInference", "jt_treewidth"]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Step 1: Moral graph
# ---------------------------------------------------------------------------


def _build_moral_graph(graph: FactorGraph) -> dict[str, set[str]]:
    """Build the moral graph from the factor graph.

    The moral graph is an undirected graph where:
    - Nodes = all variables in the factor graph
    - Edges = for every factor, connect all pairs of variables it touches
      (premises + conclusions + relation_var)

    This is the standard 'moralization' step that converts the hypergraph
    into a pairwise undirected graph, making it amenable to triangulation.
    """
    adj: dict[str, set[str]] = {v: set() for v in graph.variables}
    for factor in graph.factors:
        vars_in_factor = factor.all_vars
        for i, u in enumerate(vars_in_factor):
            for v in vars_in_factor[i + 1 :]:
                if u in adj and v in adj:
                    adj[u].add(v)
                    adj[v].add(u)
    return adj


# ---------------------------------------------------------------------------
# Step 2: Triangulation (min-fill heuristic)
# ---------------------------------------------------------------------------


def _fill_count(node: str, adj: dict[str, set[str]]) -> int:
    """Count how many fill edges would be added to triangulate by eliminating node.

    When we eliminate a node, we connect all its current neighbors into a clique.
    The number of edges we need to add = |{(u,v) : u,v in N(node), (u,v) not in E}|.
    """
    neighbors = list(adj[node])
    count = 0
    for i, u in enumerate(neighbors):
        for v in neighbors[i + 1 :]:
            if v not in adj[u]:
                count += 1
    return count


def _triangulate_min_fill(
    adj_in: dict[str, set[str]],
) -> tuple[dict[str, set[str]], list[list[str]]]:
    """Triangulate graph using min-fill heuristic, collect elimination cliques.

    Creates a chordal (triangulated) graph by repeatedly:
    1. Choosing the node with the fewest fill edges (ties broken by degree)
    2. Making its neighbors a clique (adding fill edges)
    3. Removing the node from the graph

    Returns:
        adj_tri: triangulated adjacency (original + fill edges)
        elim_cliques: list of [node] + sorted(neighbors) at each elimination step
    """
    # Deep copy the adjacency
    adj = {v: set(ns) for v, ns in adj_in.items()}
    adj_tri = {v: set(ns) for v, ns in adj_in.items()}  # accumulate fill edges here

    remaining = set(adj.keys())
    elim_cliques: list[list[str]] = []

    while remaining:
        # Choose node with min fill count (break ties by min degree)
        best = min(remaining, key=lambda v: (_fill_count(v, adj), len(adj[v])))

        # Record elimination clique: best + its remaining neighbors
        neighbors_remaining = [n for n in adj[best] if n in remaining]
        clique = [best] + sorted(neighbors_remaining)
        elim_cliques.append(clique)

        # Add fill edges (make neighbors a clique in triangulated graph)
        for i, u in enumerate(neighbors_remaining):
            for v in neighbors_remaining[i + 1 :]:
                if v not in adj[u]:
                    adj[u].add(v)
                    adj[v].add(u)
                    adj_tri[u].add(v)
                    adj_tri[v].add(u)

        # Remove best from graph
        for n in adj[best]:
            adj[n].discard(best)
        del adj[best]
        remaining.remove(best)

    return adj_tri, elim_cliques


# ---------------------------------------------------------------------------
# Step 3: Find maximal cliques from elimination cliques
# ---------------------------------------------------------------------------


def _maximal_cliques(elim_cliques: list[list[str]]) -> list[frozenset[str]]:
    """Extract maximal cliques from elimination clique list.

    An elimination clique C_i is maximal if it is not a subset of any
    later elimination clique C_j (j > i). This follows from the property
    that every maximal clique of the triangulated graph appears as some
    elimination clique.
    """
    clique_sets = [frozenset(c) for c in elim_cliques]
    maximal: list[frozenset[str]] = []
    for i, ci in enumerate(clique_sets):
        dominated = False
        for j in range(i + 1, len(clique_sets)):
            if ci <= clique_sets[j]:  # ci is subset of later clique
                dominated = True
                break
        if not dominated:
            maximal.append(ci)
    return maximal


# ---------------------------------------------------------------------------
# Step 4: Build Junction Tree via maximum spanning tree
# ---------------------------------------------------------------------------


def _build_junction_tree(
    cliques: list[frozenset[str]],
) -> list[tuple[int, int, frozenset[str]]]:
    """Build a junction tree by maximum spanning tree on clique separators.

    Each edge between cliques C_i and C_j has weight |C_i ∩ C_j| (separator size).
    We use Kruskal's MST on the complete clique graph, maximizing separator size,
    which guarantees the Running Intersection Property (RIP).

    Returns list of (clique_i_idx, clique_j_idx, separator_variables) for each
    edge in the junction tree.
    """
    n = len(cliques)
    if n == 1:
        return []

    # Build all possible edges with weights
    edges: list[tuple[int, int, int, frozenset[str]]] = []
    for i in range(n):
        for j in range(i + 1, n):
            sep = cliques[i] & cliques[j]
            edges.append((i, j, len(sep), sep))

    # Sort by weight descending (max spanning tree)
    edges.sort(key=lambda e: e[2], reverse=True)

    # Kruskal's algorithm
    parent = list(range(n))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    tree_edges: list[tuple[int, int, frozenset[str]]] = []
    for i, j, w, sep in edges:
        if find(i) != find(j):
            union(i, j)
            tree_edges.append((i, j, sep))
            if len(tree_edges) == n - 1:
                break

    return tree_edges


# ---------------------------------------------------------------------------
# Step 5–6: Assign factors and compute clique potentials
# ---------------------------------------------------------------------------


def _assign_factors_to_cliques(
    cliques: list[frozenset[str]],
    graph: FactorGraph,
) -> dict[int, list[Factor]]:
    """Assign each factor to exactly one clique containing all its variables.

    A factor can be assigned to any clique that is a superset of its variable
    scope. We choose the smallest such clique to keep clique potentials tight.
    """
    assignment: dict[int, list[Factor]] = {i: [] for i in range(len(cliques))}
    for factor in graph.factors:
        scope = frozenset(factor.all_vars)
        # Find smallest clique that contains all factor variables
        best_idx = None
        best_size = float("inf")
        for i, clique in enumerate(cliques):
            if scope <= clique and len(clique) < best_size:
                best_idx = i
                best_size = len(clique)
        if best_idx is None:
            raise RuntimeError(
                f"Factor '{factor.factor_id}' with scope {scope} "
                f"cannot be assigned to any clique. "
                f"The triangulation may be incomplete or a variable is missing."
            )
        assignment[best_idx].append(factor)
    return assignment


def _compute_clique_potential(
    clique: frozenset[str],
    factors: list[Factor],
    priors: dict[str, float],
) -> dict[tuple[int, ...], float]:
    """Compute the initial (unnormalized) potential table for a clique.

    The clique potential is:
        ψ_C(x_C) = ∏_{v ∈ C} prior_factor(v) × ∏_{f assigned to C} ψ_f(x_scope(f))

    The prior factor for variable v is: [1-π_v, π_v] evaluated at x_v.
    This encodes the prior as a unary factor on each variable.

    Since priors are distributed among cliques (each variable appears in exactly
    one clique as "owner"), we track which variables have had their prior applied.
    To avoid double-counting priors, each variable's prior is applied in exactly
    one clique — the one it was first encountered in.

    Returns dict: tuple of {0,1} assignments (in sorted variable order) -> potential.
    """
    var_list = sorted(clique)
    n = len(var_list)
    table: dict[tuple[int, ...], float] = {}

    for vals in cartesian_product((0, 1), repeat=n):
        assignment = {v: vals[i] for i, v in enumerate(var_list)}

        # Prior contributions
        pot = 1.0
        for v in var_list:
            if v in priors:
                pi = priors[v]
                pot *= pi if assignment[v] == 1 else (1.0 - pi)

        # Factor potential contributions
        for factor in factors:
            pot *= evaluate_potential(factor, assignment)

        table[vals] = pot

    return table


# ---------------------------------------------------------------------------
# Step 7: Two-pass message passing on the junction tree
# ---------------------------------------------------------------------------


def _tree_adjacency(
    n_cliques: int,
    tree_edges: list[tuple[int, int, frozenset[str]]],
) -> dict[int, list[tuple[int, frozenset[str]]]]:
    """Build adjacency list for junction tree."""
    adj: dict[int, list[tuple[int, frozenset[str]]]] = {i: [] for i in range(n_cliques)}
    for i, j, sep in tree_edges:
        adj[i].append((j, sep))
        adj[j].append((i, sep))
    return adj


def _marginalize(
    table: dict[tuple[int, ...], float],
    var_list: list[str],
    keep_vars: frozenset[str],
) -> dict[tuple[int, ...], float]:
    """Marginalize a clique potential table down to keep_vars.

    Sums over all variables NOT in keep_vars, returning a table indexed
    by the sorted variables in keep_vars.

    Parameters
    ----------
    table: dict from (vals for var_list) -> potential
    var_list: sorted list of variables corresponding to table keys
    keep_vars: frozenset of variables to keep
    """
    keep_list = sorted(keep_vars)
    keep_indices = [var_list.index(v) for v in keep_list]
    result: dict[tuple[int, ...], float] = {}

    for vals, pot in table.items():
        key = tuple(vals[i] for i in keep_indices)
        result[key] = result.get(key, 0.0) + pot

    return result


def _multiply_tables(
    table_a: dict[tuple[int, ...], float],
    vars_a: list[str],
    table_b: dict[tuple[int, ...], float],
    vars_b: list[str],
) -> tuple[dict[tuple[int, ...], float], list[str]]:
    """Multiply two factor tables, aligning on shared variables.

    Returns (product_table, sorted_union_vars).
    """
    union_vars = sorted(set(vars_a) | set(vars_b))
    a_indices = [union_vars.index(v) for v in vars_a]
    b_indices = [union_vars.index(v) for v in vars_b]

    result: dict[tuple[int, ...], float] = {}
    for vals in cartesian_product((0, 1), repeat=len(union_vars)):
        a_key = tuple(vals[i] for i in a_indices)
        b_key = tuple(vals[i] for i in b_indices)
        pot_a = table_a.get(a_key, 0.0)
        pot_b = table_b.get(b_key, 0.0)
        result[vals] = pot_a * pot_b

    return result, union_vars


def _divide_tables(
    table_a: dict[tuple[int, ...], float],
    vars_a: list[str],
    table_b: dict[tuple[int, ...], float],
    vars_b: list[str],
) -> tuple[dict[tuple[int, ...], float], list[str]]:
    """Divide table_a / table_b (aligned on shared variables).

    Used in Shafer-Shenoy message passing: message(i->j) =
    marginalize(ψ_i) / old_message(j->i).
    Division by zero is set to zero (vacuous message).
    """
    union_vars = sorted(set(vars_a) | set(vars_b))
    a_indices = [union_vars.index(v) for v in vars_a]
    b_indices = [union_vars.index(v) for v in vars_b]

    result: dict[tuple[int, ...], float] = {}
    for vals in cartesian_product((0, 1), repeat=len(union_vars)):
        a_key = tuple(vals[i] for i in a_indices)
        b_key = tuple(vals[i] for i in b_indices)
        pot_a = table_a.get(a_key, 0.0)
        pot_b = table_b.get(b_key, 0.0)
        result[vals] = pot_a / pot_b if pot_b > 1e-300 else 0.0

    return result, union_vars


def _collect_distribute(
    cliques: list[frozenset[str]],
    clique_potentials: list[dict[tuple[int, ...], float]],
    clique_var_lists: list[list[str]],
    tree_adj: dict[int, list[tuple[int, frozenset[str]]]],
    n_cliques: int,
) -> list[dict[tuple[int, ...], float]]:
    """Run collect + distribute (two-pass Shafer-Shenoy) message passing.

    Uses post-order DFS (collect) then pre-order DFS (distribute),
    rooted at clique 0.

    After calibration, each clique's potential is proportional to the joint
    distribution marginalized to that clique's variables.

    Returns list of calibrated clique potential tables (same indexing as input).
    """
    if n_cliques == 1:
        return clique_potentials[:]

    # Build DFS order rooted at 0
    visited = [False] * n_cliques
    post_order: list[int] = []  # collect order
    parent: dict[int, int | None] = {0: None}

    stack = [0]
    while stack:
        node = stack[-1]
        if not visited[node]:
            visited[node] = True
            for child, _ in tree_adj[node]:
                if not visited[child]:
                    parent[child] = node
                    stack.append(child)
        else:
            stack.pop()
            post_order.append(node)

    pre_order = list(reversed(post_order))

    # Messages: msg[(sender, receiver)] = separator-indexed table
    # Initially: uniform over separator
    messages: dict[tuple[int, int], tuple[dict, list[str]]] = {}
    for i, j, sep in [(i, j, sep) for i in range(n_cliques) for j, sep in tree_adj[i]]:
        sep_list = sorted(sep)
        uniform = {vals: 1.0 for vals in cartesian_product((0, 1), repeat=len(sep_list))}
        messages[(i, j)] = (uniform, sep_list)

    # Helper: compute message from clique i to clique j
    def compute_message(sender: int, receiver: int, sep: frozenset[str]) -> tuple[dict, list[str]]:
        # Start with sender's initial potential
        table = dict(clique_potentials[sender])
        var_list = list(clique_var_lists[sender])

        # Multiply in all incoming messages EXCEPT from receiver
        for neighbor, neighbor_sep in tree_adj[sender]:
            if neighbor == receiver:
                continue
            in_msg, in_vars = messages[(neighbor, sender)]
            table, var_list = _multiply_tables(table, var_list, in_msg, in_vars)

        # Marginalize down to separator
        sep_msg = _marginalize(table, var_list, sep)
        return sep_msg, sorted(sep)

    # COLLECT: post-order (leaves to root)
    for node in post_order:
        par = parent.get(node)
        if par is not None:
            # Find separator between node and par
            sep = None
            for neighbor, s in tree_adj[node]:
                if neighbor == par:
                    sep = s
                    break
            msg_table, msg_vars = compute_message(node, par, sep)
            messages[(node, par)] = (msg_table, msg_vars)

    # DISTRIBUTE: pre-order (root to leaves)
    for node in pre_order:
        for child, sep in tree_adj[node]:
            if parent.get(child) == node:
                msg_table, msg_vars = compute_message(node, child, sep)
                messages[(node, child)] = (msg_table, msg_vars)

    # Calibrate: multiply all incoming messages into each clique
    calibrated: list[dict[tuple[int, ...], float]] = []
    for i in range(n_cliques):
        table = dict(clique_potentials[i])
        var_list = list(clique_var_lists[i])
        for neighbor, sep in tree_adj[i]:
            in_msg, in_vars = messages[(neighbor, i)]
            table, var_list = _multiply_tables(table, var_list, in_msg, in_vars)
        # Re-index to sorted clique variable order
        target_vars = clique_var_lists[i]
        reindexed: dict[tuple[int, ...], float] = {}
        for vals, pot in table.items():
            key = tuple(vals[var_list.index(v)] for v in target_vars)
            reindexed[key] = reindexed.get(key, 0.0) + pot
        calibrated.append(reindexed)

    return calibrated


# ---------------------------------------------------------------------------
# Step 8: Marginalize beliefs from calibrated cliques
# ---------------------------------------------------------------------------


def _extract_beliefs(
    cliques: list[frozenset[str]],
    calibrated: list[dict[tuple[int, ...], float]],
    clique_var_lists: list[list[str]],
    all_variables: set[str],
) -> dict[str, float]:
    """Extract single-variable marginals from the calibrated clique potentials.

    For each variable, find any clique containing it, marginalize out all
    other variables, then normalize to get P(v=1).

    Since the junction tree is calibrated, all cliques containing v give
    the same marginal (up to normalization). We use the first clique found.
    """
    # Map each variable to the first clique containing it
    var_to_clique: dict[str, int] = {}
    for v in sorted(all_variables):
        for i, clique in enumerate(cliques):
            if v in clique:
                var_to_clique[v] = i
                break

    beliefs: dict[str, float] = {}
    for v, ci in var_to_clique.items():
        table = calibrated[ci]
        var_list = clique_var_lists[ci]
        v_idx = var_list.index(v)

        # Marginalize: sum over all assignments where v=1
        p_one = sum(pot for vals, pot in table.items() if vals[v_idx] == 1)
        p_zero = sum(pot for vals, pot in table.items() if vals[v_idx] == 0)
        total = p_one + p_zero

        if total < 1e-300:
            beliefs[v] = 0.5  # degenerate: uniform fallback
        else:
            beliefs[v] = float(p_one / total)

    return beliefs


# ---------------------------------------------------------------------------
# Treewidth estimation
# ---------------------------------------------------------------------------


def jt_treewidth(graph: FactorGraph) -> int:
    """Estimate the treewidth of the factor graph via min-fill triangulation.

    Returns the size of the largest maximal clique minus 1.
    """
    if not graph.variables:
        return 0
    moral_adj = _build_moral_graph(graph)
    _, elim_cliques = _triangulate_min_fill(moral_adj)
    max_cliques = _maximal_cliques(elim_cliques)
    return max(len(c) for c in max_cliques) - 1


# ---------------------------------------------------------------------------
# Main class
# ---------------------------------------------------------------------------


class JunctionTreeInference:
    """Exact inference via the Junction Tree Algorithm.

    Converts the FactorGraph to a Junction Tree (chordal graph with clique
    potentials), then runs exact two-pass message passing (Shafer-Shenoy
    collect + distribute). The result is mathematically identical to
    brute-force enumeration but runs in O(n * 2^w) time.

    This fixes loopy BP's double-counting error on graphs with short cycles.
    For Gaia's factor graphs (treewidth ≤ ~15), this is the preferred engine.

    Returns the same BPResult interface as BeliefPropagation for drop-in use.
    """

    def run(self, graph: FactorGraph) -> BPResult:
        """Run exact Junction Tree inference on *graph*.

        Parameters
        ----------
        graph:
            A validated FactorGraph. All variables referenced by factors
            must be registered.

        Returns
        -------
        BPResult
            .beliefs: dict[str, float] — exact marginal P(v=1) per variable.
            .diagnostics: BPDiagnostics recording treewidth and clique count.
        """
        diag = BPDiagnostics()

        if not graph.variables:
            diag.converged = True
            return BPResult(beliefs={}, diagnostics=diag)

        if not graph.factors:
            # No factors: beliefs = priors
            diag.converged = True
            beliefs = dict(graph.variables)
            for vid, p in beliefs.items():
                diag.belief_history[vid] = [p]
            return BPResult(beliefs=beliefs, diagnostics=diag)

        # Step 1: Moral graph
        moral_adj = _build_moral_graph(graph)

        # Step 2: Triangulate
        _, elim_cliques = _triangulate_min_fill(moral_adj)

        # Step 3: Maximal cliques
        cliques = _maximal_cliques(elim_cliques)
        n_cliques = len(cliques)
        clique_var_lists = [sorted(c) for c in cliques]

        treewidth = max(len(c) for c in cliques) - 1
        diag.treewidth = treewidth
        diag.iterations_run = 2  # JT does exactly 2 passes: collect + distribute

        logger.debug(
            "JT: %d variables, %d cliques, treewidth=%d", len(graph.variables), n_cliques, treewidth
        )

        # Step 4: Junction tree edges
        tree_edges = _build_junction_tree(cliques)
        tree_adj = _tree_adjacency(n_cliques, tree_edges)

        # Step 5: Assign factors to cliques
        factor_assignment = _assign_factors_to_cliques(cliques, graph)

        # Step 6: Compute clique potentials
        # Each variable's prior is applied in exactly one clique — the first
        # clique found that contains it. This prevents double-counting priors.
        prior_assigned: set[str] = set()
        clique_potentials: list[dict[tuple[int, ...], float]] = []

        for i, clique in enumerate(cliques):
            var_list = clique_var_lists[i]
            # Determine which priors to apply in this clique
            local_priors: dict[str, float] = {}
            for v in var_list:
                if v not in prior_assigned:
                    local_priors[v] = graph.variables[v]
                    prior_assigned.add(v)

            pot_table = _compute_clique_potential(clique, factor_assignment[i], local_priors)
            clique_potentials.append(pot_table)

        # Step 7: Two-pass message passing
        calibrated = _collect_distribute(
            cliques, clique_potentials, clique_var_lists, tree_adj, n_cliques
        )

        # Step 8: Extract beliefs
        beliefs = _extract_beliefs(
            cliques, calibrated, clique_var_lists, set(graph.variables.keys())
        )

        # NOTE: Do NOT apply Cromwell clamping to the output beliefs.
        # Cromwell's rule applies to author-supplied inputs (priors, p values)
        # to prevent zero probabilities from locking out future evidence.
        # Computed posterior beliefs are allowed to be near 0 or 1 — that is
        # the correct answer when evidence overwhelmingly supports or refutes
        # a proposition.

        # Record beliefs in history (single "iteration" = 0)
        for vid, b in beliefs.items():
            diag.belief_history[vid] = [b]
        diag.converged = True
        diag.max_change_at_stop = 0.0

        return BPResult(beliefs=beliefs, diagnostics=diag)
