"""Galileo coarse graph: exact enumeration vs BP.

Enumerate all 2^10 = 1024 states, compute exact marginals,
and compare with BP results.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
from itertools import product as cartesian_product

from libs.inference.factor_graph import FactorGraph
from libs.inference.bp import BeliefPropagation

# ============================================================
# Variable IDs (same as galileo_bp_demo.py coarse graph)
# ============================================================
A = 1
V = 2
O_DAILY = 10
O_MEDIA = 11
O_AIR = 12
T1 = 20
T2 = 21
A_VAC = 22
S_VAC = 41
E_EXP = 83

ALL_VARS = [A, V, O_DAILY, O_MEDIA, O_AIR, T1, T2, A_VAC, S_VAC, E_EXP]
NAMES = {
    A: "A(重者更快)",
    V: "V(真空等速)",
    O_DAILY: "O_daily",
    O_MEDIA: "O_media",
    O_AIR: "O_air",
    T1: "T₁(拖拽)",
    T2: "T₂(总重)",
    A_VAC: "A_vac",
    S_VAC: "S_vac",
    E_EXP: "E_θᵢ",
}

# ============================================================
# Priors
# ============================================================
priors = {
    A: 0.5,
    V: 0.5,
    O_DAILY: 0.95,
    O_MEDIA: 0.95,
    O_AIR: 0.95,
    T1: 0.5,
    T2: 0.5,
    A_VAC: 0.5,
    S_VAC: 0.95,
    E_EXP: 0.95,
}

# Cromwell clamp
EPS = 1e-3
for k in priors:
    priors[k] = max(EPS, min(1 - EPS, priors[k]))

# ============================================================
# Factors (same as coarse graph)
# ============================================================
factors = [
    # (premises, conclusions, p, edge_type)
    ([O_DAILY], [A], 0.7, "deduction"),  # W1
    ([A], [T1], 0.99, "deduction"),  # f1: A->T1
    ([A], [T2], 0.99, "deduction"),  # f2: A->T2
    ([T1, T2], [], 0.95, "relation_contradiction"),  # T1 ⊗ T2
    ([A, S_VAC], [A_VAC], 0.99, "deduction"),  # f3: A+S_vac->A_vac
    ([A_VAC, V], [], 0.95, "relation_contradiction"),  # A_vac ⊗ V
    ([O_MEDIA, O_AIR], [V], 0.7, "deduction"),  # W2
    ([E_EXP], [V], 0.75, "deduction"),  # W3
]

# Cromwell clamp factor probs
for i, (prem, conc, p, etype) in enumerate(factors):
    factors[i] = (prem, conc, max(EPS, min(1 - EPS, p)), etype)


def evaluate_potential(premises, conclusions, assignment, prob, edge_type):
    """Same logic as bp.py _evaluate_potential."""
    if edge_type == "relation_contradiction":
        all_true = all(assignment[p] == 1 for p in premises)
        return (1.0 - prob) if all_true else 1.0

    if edge_type == "relation_equivalence":
        a_val = assignment[premises[0]]
        b_val = assignment[premises[1]]
        return prob if a_val == b_val else (1.0 - prob)

    all_premises_true = all(assignment[p] == 1 for p in premises)
    if not all_premises_true:
        return 1.0

    pot = 1.0
    for h in conclusions:
        h_val = assignment[h]
        pot *= prob if h_val == 1 else (1.0 - prob)
    return pot


# ============================================================
# Exact enumeration: 2^10 = 1024 states
# ============================================================
n = len(ALL_VARS)
print(f"Enumerating all 2^{n} = {2**n} states...")

# For each state, compute unnormalized probability
unnorm = np.zeros(2**n)

for state_idx, vals in enumerate(cartesian_product([0, 1], repeat=n)):
    assignment = {var: val for var, val in zip(ALL_VARS, vals)}

    # Prior contribution
    p_state = 1.0
    for var in ALL_VARS:
        pi = priors[var]
        p_state *= pi if assignment[var] == 1 else (1 - pi)

    # Factor contribution
    for premises, conclusions, prob, edge_type in factors:
        p_state *= evaluate_potential(premises, conclusions, assignment, prob, edge_type)

    unnorm[state_idx] = p_state

# Normalize
Z = unnorm.sum()
prob_dist = unnorm / Z

# Compute exact marginals
exact_beliefs = {}
for vi, var in enumerate(ALL_VARS):
    # Sum over all states where var=1
    marginal = 0.0
    for state_idx, vals in enumerate(cartesian_product([0, 1], repeat=n)):
        if list(vals)[vi] == 1:
            marginal += prob_dist[state_idx]
    exact_beliefs[var] = marginal

# ============================================================
# BP computation (same graph)
# ============================================================
fg = FactorGraph()
for var in ALL_VARS:
    fg.add_variable(var, priors[var])

for fid, (premises, conclusions, prob, edge_type) in enumerate(factors):
    fg.add_factor(fid, premises, conclusions, prob, edge_type)

bp = BeliefPropagation(damping=0.5, max_iterations=200, convergence_threshold=1e-8)
bp_beliefs, diag = bp.run_with_diagnostics(fg)

print("diag", diag)

# ============================================================
# Compare
# ============================================================
print()
print("=" * 75)
print(f"{'Variable':<20} {'Exact':>10} {'BP':>10} {'Diff':>10} {'Match?':>8}")
print("=" * 75)

all_match = True
for var in ALL_VARS:
    exact = exact_beliefs[var]
    bp_val = bp_beliefs[var]
    diff = abs(exact - bp_val)
    match = diff < 0.01
    if not match:
        all_match = False
    print(
        f"{NAMES[var]:<20} {exact:>10.6f} {bp_val:>10.6f} {diff:>10.6f} {'✓' if match else '✗':>8}"
    )

print("=" * 75)
print(f"BP converged: {diag.converged} | Iterations: {diag.iterations_run}")
print(f"Z (partition function): {Z:.6e}")
print()

if all_match:
    print("✓ All beliefs match within 0.01 tolerance!")
else:
    print("✗ Some beliefs differ — expected for loopy BP on graphs with cycles.")
    print("  (BP is exact on trees, approximate on graphs with loops)")
