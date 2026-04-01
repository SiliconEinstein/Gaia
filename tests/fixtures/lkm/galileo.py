"""Galileo Falling Bodies — complete LKM fixture.

Source: tests/fixtures/gaia_language_packages/galileo_falling_bodies_v4/

Galileo's reductio ad absurdum argument against Aristotle's "heavier falls faster":
- Observations → tied balls thought experiment → contradiction → vacuum prediction
"""

from gaia.lkm.models import Step

from tests.fixtures.lkm._helpers import operator, strategy, var

PACKAGE_ID = "galileo_falling_bodies"
VERSION = "4.0.0"

# ── Helper: full QID ──
_P = PACKAGE_ID


def _qid(label: str) -> str:
    return f"reg:{_P}::{label}"


# ══════════════════════════════════════════════════════════════════════
#  CLAIMS
# ══════════════════════════════════════════════════════════════════════

everyday_observation = var(
    "aristotle.everyday_observation",
    "日常生活中，石头比羽毛下落更快、铁球比木球更快，似乎重者总是先着地。",
    _P,
)

heavier_falls_faster = var(
    "aristotle.heavier_falls_faster",
    "物体下落的速度与其重量成正比——重者下落更快。",
    _P,
)

medium_density_observation = var(
    "galileo.medium_density_observation",
    "在水、油、空气等不同介质中比较轻重物体的下落，"
    "会发现介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。",
    _P,
)

inclined_plane_observation = var(
    "galileo.inclined_plane_observation",
    "伽利略的斜面实验把下落过程放慢到可测量尺度后显示："
    "不同重量的小球在相同斜面条件下呈现近似一致的加速趋势，"
    '与"重量越大速度越大"的简单比例律并不相符。',
    _P,
)

composite_is_slower = var(
    "galileo.composite_is_slower",
    '假设"重者下落更快"，将重球（H）与轻球（L）绑成复合体（HL），则HL的下落速度慢于H单独下落。',
    _P,
)

composite_is_faster = var(
    "galileo.composite_is_faster",
    '假设"重者下落更快"，将重球（H）与轻球（L）绑成复合体（HL），则HL的下落速度快于H单独下落。',
    _P,
)

air_resistance_is_confound = var(
    "galileo.air_resistance_is_confound",
    "日常观察到的速度差异更应被解释为介质阻力造成的表象，而不是重量本身决定自由落体速度的证据。",
    _P,
)

vacuum_prediction = var(
    "galileo.vacuum_prediction",
    "在真空中，不同重量的物体应以相同速率下落。",
    _P,
)

# ══════════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════════

thought_experiment_env = var(
    "setting.thought_experiment_env",
    "想象一个重球H和一个轻球L从同一高度落下。"
    '先分别考虑它们各自的"自然下落速度"，'
    "再考虑把二者用细绳绑成复合体HL后一起下落，会得到什么结果。",
    _P,
    type_="setting",
)

vacuum_env = var(
    "setting.vacuum_env",
    "一个理想化的无空气阻力环境，只保留重力作用，不让介质阻力参与落体过程。",
    _P,
    type_="setting",
)

# ══════════════════════════════════════════════════════════════════════
#  QUESTIONS
# ══════════════════════════════════════════════════════════════════════

main_question = var(
    "motivation.main_question",
    "下落的速率是否真正取决于物体的重量？"
    '如果"重者下落更快"只是空气阻力造成的表象，'
    "那么在思想实验、控制条件实验以及真空极限下，应当分别看到怎样的结果？",
    _P,
    type_="question",
)

follow_up_question = var(
    "follow_up.follow_up_question",
    "能否在足够接近真空的条件下直接比较重球与轻球的下落时间？"
    "如果日常差异确实来自空气阻力，"
    "那么真正决定性的实验应当在几乎无介质的环境中完成。",
    _P,
    type_="question",
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Strategies (reasoning with from:)
# ══════════════════════════════════════════════════════════════════════

# aristotle.heavier_falls_faster ← aristotle.everyday_observation
f_heavier_from_observation = strategy(
    "heavier_from_observation",
    premises=[_qid("aristotle.everyday_observation")],
    conclusion=_qid("aristotle.heavier_falls_faster"),
    package=_P,
    steps=[Step(reasoning="日常观察归纳出重者下落更快的经验规律。")],
)

# galileo.composite_is_slower ← aristotle.heavier_falls_faster
#   background: setting.thought_experiment_env
f_composite_slower = strategy(
    "composite_slower",
    premises=[_qid("aristotle.heavier_falls_faster")],
    conclusion=_qid("galileo.composite_is_slower"),
    background=[_qid("setting.thought_experiment_env")],
    package=_P,
    steps=[Step(reasoning="L的拖拽效应使HL比H慢——如果重者确实更快，轻球会拖慢重球。")],
)

# galileo.composite_is_faster ← aristotle.heavier_falls_faster
#   background: setting.thought_experiment_env
f_composite_faster = strategy(
    "composite_faster",
    premises=[_qid("aristotle.heavier_falls_faster")],
    conclusion=_qid("galileo.composite_is_faster"),
    background=[_qid("setting.thought_experiment_env")],
    package=_P,
    steps=[Step(reasoning="HL总质量大于H——如果重者确实更快，复合体应该比H更快。")],
)

# galileo.air_resistance_is_confound ← galileo.medium_density_observation
f_air_resistance = strategy(
    "air_resistance",
    premises=[_qid("galileo.medium_density_observation")],
    conclusion=_qid("galileo.air_resistance_is_confound"),
    package=_P,
    steps=[Step(reasoning="介质越稀薄差异越小，说明差异来自介质阻力而非重量本身。")],
)

# galileo.vacuum_prediction ← tied_balls_contradiction + air_resistance + inclined_plane
#   background: setting.vacuum_env
f_vacuum_prediction = strategy(
    "vacuum_prediction",
    premises=[
        _qid("galileo.air_resistance_is_confound"),
        _qid("galileo.inclined_plane_observation"),
    ],
    conclusion=_qid("galileo.vacuum_prediction"),
    background=[_qid("setting.vacuum_env")],
    package=_P,
    steps=[
        Step(reasoning="绑球矛盾否定了'重者更快'假设；"),
        Step(reasoning="介质阻力解释了日常观察差异；斜面实验进一步支持；"),
        Step(reasoning="因此在真空中一切物体应等速下落。"),
    ],
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Operators (relations)
# ══════════════════════════════════════════════════════════════════════

# contradiction: composite_is_slower ↔ composite_is_faster
# For contradiction operator: variables are the two contradicting nodes,
# conclusion is a helper claim (the contradiction itself resolves to)
# In Gaia IR, contradiction has variables=[A, B] and conclusion=helper
# For simplicity, we use composite_is_slower as conclusion (the one negated)
f_tied_balls_contradiction = operator(
    "tied_balls_contradiction",
    variables=[_qid("galileo.composite_is_slower"), _qid("galileo.composite_is_faster")],
    conclusion=_qid("galileo.composite_is_slower"),
    package=_P,
    subtype="contradiction",
)

# ══════════════════════════════════════════════════════════════════════
#  EXPORTS
# ══════════════════════════════════════════════════════════════════════

LOCAL_VARIABLES = [
    # claims
    everyday_observation,
    heavier_falls_faster,
    medium_density_observation,
    inclined_plane_observation,
    composite_is_slower,
    composite_is_faster,
    air_resistance_is_confound,
    vacuum_prediction,
    # settings
    thought_experiment_env,
    vacuum_env,
    # questions
    main_question,
    follow_up_question,
]

LOCAL_FACTORS = [
    f_heavier_from_observation,
    f_composite_slower,
    f_composite_faster,
    f_air_resistance,
    f_vacuum_prediction,
    f_tied_balls_contradiction,
]
