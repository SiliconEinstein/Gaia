from libs.lang.plausible_core import (
    AbductionMode,
    Claim,
    Close,
    ContradictionMode,
    Hole,
    KernelError,
    Observation,
    Proof,
    Program,
    Relation,
    SynthesisMode,
    Use,
    Have,
    check_program,
    build_review_packet,
    render_review_packet_markdown,
)


def test_abduction_packet_contains_process_fields():
    program = Program(
        declarations=[
            Observation(
                name="medium_effect",
                text="In denser media, the speed gap between heavier and lighter bodies grows.",
            ),
            Claim(
                name="weight_causes_speed_gap",
                text="Weight itself causes the observed speed gap.",
            ),
            Claim(
                name="air_drag_explains_gap",
                text="Air drag is a better explanation for the observed speed gap.",
                proof=Proof(
                    steps=[
                        Use("medium_effect"),
                        Close(
                            AbductionMode(
                                observations=("medium_effect",),
                                alternatives=("weight_causes_speed_gap",),
                                warrant=(
                                    "If drag causes the gap, denser media should amplify the difference."
                                ),
                                comparison=(
                                    "The weight-only story does not explain why the gap changes with the medium."
                                ),
                            )
                        ),
                    ]
                ),
            ),
        ]
    )

    checked = check_program(program)
    packet = build_review_packet(checked, "air_drag_explains_gap")

    assert packet.target.name == "air_drag_explains_gap"
    assert packet.structural_status == "closed"
    assert packet.final_step.strategy == "abduction"
    assert packet.final_step.warrant == (
        "If drag causes the gap, denser media should amplify the difference."
    )
    assert packet.final_step.comparison == (
        "The weight-only story does not explain why the gap changes with the medium."
    )
    assert packet.direct_premises[0].name == "medium_effect"
    assert packet.final_step.alternatives == ["weight_causes_speed_gap"]
    assert any("alternative" in question.lower() for question in packet.review_questions)


def test_have_can_feed_a_later_synthesis_step():
    program = Program(
        declarations=[
            Observation(
                name="medium_effect",
                text="In denser media, the speed gap between heavier and lighter bodies grows.",
            ),
            Claim(
                name="tied_ball_contradiction",
                text="The tied-ball thought experiment undermines the heavier-falls-faster law.",
            ),
            Claim(
                name="weight_causes_speed_gap",
                text="Weight itself causes the observed speed gap.",
            ),
            Claim(
                name="vacuum_prediction",
                text="In vacuum, bodies of different weights should fall at the same rate.",
                proof=Proof(
                    steps=[
                        Use("tied_ball_contradiction"),
                        Have(
                            name="drag_is_confound",
                            statement="Air drag is the confound in ordinary observations.",
                            proof=Proof(
                                steps=[
                                    Use("medium_effect"),
                                    Close(
                                        AbductionMode(
                                            observations=("medium_effect",),
                                            alternatives=("weight_causes_speed_gap",),
                                            warrant=(
                                                "If drag is the confound, denser media should amplify the gap."
                                            ),
                                            comparison=(
                                                "A weight-only explanation does not predict medium sensitivity."
                                            ),
                                        )
                                    ),
                                ]
                            ),
                        ),
                        Close(
                            SynthesisMode(
                                supports=("tied_ball_contradiction", "drag_is_confound"),
                                convergence=(
                                    "The thought experiment removes the old law, and the medium effect explains the leftover gap."
                                ),
                            )
                        ),
                    ]
                ),
            ),
        ]
    )

    checked = check_program(program)
    packet = build_review_packet(checked, "vacuum_prediction")

    assert packet.structural_status == "closed"
    assert packet.final_step.strategy == "synthesis"
    assert packet.final_step.supports == ["tied_ball_contradiction", "drag_is_confound"]
    assert len(packet.derived_facts) == 1
    derived = packet.derived_facts[0]
    assert derived.name == "drag_is_confound"
    assert derived.final_step is not None
    assert derived.final_step.strategy == "abduction"
    assert "independent" in " ".join(packet.review_questions).lower()


def test_relation_goal_can_close_by_contradiction():
    program = Program(
        declarations=[
            Claim(
                name="slower_than_h",
                text="The tied pair is slower than H.",
            ),
            Claim(
                name="faster_than_h",
                text="The tied pair is faster than H.",
            ),
            Relation(
                name="tied_ball_contradiction",
                relation_kind="contradiction",
                text="The two tied-ball conclusions cannot both hold.",
                proof=Proof(
                    steps=[
                        Use("slower_than_h"),
                        Use("faster_than_h"),
                        Close(ContradictionMode(between=("slower_than_h", "faster_than_h"))),
                    ]
                ),
            ),
        ]
    )

    checked = check_program(program)
    packet = build_review_packet(checked, "tied_ball_contradiction")

    assert packet.final_step is not None
    assert packet.final_step.strategy == "contradiction"
    assert packet.final_step.between == ["slower_than_h", "faster_than_h"]


def test_unknown_reference_is_rejected():
    program = Program(
        declarations=[
            Claim(
                name="broken_claim",
                text="Broken.",
                proof=Proof(steps=[Use("missing_fact"), Hole("unfinished")]),
            )
        ]
    )

    try:
        check_program(program)
    except KernelError as exc:
        assert "missing_fact" in str(exc)
    else:
        raise AssertionError("expected KernelError")


def test_self_support_is_rejected():
    program = Program(
        declarations=[
            Observation(name="medium_effect", text="Observed medium effect."),
            Claim(
                name="air_drag_explains_gap",
                text="Air drag explains the gap.",
                proof=Proof(
                    steps=[
                        Use("medium_effect"),
                        Use("air_drag_explains_gap"),
                        Close(
                            SynthesisMode(
                                supports=("medium_effect", "air_drag_explains_gap"),
                                convergence="Bad circular closure.",
                            )
                        ),
                    ]
                ),
            ),
        ]
    )

    try:
        check_program(program)
    except KernelError as exc:
        assert "self-support" in str(exc)
    else:
        raise AssertionError("expected KernelError")


def test_hole_marks_packet_incomplete():
    program = Program(
        declarations=[
            Observation(name="medium_effect", text="Observed medium effect."),
            Claim(
                name="unfinished_claim",
                text="An unfinished claim.",
                proof=Proof(steps=[Use("medium_effect"), Hole("missing close step")]),
            ),
        ]
    )

    checked = check_program(program)
    packet = build_review_packet(checked, "unfinished_claim")
    markdown = render_review_packet_markdown(packet)

    assert packet.structural_status == "has_holes"
    assert packet.final_step is None
    assert packet.holes == ["missing close step"]
    assert "missing close step" in markdown
