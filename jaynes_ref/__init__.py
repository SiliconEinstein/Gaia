"""Jaynes-strict probabilistic inference over propositional logic.

A reference implementation of Jaynes (PTLoS) Layer 0: propositional
variables, five information classes (I-V), deterministic logical
constraints, and exact enumeration-based inference. No belief propagation,
no message passing, no approximation — intended as the golden reference
against which gaia.bp is validated.
"""

from jaynes_ref.ap_distribution import (
    ApDistribution,
    beta_ap,
    credible_interval,
    entropy_ap,
    predictive_probability,
    uniform_ap,
    update_with_bernoulli,
)
from jaynes_ref.constraints import (
    CPT,
    Likelihood,
    LogicalConstraint,
    WeightedFactor,
    complement,
    conjunction,
    contradiction,
    disjunction,
    equivalence,
    implication,
    negation,
    pairwise_weight,
)
from jaynes_ref.decision import (
    DecisionResult,
    asymmetric_loss,
    bayes_action,
    expected_loss,
    quadratic_loss,
    zero_one_loss,
)
from jaynes_ref.information import CROMWELL_EPS, InformationSet
from jaynes_ref.maxent import (
    MaxEntFit,
    MomentConstraint,
    correlation_constraint,
    fit_maxent,
    inject_marginal_priors,
    marginal_constraint,
    marginal_from_fit,
    maxent_from_info,
)
from jaynes_ref.queries import (
    entropy,
    kl_divergence,
    map_assignment,
    marginal,
    marginal_entropy,
    mutual_information,
)

__all__ = [
    "CPT",
    "CROMWELL_EPS",
    "ApDistribution",
    "DecisionResult",
    "InformationSet",
    "Likelihood",
    "LogicalConstraint",
    "MaxEntFit",
    "MomentConstraint",
    "WeightedFactor",
    "asymmetric_loss",
    "bayes_action",
    "beta_ap",
    "complement",
    "conjunction",
    "contradiction",
    "correlation_constraint",
    "credible_interval",
    "disjunction",
    "entropy",
    "entropy_ap",
    "equivalence",
    "expected_loss",
    "fit_maxent",
    "implication",
    "inject_marginal_priors",
    "kl_divergence",
    "map_assignment",
    "marginal",
    "marginal_constraint",
    "marginal_entropy",
    "marginal_from_fit",
    "maxent_from_info",
    "mutual_information",
    "negation",
    "pairwise_weight",
    "predictive_probability",
    "quadratic_loss",
    "uniform_ap",
    "update_with_bernoulli",
    "zero_one_loss",
]
