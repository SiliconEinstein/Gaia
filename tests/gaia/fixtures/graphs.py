"""Graph fixtures — real scientific examples as LocalCanonicalGraph instances.

Each builder returns ``(LocalCanonicalGraph, LocalParameterization)`` so that
per-node priors and per-factor conditional probabilities travel together with
the graph they describe.  ``make_minimal_claim_pair`` is the only exception:
it returns just a ``LocalCanonicalGraph`` (use ``make_default_local_params``
for uniform parameterisation).
"""

from gaia.core.local_params import LocalParameterization
from gaia.libs.models import (
    FactorCategory,
    FactorNode,
    FactorStage,
    KnowledgeNode,
    KnowledgeType,
    LocalCanonicalGraph,
    ReasoningType,
    SourceRef,
)

# ---------------------------------------------------------------------------
# Shared content constants (for cross-package matching)
# ---------------------------------------------------------------------------

VACUUM_PREDICTION_CONTENT = "In vacuum, all objects fall at the same rate regardless of mass"
INVERSE_SQUARE_CONTENT = "Gravitational force follows an inverse-square law: F = GMm/r\u00b2"


def _src(package: str, version: str = "1.0") -> list[SourceRef]:
    return [SourceRef(package=package, version=version)]


def _factor_src(package: str, version: str = "1.0") -> SourceRef:
    return SourceRef(package=package, version=version)


def _make_params(
    graph: LocalCanonicalGraph,
    node_priors: dict[str, float],
    factor_params: dict[str, float],
) -> LocalParameterization:
    return LocalParameterization(
        graph_hash=graph.graph_hash,
        node_priors=node_priors,
        factor_parameters=factor_params,
    )


# ---------------------------------------------------------------------------
# Galileo's falling bodies — 10 nodes, 7 factors
# ---------------------------------------------------------------------------


def make_galileo_falling_bodies() -> tuple[LocalCanonicalGraph, LocalParameterization]:
    """Galileo's refutation of Aristotle's falling bodies doctrine.

    10 knowledge nodes (1 setting + 9 claims), 7 factors including a
    contradiction between the two deductions from Aristotle's law.
    """
    pkg = "galileo_falling_bodies"

    aristotle_doctrine = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Aristotle's doctrine: heavier objects fall faster in proportion"
            " to their weight (v \u221d W)"
        ),
        source_refs=_src(pkg),
    )
    empirical_observation = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Everyday observation confirms: stones fall faster than leaves,"
            " cannonballs faster than feathers"
        ),
        source_refs=_src(pkg),
    )
    aristotle_law = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Aristotle's law of falling bodies: the speed of fall v is"
            " directly proportional to weight W (v = kW)"
        ),
        source_refs=_src(pkg),
    )
    tied_balls_setup = KnowledgeNode(
        type=KnowledgeType.SETTING,
        content=(
            "Galileo's thought experiment: tie a heavy cannonball to a light"
            " musket ball and drop them together"
        ),
        source_refs=_src(pkg),
    )
    deduction_slower = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "By Aristotle's law, the light ball drags the heavy ball, so the"
            " composite falls slower than the heavy ball alone"
        ),
        source_refs=_src(pkg),
    )
    deduction_faster = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "By Aristotle's law, the composite weighs more, so it falls"
            " faster than the heavy ball alone"
        ),
        source_refs=_src(pkg),
    )
    medium_density_obs = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Speed difference between heavy and light objects decreases"
            " systematically in less dense media"
        ),
        source_refs=_src(pkg),
    )
    air_resistance_hyp = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "The observed speed differences are caused by medium resistance,"
            " not intrinsic weight-speed relationship"
        ),
        source_refs=_src(pkg),
    )
    aristotle_refuted = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Aristotle's law is self-contradictory: the same system cannot"
            " fall both faster and slower"
        ),
        source_refs=_src(pkg),
    )
    vacuum_prediction = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=VACUUM_PREDICTION_CONTENT,
        source_refs=_src(pkg),
    )

    nodes = [
        aristotle_doctrine,
        empirical_observation,
        aristotle_law,
        tied_balls_setup,
        deduction_slower,
        deduction_faster,
        medium_density_obs,
        air_resistance_hyp,
        aristotle_refuted,
        vacuum_prediction,
    ]

    src = _factor_src(pkg)

    # Factor 1: aristotle_doctrine + empirical_observation -> aristotle_law (INDUCTION)
    f_induction = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.INDUCTION,
        premises=[aristotle_doctrine.id, empirical_observation.id],
        conclusion=aristotle_law.id,
        source_ref=src,
    )
    # Factor 2: aristotle_law + [tied_balls_setup] -> deduction_slower (ENTAILMENT)
    f_slower = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[aristotle_law.id, tied_balls_setup.id],
        conclusion=deduction_slower.id,
        source_ref=src,
    )
    # Factor 3: aristotle_law + [tied_balls_setup] -> deduction_faster (ENTAILMENT)
    f_faster = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[aristotle_law.id, tied_balls_setup.id],
        conclusion=deduction_faster.id,
        source_ref=src,
    )
    # Factor 4: deduction_slower -|- deduction_faster (CONTRADICT)
    f_contradict = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.CONTRADICT,
        premises=[deduction_slower.id, deduction_faster.id],
        conclusion=None,
        source_ref=src,
    )
    # Factor 5: deduction_slower + deduction_faster -> aristotle_refuted (ENTAILMENT)
    f_refuted = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[deduction_slower.id, deduction_faster.id],
        conclusion=aristotle_refuted.id,
        source_ref=src,
    )
    # Factor 6: medium_density_obs -> air_resistance_hyp (INDUCTION)
    f_air = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.INDUCTION,
        premises=[medium_density_obs.id],
        conclusion=air_resistance_hyp.id,
        source_ref=src,
    )
    # Factor 7: aristotle_refuted + air_resistance_hyp -> vacuum_prediction (ENTAILMENT)
    f_vacuum = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[aristotle_refuted.id, air_resistance_hyp.id],
        conclusion=vacuum_prediction.id,
        source_ref=src,
    )

    factors = [f_induction, f_slower, f_faster, f_contradict, f_refuted, f_air, f_vacuum]

    graph = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)

    node_priors = {
        aristotle_doctrine.id: 0.7,
        empirical_observation.id: 0.9,
        aristotle_law.id: 0.7,
        # tied_balls_setup is SETTING — no prior
        deduction_slower.id: 0.9,
        deduction_faster.id: 0.9,
        medium_density_obs.id: 0.9,
        air_resistance_hyp.id: 0.8,
        aristotle_refuted.id: 0.9,
        vacuum_prediction.id: 0.85,
    }
    factor_params = {
        f_induction.factor_id: 0.7,
        f_slower.factor_id: 1.0,
        f_faster.factor_id: 1.0,
        f_contradict.factor_id: 1.0,
        f_refuted.factor_id: 1.0,
        f_air.factor_id: 0.8,
        f_vacuum.factor_id: 0.85,
    }

    params = _make_params(graph, node_priors, factor_params)
    return graph, params


# ---------------------------------------------------------------------------
# Newton's universal gravitation — 6 nodes, 3 factors
# ---------------------------------------------------------------------------


def make_newton_gravity() -> tuple[LocalCanonicalGraph, LocalParameterization]:
    """Newton's derivation of universal gravitation.

    5 knowledge nodes (all claims), 3 factors.  ``mass_cancellation`` is
    Newton's independent derivation of the same physical truth as Galileo's
    ``vacuum_prediction`` — semantically equivalent but worded differently.
    Since it's a *conclusion* (of F=ma + F=mg entailment), cross-package
    canonicalization should produce an ``equivalent_candidate`` binding
    rather than a direct ``match_existing``.
    """
    pkg = "newton_principia"

    newton_second_law = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Newton's second law: F = ma",
        source_refs=_src(pkg),
    )
    gravitational_force = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Near Earth's surface, gravitational force on mass m is"
            " F = mg where g \u2248 9.8 m/s\u00b2"
        ),
        source_refs=_src(pkg),
    )
    # Semantically equivalent to Galileo's vacuum_prediction but independently
    # derived — Newton's version expressed as a Newtonian derivation result.
    mass_cancellation = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=("All objects fall at the same rate in vacuum, independent of their mass"),
        source_refs=_src(pkg),
    )
    kepler_third_law = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Kepler's third law: T\u00b2 \u221d a\u00b3 for planetary orbits",
        source_refs=_src(pkg),
    )
    inverse_square_law = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=INVERSE_SQUARE_CONTENT,
        source_refs=_src(pkg),
    )

    nodes = [
        newton_second_law,
        gravitational_force,
        mass_cancellation,
        kepler_third_law,
        inverse_square_law,
    ]

    src = _factor_src(pkg)

    # Factor 1: newton_second_law + gravitational_force -> mass_cancellation (ENTAILMENT)
    f_cancel = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[newton_second_law.id, gravitational_force.id],
        conclusion=mass_cancellation.id,
        source_ref=src,
    )
    # Factor 2: kepler_third_law -> inverse_square_law (ENTAILMENT)
    f_kepler = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[kepler_third_law.id],
        conclusion=inverse_square_law.id,
        source_ref=src,
    )
    # Factor 3: inverse_square_law -> mass_cancellation (ENTAILMENT)
    f_isq = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[inverse_square_law.id],
        conclusion=mass_cancellation.id,
        source_ref=src,
    )

    factors = [f_cancel, f_kepler, f_isq]

    graph = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)

    node_priors = {
        newton_second_law.id: 0.95,
        gravitational_force.id: 0.95,
        mass_cancellation.id: 0.95,
        kepler_third_law.id: 0.9,
        inverse_square_law.id: 0.9,
    }
    factor_params = {
        f_cancel.factor_id: 0.95,
        f_kepler.factor_id: 0.9,
        f_isq.factor_id: 0.9,
    }

    params = _make_params(graph, node_priors, factor_params)
    return graph, params


# ---------------------------------------------------------------------------
# Einstein's equivalence principle — 7 nodes, 5 factors
# ---------------------------------------------------------------------------


def make_einstein_equivalence() -> tuple[LocalCanonicalGraph, LocalParameterization]:
    """Einstein's equivalence principle and GR light-bending prediction.

    7 knowledge nodes (all claims), 5 factors including a contradiction
    between GR and Newtonian light-deflection predictions.
    ``newton_gravity`` uses the exact same content string as Newton's
    ``inverse_square_law`` for cross-package matching.
    """
    pkg = "einstein_gravity"

    newton_gravity = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=INVERSE_SQUARE_CONTENT,
        source_refs=_src(pkg),
    )
    eotvos_experiment = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "E\u00f6tv\u00f6s experiment confirms: inertial mass equals gravitational"
            " mass to precision 10\u207b\u2078"
        ),
        source_refs=_src(pkg),
    )
    elevator_experiment = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "An observer in a closed elevator cannot distinguish gravity from uniform acceleration"
        ),
        source_refs=_src(pkg),
    )
    equivalence_principle = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "The equivalence principle: gravitational and inertial effects"
            " are locally indistinguishable"
        ),
        source_refs=_src(pkg),
    )
    gr_light_bending = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=("General relativity predicts light deflection of 1.75 arcseconds near the Sun"),
        source_refs=_src(pkg),
    )
    newtonian_prediction = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Newtonian corpuscular theory predicts light deflection of"
            " 0.87 arcseconds (Soldner 1801)"
        ),
        source_refs=_src(pkg),
    )
    eddington_observation = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "1919 solar eclipse observation confirms light deflection of"
            " approximately 1.75 arcseconds"
        ),
        source_refs=_src(pkg),
    )

    nodes = [
        newton_gravity,
        eotvos_experiment,
        elevator_experiment,
        equivalence_principle,
        gr_light_bending,
        newtonian_prediction,
        eddington_observation,
    ]

    src = _factor_src(pkg)

    # Factor 1: eotvos + elevator -> equivalence_principle (ABDUCTION)
    f_abduction = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ABDUCTION,
        premises=[eotvos_experiment.id, elevator_experiment.id],
        conclusion=equivalence_principle.id,
        weak_points=["Only valid locally; breaks down for tidal forces over extended regions"],
        source_ref=src,
    )
    # Factor 2: equivalence_principle -> gr_light_bending (ENTAILMENT)
    f_gr = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[equivalence_principle.id],
        conclusion=gr_light_bending.id,
        source_ref=src,
    )
    # Factor 3: newton_gravity -> newtonian_prediction (ENTAILMENT)
    f_newton = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.ENTAILMENT,
        premises=[newton_gravity.id],
        conclusion=newtonian_prediction.id,
        source_ref=src,
    )
    # Factor 4: gr_light_bending -|- newtonian_prediction (CONTRADICT)
    f_contradict = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.CONTRADICT,
        premises=[gr_light_bending.id, newtonian_prediction.id],
        conclusion=None,
        source_ref=src,
    )
    # Factor 5: eddington_observation -> gr_light_bending (INDUCTION)
    f_eddington = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.PERMANENT,
        reasoning_type=ReasoningType.INDUCTION,
        premises=[eddington_observation.id],
        conclusion=gr_light_bending.id,
        source_ref=src,
    )

    factors = [f_abduction, f_gr, f_newton, f_contradict, f_eddington]

    graph = LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)

    node_priors = {
        newton_gravity.id: 0.95,
        eotvos_experiment.id: 0.95,
        elevator_experiment.id: 0.9,
        equivalence_principle.id: 0.85,
        gr_light_bending.id: 0.8,
        newtonian_prediction.id: 0.7,
        eddington_observation.id: 0.9,
    }
    factor_params = {
        f_abduction.factor_id: 0.85,
        f_gr.factor_id: 0.8,
        f_newton.factor_id: 0.7,
        f_contradict.factor_id: 1.0,
        f_eddington.factor_id: 0.9,
    }

    params = _make_params(graph, node_priors, factor_params)
    return graph, params


# ---------------------------------------------------------------------------
# Minimal claim pair (unchanged — returns just a graph)
# ---------------------------------------------------------------------------


def make_minimal_claim_pair() -> LocalCanonicalGraph:
    """Simplest graph: one premise -> one conclusion via a single factor."""
    premise = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Premise claim for minimal test",
        source_refs=[SourceRef(package="minimal_test", version="1.0")],
    )
    conclusion = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Conclusion claim for minimal test",
        source_refs=[SourceRef(package="minimal_test", version="1.0")],
    )

    factor = FactorNode(
        scope="local",
        category=FactorCategory.INFER,
        stage=FactorStage.INITIAL,
        premises=[premise.id],
        conclusion=conclusion.id,
        source_ref=SourceRef(package="minimal_test", version="1.0"),
    )

    return LocalCanonicalGraph(
        knowledge_nodes=[premise, conclusion],
        factor_nodes=[factor],
    )
