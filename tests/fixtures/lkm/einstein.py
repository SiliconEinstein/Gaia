"""Einstein Gravity — complete LKM fixture.

Source: tests/fixtures/gaia_language_packages/einstein_gravity_v4/

General relativity: equivalence principle → light bending → field equations →
1919 eclipse observations confirm GR over Newtonian prediction.
"""

from gaia.lkm.models import Step

from tests.fixtures.lkm._helpers import operator, strategy, var

PACKAGE_ID = "einstein_gravity"
VERSION = "4.0.0"

_P = PACKAGE_ID


def _qid(label: str) -> str:
    return f"reg:{_P}::{label}"


# ══════════════════════════════════════════════════════════════════════
#  CLAIMS
# ══════════════════════════════════════════════════════════════════════

eotvos_experiment = var(
    "prior_knowledge.eotvos_experiment",
    "Eötvös 1889年扭摆实验以10^(-9)精度验证：物体的惯性质量与引力质量在实验可区分范围内相等。",
    _P,
)

maxwell_electromagnetism = var(
    "prior_knowledge.maxwell_electromagnetism",
    "麦克斯韦电磁理论：光是电磁波，在真空中以恒定速度c传播，与光源运动状态无关。",
    _P,
)

soldner_deflection = var(
    "prior_knowledge.soldner_deflection",
    "Soldner 1801年基于牛顿力学将光视为质点（微粒说），计算得光线掠过太阳表面时偏折约0.87角秒。",
    _P,
)

equivalence_principle = var(
    "equivalence_principle.equivalence_principle",
    "爱因斯坦等价原理：在足够小的时空区域内，均匀引力场的效应与匀加速参考系的效应不可区分。",
    _P,
)

light_bends_in_gravity = var(
    "equivalence_principle.light_bends_in_gravity",
    "光线在引力场中会发生弯曲。",
    _P,
)

einstein_field_equations = var(
    "general_relativity.einstein_field_equations",
    "爱因斯坦场方程：引力不是超距力，而是质能分布导致的时空弯曲。G_μν + Λg_μν = (8πG/c⁴)T_μν",
    _P,
)

gr_light_deflection = var(
    "general_relativity.gr_light_deflection",
    "广义相对论预测：光线掠过太阳表面时偏折1.75角秒。",
    _P,
)

mercury_perihelion = var(
    "general_relativity.mercury_perihelion",
    "天文观测显示水星近日点每世纪有约43角秒的异常进动，"
    "牛顿引力理论在扣除其他行星摄动后无法解释这一剩余量。",
    _P,
)

gr_mercury_precession = var(
    "general_relativity.gr_mercury_precession",
    "广义相对论精确解释了水星近日点每世纪43角秒的异常进动，无需引入任何新参数。",
    _P,
)

eddington_sobral = var(
    "observation.eddington_sobral",
    "1919年5月29日日全食期间，巴西Sobral观测站测得恒星光线经过太阳附近时偏折：1.98±0.16角秒。",
    _P,
)

eddington_principe = var(
    "observation.eddington_principe",
    "同一次日全食期间，西非Príncipe岛观测站测得恒星光线偏折：1.61±0.30角秒。",
    _P,
)

eddington_confirms_gr = var(
    "observation.eddington_confirms_gr",
    "1919年日食观测数据支持广义相对论的1.75角秒光线偏折预测，排除牛顿微粒说的0.87角秒预测。",
    _P,
)

gr_dual_confirmation = var(
    "observation.gr_dual_confirmation",
    "光线偏折与水星进动是广义相对论的两个独立预测，分别被不同类型的观测所证实。",
    _P,
)

# ══════════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════════

elevator_env = var(
    "equivalence_principle.elevator_env",
    "密闭电梯思想实验：电梯中的观察者无法看到外界，"
    "需要判断自己是静止在引力场中还是在无引力空间中匀加速上升。",
    _P,
    type_="setting",
)

# ══════════════════════════════════════════════════════════════════════
#  QUESTIONS
# ══════════════════════════════════════════════════════════════════════

gravitational_waves_question = var(
    "follow_up.gravitational_waves_question",
    "广义相对论预测时空曲率的扰动以引力波形式传播。"
    "能否直接探测到引力波，为时空弯曲提供独立于光线偏折的验证？",
    _P,
    type_="question",
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Strategies
# ══════════════════════════════════════════════════════════════════════

f_equivalence_principle = strategy(
    "equivalence_principle",
    premises=[_qid("prior_knowledge.eotvos_experiment")],
    conclusion=_qid("equivalence_principle.equivalence_principle"),
    background=[_qid("equivalence_principle.elevator_env")],
    package=_P,
    steps=[Step(reasoning="惯性质量=引力质量 → 引力场与加速不可区分。")],
)

f_light_bends = strategy(
    "light_bends",
    premises=[
        _qid("equivalence_principle.equivalence_principle"),
        _qid("prior_knowledge.maxwell_electromagnetism"),
    ],
    conclusion=_qid("equivalence_principle.light_bends_in_gravity"),
    package=_P,
    steps=[Step(reasoning="加速电梯中光线弯曲 + 等价原理 → 引力场中光线也弯曲。")],
)

f_gr_deflection = strategy(
    "gr_deflection",
    premises=[
        _qid("equivalence_principle.light_bends_in_gravity"),
        _qid("general_relativity.einstein_field_equations"),
    ],
    conclusion=_qid("general_relativity.gr_light_deflection"),
    package=_P,
    steps=[Step(reasoning="场方程精确计算得偏折角为1.75角秒，是牛顿值的两倍。")],
)

f_gr_mercury = strategy(
    "gr_mercury",
    premises=[
        _qid("general_relativity.einstein_field_equations"),
        _qid("general_relativity.mercury_perihelion"),
    ],
    conclusion=_qid("general_relativity.gr_mercury_precession"),
    package=_P,
    steps=[Step(reasoning="场方程对水星轨道的精确解给出43角秒/世纪的进动。")],
)

f_eddington_confirms = strategy(
    "eddington_confirms",
    premises=[
        _qid("observation.eddington_sobral"),
        _qid("observation.eddington_principe"),
        _qid("general_relativity.gr_light_deflection"),
    ],
    conclusion=_qid("observation.eddington_confirms_gr"),
    package=_P,
    steps=[Step(reasoning="两个独立观测站的结果都更接近GR的1.75角秒而非牛顿的0.87角秒。")],
)

f_dual_confirmation = strategy(
    "dual_confirmation",
    premises=[
        _qid("observation.eddington_confirms_gr"),
        _qid("general_relativity.gr_mercury_precession"),
    ],
    conclusion=_qid("observation.gr_dual_confirmation"),
    package=_P,
    steps=[Step(reasoning="光偏折（天文）和水星进动（轨道力学）独立验证同一理论。")],
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Operators
# ══════════════════════════════════════════════════════════════════════

f_deflection_contradiction = operator(
    "deflection_contradiction",
    variables=[
        _qid("general_relativity.gr_light_deflection"),
        _qid("prior_knowledge.soldner_deflection"),
    ],
    conclusion=_qid("prior_knowledge.soldner_deflection"),
    package=_P,
    subtype="contradiction",
)

# ══════════════════════════════════════════════════════════════════════
#  EXPORTS
# ══════════════════════════════════════════════════════════════════════

LOCAL_VARIABLES = [
    # claims
    eotvos_experiment,
    maxwell_electromagnetism,
    soldner_deflection,
    equivalence_principle,
    light_bends_in_gravity,
    einstein_field_equations,
    gr_light_deflection,
    mercury_perihelion,
    gr_mercury_precession,
    eddington_sobral,
    eddington_principe,
    eddington_confirms_gr,
    gr_dual_confirmation,
    # settings
    elevator_env,
    # questions
    gravitational_waves_question,
]

LOCAL_FACTORS = [
    f_equivalence_principle,
    f_light_bends,
    f_gr_deflection,
    f_gr_mercury,
    f_eddington_confirms,
    f_dual_confirmation,
    f_deflection_contradiction,
]
