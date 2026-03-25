"""Graph fixtures — real scientific examples as LocalCanonicalGraph instances."""

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


def _src(package: str, version: str = "1.0") -> list[SourceRef]:
    return [SourceRef(package=package, version=version)]


def _factor_src(package: str, version: str = "1.0") -> SourceRef:
    return SourceRef(package=package, version=version)


# ---------------------------------------------------------------------------
# Galileo's falling bodies
# ---------------------------------------------------------------------------


def make_galileo_falling_bodies() -> LocalCanonicalGraph:
    """Galileo's refutation of Aristotle's falling bodies doctrine."""
    pkg = "galileo_falling_bodies"

    aristotle_doctrine = KnowledgeNode(
        type=KnowledgeType.SETTING,
        content="Aristotle's doctrine: heavier objects fall faster than lighter ones",
        source_refs=_src(pkg),
    )
    tied_balls_setup = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Consider a heavy ball tied to a light ball and dropped together",
        source_refs=_src(pkg),
    )
    composite_slower = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "The light ball drags down the heavy ball, so the composite falls"
            " slower than the heavy ball alone"
        ),
        source_refs=_src(pkg),
    )
    composite_faster = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "The composite is heavier than either ball, so it falls faster"
            " than the heavy ball alone"
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
        tied_balls_setup,
        composite_slower,
        composite_faster,
        vacuum_prediction,
    ]

    src = _factor_src(pkg)

    factors = [
        # aristotle + tied_balls → composite_slower
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=[aristotle_doctrine.id, tied_balls_setup.id],
            conclusion=composite_slower.id,
            source_ref=src,
        ),
        # aristotle + tied_balls → composite_faster
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=[aristotle_doctrine.id, tied_balls_setup.id],
            conclusion=composite_faster.id,
            source_ref=src,
        ),
        # composite_slower ⊥ composite_faster
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.CONTRADICT,
            premises=[composite_slower.id, composite_faster.id],
            conclusion=None,
            source_ref=src,
        ),
        # composite_slower + composite_faster → vacuum_prediction
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=[composite_slower.id, composite_faster.id],
            conclusion=vacuum_prediction.id,
            source_ref=src,
        ),
    ]

    return LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)


# ---------------------------------------------------------------------------
# Newton's universal gravitation
# ---------------------------------------------------------------------------


def make_newton_gravity() -> LocalCanonicalGraph:
    """Newton's derivation of universal gravitation."""
    pkg = "newton_principia"

    kepler_law = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Kepler's third law: T² ∝ a³ for planetary orbits",
        source_refs=_src(pkg),
    )
    galileo_vacuum = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=VACUUM_PREDICTION_CONTENT,
        source_refs=_src(pkg),
    )
    falling_apple = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Objects near Earth's surface accelerate at g ≈ 9.8 m/s²",
        source_refs=_src(pkg),
    )
    inverse_square = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Gravitational force follows an inverse-square law: F = GMm/r²",
        source_refs=_src(pkg),
    )
    mass_equivalence = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Gravitational mass equals inertial mass",
        source_refs=_src(pkg),
    )

    nodes = [kepler_law, galileo_vacuum, falling_apple, inverse_square, mass_equivalence]

    src = _factor_src(pkg)

    factors = [
        # kepler + galileo_vacuum + falling_apple → inverse_square
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.INDUCTION,
            premises=[kepler_law.id, galileo_vacuum.id, falling_apple.id],
            conclusion=inverse_square.id,
            source_ref=src,
        ),
        # inverse_square → mass_equivalence
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=[inverse_square.id],
            conclusion=mass_equivalence.id,
            source_ref=src,
        ),
    ]

    return LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)


# ---------------------------------------------------------------------------
# Einstein's equivalence principle
# ---------------------------------------------------------------------------


def make_einstein_equivalence() -> LocalCanonicalGraph:
    """Einstein's equivalence principle."""
    pkg = "einstein_equivalence"

    newton_gravity = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content="Gravitational force follows an inverse-square law: F = GMm/r²",
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
    light_bending = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Light bends in a gravitational field by 1.75 arcseconds near the Sun (GR prediction)"
        ),
        source_refs=_src(pkg),
    )
    newtonian_prediction = KnowledgeNode(
        type=KnowledgeType.CLAIM,
        content=(
            "Newtonian corpuscular theory predicts light deflection of 0.87 arcseconds near the Sun"
        ),
        source_refs=_src(pkg),
    )

    nodes = [
        newton_gravity,
        elevator_experiment,
        equivalence_principle,
        light_bending,
        newtonian_prediction,
    ]

    src = _factor_src(pkg)

    factors = [
        # newton_gravity + elevator → equivalence_principle (abduction)
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ABDUCTION,
            premises=[newton_gravity.id, elevator_experiment.id],
            conclusion=equivalence_principle.id,
            weak_points=["Only valid locally; breaks for tidal forces"],
            source_ref=src,
        ),
        # equivalence_principle → light_bending
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.ENTAILMENT,
            premises=[equivalence_principle.id],
            conclusion=light_bending.id,
            source_ref=src,
        ),
        # light_bending ⊥ newtonian_prediction
        FactorNode(
            scope="local",
            category=FactorCategory.INFER,
            stage=FactorStage.PERMANENT,
            reasoning_type=ReasoningType.CONTRADICT,
            premises=[light_bending.id, newtonian_prediction.id],
            conclusion=None,
            source_ref=src,
        ),
    ]

    return LocalCanonicalGraph(knowledge_nodes=nodes, factor_nodes=factors)


# ---------------------------------------------------------------------------
# Minimal claim pair
# ---------------------------------------------------------------------------


def make_minimal_claim_pair() -> LocalCanonicalGraph:
    """Simplest graph: one premise → one conclusion via a single factor."""
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
