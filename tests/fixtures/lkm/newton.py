"""Newton Principia — complete LKM fixture.

Source: tests/fixtures/gaia_language_packages/newton_principia_v4/

Derivation chain: Kepler's law + Newton's laws → inverse square → universal gravitation
→ mass equivalence → freefall acceleration independent of mass.

Cross-package dependency: galileo_falling_bodies::vacuum_prediction
"""

from gaia.lkm.models import Step

from tests.fixtures.lkm._helpers import strategy, var

PACKAGE_ID = "newton_principia"
VERSION = "4.0.0"

_P = PACKAGE_ID


def _qid(label: str) -> str:
    return f"reg:{_P}::{label}"


# ══════════════════════════════════════════════════════════════════════
#  CLAIMS
# ══════════════════════════════════════════════════════════════════════

second_law = var(
    "laws.second_law",
    "牛顿第二定律：物体所受合外力等于其惯性质量与加速度的乘积。F = m_i·a",
    _P,
)

third_law = var(
    "laws.third_law",
    "牛顿第三定律：两个物体之间的作用力与反作用力大小相等、方向相反。F_AB = -F_BA",
    _P,
)

kepler_third_law = var(
    "observations.kepler_third_law",
    "开普勒第三定律（1619，基于第谷·布拉赫的行星观测数据）："
    "行星绕太阳运行的轨道周期T的平方与轨道半径r的立方成正比。T² = kr³",
    _P,
)

pendulum_experiment = var(
    "observations.pendulum_experiment",
    "牛顿用等长摆锤悬挂金、银、铅、玻璃、沙、盐、木、水、小麦等不同材料，"
    "测得所有材料的摆动周期在10^(-3)精度内完全一致。",
    _P,
)

inverse_square_force = var(
    "derivation.inverse_square_force",
    "对于绕中心天体做圆周运动的物体，所受引力与到天体中心距离r的平方成反比。F ∝ 1/r²",
    _P,
)

law_of_gravity = var(
    "derivation.law_of_gravity",
    "万有引力定律：质量为M和m_g的两个物体之间的引力与两者质量之积成正比，"
    "与距离的平方成反比。F = GMm_g/r²",
    _P,
)

mass_equivalence = var(
    "derivation.mass_equivalence",
    "物体的惯性质量m_i（决定对力的加速响应）与引力质量m_g（决定所受引力大小）相等。m_i = m_g",
    _P,
)

freefall_acceleration = var(
    "derivation.freefall_acceleration_equals_g",
    "在地球表面附近，任何物体的自由落体加速度都等于g≈9.8m/s²，与物体质量无关。",
    _P,
)

apollo15_feather_drop = var(
    "derivation.apollo15_feather_drop",
    "1971年Apollo 15任务中，宇航员David Scott在月球表面（真空环境）"
    "同时释放一把锤子（1.32kg）和一根羽毛（0.03g），质量比约44000:1，两者同时落地。",
    _P,
)

apollo15_confirms = var(
    "derivation.apollo15_confirms_equal_fall",
    "在月球真空条件下，质量相差约四万倍的物体仍然同时落地，直接验证自由落体加速度与质量无关。",
    _P,
)

galileo_newton_convergence = var(
    "derivation.galileo_newton_convergence",
    "牛顿从力学定律出发的数学推导，与伽利略从思想实验出发的逻辑论证，"
    "独立得出同一结论：自由落体加速度与物体质量无关。",
    _P,
)

apollo_galileo_convergence = var(
    "derivation.apollo_galileo_convergence",
    "伽利略1638年的思想实验预测与Apollo 15 1971年的月面实验结果一致："
    "在真空中一切物体以相同速率下落。",
    _P,
)

# ══════════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════════

near_earth_surface = var(
    "observations.near_earth_surface",
    "在地球表面附近，物体到地心的距离r近似等于地球半径R，"
    "因此引力加速度可视为常数：g = GM/R² ≈ 9.8 m/s²",
    _P,
    type_="setting",
)

# ══════════════════════════════════════════════════════════════════════
#  QUESTIONS
# ══════════════════════════════════════════════════════════════════════

main_question = var(
    "motivation.main_question",
    "能否从力学基本定律与天文观测出发，推导出自由落体加速度与物体质量无关？",
    _P,
    type_="question",
)

follow_up_question = var(
    "follow_up.follow_up_question",
    "上述推导依赖m_i = m_g这一经验事实。惯性质量与引力质量的精确相等是否有更深层的理论解释？",
    _P,
    type_="question",
)

# ══════════════════════════════════════════════════════════════════════
#  CROSS-PACKAGE REFERENCE
#  Newton references Galileo's vacuum_prediction with IDENTICAL content
# ══════════════════════════════════════════════════════════════════════

# This has the SAME content as galileo.vacuum_prediction
# → content_hash will match → dedup in integrate
vacuum_prediction = var(
    "ext.vacuum_prediction",
    "在真空中，不同重量的物体应以相同速率下落。",
    _P,
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Strategies
# ══════════════════════════════════════════════════════════════════════

f_inverse_square = strategy(
    "inverse_square",
    premises=[_qid("observations.kepler_third_law"), _qid("laws.second_law")],
    conclusion=_qid("derivation.inverse_square_force"),
    package=_P,
    steps=[Step(reasoning="圆周运动 + F=ma + T²∝r³ → F ∝ 1/r²")],
)

f_law_of_gravity = strategy(
    "law_of_gravity",
    premises=[_qid("derivation.inverse_square_force"), _qid("laws.third_law")],
    conclusion=_qid("derivation.law_of_gravity"),
    package=_P,
    steps=[Step(reasoning="反比力 + 第三定律对称性 → F = GMm/r²")],
)

f_mass_equivalence = strategy(
    "mass_equivalence",
    premises=[
        _qid("observations.pendulum_experiment"),
        _qid("laws.second_law"),
        _qid("derivation.law_of_gravity"),
    ],
    conclusion=_qid("derivation.mass_equivalence"),
    package=_P,
    steps=[Step(reasoning="摆动周期一致 → 加速度一致 → m_i = m_g")],
)

f_freefall = strategy(
    "freefall",
    premises=[
        _qid("laws.second_law"),
        _qid("derivation.law_of_gravity"),
        _qid("derivation.mass_equivalence"),
    ],
    conclusion=_qid("derivation.freefall_acceleration_equals_g"),
    background=[_qid("observations.near_earth_surface")],
    package=_P,
    steps=[Step(reasoning="F=m_i·a, F=GMm_g/R², m_i=m_g → a=GM/R²=g，与m无关。")],
)

f_apollo15_confirms = strategy(
    "apollo15_confirms",
    premises=[_qid("derivation.apollo15_feather_drop")],
    conclusion=_qid("derivation.apollo15_confirms_equal_fall"),
    package=_P,
    steps=[Step(reasoning="月球真空中锤子和羽毛同时落地 → 直接验证。")],
)

# Cross-package reasoning: convergence with galileo
f_galileo_newton_convergence = strategy(
    "galileo_newton_convergence",
    premises=[
        _qid("derivation.freefall_acceleration_equals_g"),
        _qid("ext.vacuum_prediction"),  # dedup'd with galileo's
    ],
    conclusion=_qid("derivation.galileo_newton_convergence"),
    package=_P,
    steps=[Step(reasoning="牛顿数学推导 + 伽利略思想实验 → 独立路径同一结论。")],
)

f_apollo_galileo_convergence = strategy(
    "apollo_galileo_convergence",
    premises=[
        _qid("derivation.apollo15_confirms_equal_fall"),
        _qid("ext.vacuum_prediction"),  # dedup'd with galileo's
    ],
    conclusion=_qid("derivation.apollo_galileo_convergence"),
    package=_P,
    steps=[Step(reasoning="1638年预测 + 1971年月面实验 = 333年后验证。")],
)

# ══════════════════════════════════════════════════════════════════════
#  EXPORTS
# ══════════════════════════════════════════════════════════════════════

LOCAL_VARIABLES = [
    # claims
    second_law,
    third_law,
    kepler_third_law,
    pendulum_experiment,
    inverse_square_force,
    law_of_gravity,
    mass_equivalence,
    freefall_acceleration,
    apollo15_feather_drop,
    apollo15_confirms,
    galileo_newton_convergence,
    apollo_galileo_convergence,
    # cross-package ref (same content as galileo's vacuum_prediction)
    vacuum_prediction,
    # settings
    near_earth_surface,
    # questions
    main_question,
    follow_up_question,
]

LOCAL_FACTORS = [
    f_inverse_square,
    f_law_of_gravity,
    f_mass_equivalence,
    f_freefall,
    f_apollo15_confirms,
    f_galileo_newton_convergence,
    f_apollo_galileo_convergence,
]
