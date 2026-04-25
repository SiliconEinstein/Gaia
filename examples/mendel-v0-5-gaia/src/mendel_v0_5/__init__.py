"""Mendel-style probability example for Gaia v0.5.

Architecture
------------

Two theories compete for the same single-factor cross:

* ``mendelian_segregation_model`` — discrete particulate inheritance with a
  clean ``P(dominant) = 3/4`` generative model for F2 counts.
* ``blending_inheritance_model`` — continuous averaging of parental traits;
  denies that discrete dominant/recessive classes exist in F2 at all.

These two theories differ in **kind**, and that difference is reflected in
how they engage with the data:

* Mendel participates **probabilistically**: it is a generative model and
  therefore engages with the observed F2 count through a single ``associate``
  that uses the pointwise binomial PMF as its likelihood.
* Blending participates **categorically**: it denies the very framework in
  which one would count dominant vs. recessive individuals, so its conflicts
  with the data are expressed through ``contradict`` edges at the qualitative
  framework level, not through a binomial likelihood it cannot produce.

Every probability in this package is traceable to two well-defined settings:
``MENDELIAN_DOMINANT_PROBABILITY = 3/4`` and a uniform prior ``p ~ U[0, 1]``
as the diffuse alternative (see ``probabilities.py``).

Why an intermediate ``f2_dominant_count_specific`` node exists
--------------------------------------------------------------

Semantically the ``associate`` below should relate ``mendelian_segregation_model``
directly to ``f2_count_observation``. In v0.5 that triggers a framework-level
collision: ``metadata.prior`` on a Claim is asked to encode two genuinely
different quantities at once —

* the **reliability / subjective prior** of the observation (0.95, meaning "I
  trust Mendel's record"), supplied via the ``PRIORS`` dict;
* the **Bayesian marginal** ``P(count) = Σ_H P(count | H) P(H)`` of the count
  event (≈ 0.024 for the 295/395 outcome under the {Mendel, diffuse}
  mixture), supplied via ``associate(..., prior_b=...)``.

These are two different concepts living on the same field, so the inference
engine sees them as "conflicting marginal providers" and refuses to compile.

As a workaround this package introduces ``f2_dominant_count_specific`` — a
plain ``derive`` node that carries only the specific numerical event and is
**not** entered into ``PRIORS`` — and routes the ``associate`` through it.
This leaves the observation's ``reliability`` prior untouched on
``f2_count_observation`` and lets the Bayesian marginal live cleanly on the
derived node. No other semantic is introduced by this node; it would go away
once the framework separates the ``reliability`` / ``marginal`` / ``belief``
roles on a Claim.
"""

from gaia.lang import associate, claim, contradict, derive, equal, exclusive, note, observe

from .probabilities import (
    DOMINANT_COUNT,
    RECESSIVE_COUNT,
    mendel_count_association_parameters,
)


association_parameters = mendel_count_association_parameters()


monohybrid_cross_setup = note(
    "单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，"
    "另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。"
)

dominance_background = note("在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。")

finite_sample_background = note(
    "F2 的显性/隐性计数是有限样本，因此用点似然（二项 PMF 在观测计数处的取值）"
    "衡量模型与数据的贴合度；对手理论取 p ~ Uniform[0,1] 的 diffuse 先验作为"
    "参考尺度，不引入任何具体的替代二项参数。"
)

mendelian_segregation_model = claim(
    "孟德尔分离模型：遗传因子是离散的；每个个体对某一性状携带一对因子；"
    "形成配子时成对因子分离，受精时重新配对；显性因子会遮蔽隐性因子。"
)

blending_inheritance_model = claim(
    "混合遗传模型：亲本性状在后代中连续平均；一旦平均，离散的显性/隐性类别"
    "就不应在 F2 中作为可计数的类型存在。"
)

competing_models = exclusive(
    mendelian_segregation_model,
    blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="在同一个单因子性状解释上，离散分离模型和连续混合模型是竞争解释。",
    label="competing_models",
)

# -----------------------------------------------------------------------------
# Observations
# -----------------------------------------------------------------------------

f1_uniform_dominant_observation = observe(
    "纯种显性亲本与纯种隐性亲本杂交后，F1 后代统一表现显性表型。",
    background=[monohybrid_cross_setup],
    rationale="这是单因子杂交实验中 F1 代的定性观察。",
    label="f1_uniform_dominant_observation",
)

f2_has_discrete_classes_observation = observe(
    "F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。",
    background=[monohybrid_cross_setup],
    rationale="这是单因子杂交实验中 F2 代的定性观察：表型呈两类，不是连续分布。",
    label="f2_has_discrete_classes_observation",
)

f2_recessive_reappears_observation = observe(
    "F1 自交得到的 F2 后代中，原隐性表型作为离散类别重新出现。",
    background=[monohybrid_cross_setup],
    rationale="这是单因子杂交实验中 F2 代的定性观察。",
    label="f2_recessive_reappears_observation",
)

f2_count_observation = observe(
    f"F2 计数为 {DOMINANT_COUNT} 个显性表型和 {RECESSIVE_COUNT} 个隐性表型，"
    f"共 {DOMINANT_COUNT + RECESSIVE_COUNT} 个个体。",
    background=[monohybrid_cross_setup, f2_has_discrete_classes_observation],
    rationale="这是用于贝叶斯点似然比较的 F2 显性/隐性计数数据。",
    label="f2_count_observation",
)

# -----------------------------------------------------------------------------
# Mendel: qualitative predictions matching the qualitative observations
# -----------------------------------------------------------------------------

mendel_predicts_f1_dominance = derive(
    "如果孟德尔分离模型成立，纯种显性亲本与纯种隐性亲本杂交后，"
    "F1 后代都应携带一个显性因子和一个隐性因子，并表现显性表型。",
    given=mendelian_segregation_model,
    background=[monohybrid_cross_setup, dominance_background],
    rationale="显性因子在杂合 F1 个体中遮蔽隐性因子。",
    label="mendel_predicts_f1_dominance",
)

f1_mendel_match = equal(
    mendel_predicts_f1_dominance,
    f1_uniform_dominant_observation,
    background=[monohybrid_cross_setup],
    rationale="孟德尔模型对 F1 统一显性的预测与观察相符。",
    label="f1_mendel_match",
)

mendel_predicts_discrete_classes = derive(
    "孟德尔分离模型下 F2 的基因型组合为 AA:Aa:aa = 1:2:1，"
    "显性因子遮蔽效应把这三个基因型映射到显性和隐性两个离散表型类别，"
    "因此 F2 应呈现清晰的两类离散表型而非连续谱。",
    given=mendelian_segregation_model,
    background=[monohybrid_cross_setup, dominance_background],
    rationale="离散因子 + 遮蔽 → 两个离散表型类别。",
    label="mendel_predicts_discrete_classes",
)

f2_discrete_classes_mendel_match = equal(
    mendel_predicts_discrete_classes,
    f2_has_discrete_classes_observation,
    background=[monohybrid_cross_setup],
    rationale="孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。",
    label="f2_discrete_classes_mendel_match",
)

mendel_predicts_recessive_reappearance = derive(
    "如果 F1 个体仍携带被遮蔽的隐性因子，那么 F1 自交后，部分 F2 个体会继承"
    "两个隐性因子并重新表现隐性表型。",
    given=mendelian_segregation_model,
    background=[monohybrid_cross_setup, dominance_background],
    rationale="分离模型保留了隐性因子，并允许它在 F2 中重新组合为纯合隐性。",
    label="mendel_predicts_recessive_reappearance",
)

f2_reappearance_mendel_match = equal(
    mendel_predicts_recessive_reappearance,
    f2_recessive_reappears_observation,
    background=[monohybrid_cross_setup],
    rationale="孟德尔模型对 F2 隐性重现的预测与观察相符。",
    label="f2_reappearance_mendel_match",
)

mendel_predicts_three_to_one_ratio = derive(
    "如果 F1 个体自交，成对因子分离会给出 AA:Aa:aa = 1:2:1 的基因型比例；"
    "由于 AA 和 Aa 都表现显性，F2 显性/隐性计数应服从 Binomial(N, 3/4)，"
    "期望表型比约为 3:1。",
    given=mendelian_segregation_model,
    background=[monohybrid_cross_setup, dominance_background, finite_sample_background],
    rationale="F1 配子等概率结合，给出 1:2:1 的基因型分布，即每个 F2 个体"
    "独立以概率 3/4 表现为显性。",
    label="mendel_predicts_three_to_one_ratio",
)

# -----------------------------------------------------------------------------
# A single derived data event carrying the specific count for the probabilistic
# comparison. This is deliberately NOT a tolerance window around the observed
# ratio; it is just the specific observed value, reified as a proposition.
#
# The node exists only to carry the Bayesian marginal ``P(count = 295/395)``
# on a separate Claim from ``f2_count_observation``, which already carries the
# reliability prior 0.95 via ``PRIORS``. See the module docstring above for
# the underlying framework issue (``metadata.prior`` doing double duty as both
# "reliability" and "marginal"). Once the framework separates those two
# semantics, this intermediate node can be deleted and ``associate`` can
# target ``f2_count_observation`` directly.
# -----------------------------------------------------------------------------

f2_dominant_count_specific = derive(
    f"F2 显性表型计数的具体数值为 {DOMINANT_COUNT} / {DOMINANT_COUNT + RECESSIVE_COUNT}。",
    given=f2_count_observation,
    background=[monohybrid_cross_setup, finite_sample_background],
    rationale="把定性观测中的具体计数提取为一个命题，作为 Mendel 与数据进行"
    "概率比较时使用的数据事件；这里也起到把 Bayes 边际和观测可靠性两个概念"
    "分开存放在两个不同 Claim 上的作用，规避 v0.5 framework 中 metadata.prior"
    "的一号多用。",
    label="f2_dominant_count_specific",
)

# -----------------------------------------------------------------------------
# Mendel: the one quantitative link — associate(model, count) via pointwise PMF
# -----------------------------------------------------------------------------

mendel_count_association = associate(
    mendelian_segregation_model,
    f2_dominant_count_specific,
    background=[monohybrid_cross_setup, finite_sample_background],
    p_a_given_b=association_parameters.p_mendelian_given_count,
    p_b_given_a=association_parameters.p_count_given_mendelian,
    prior_a=association_parameters.prior_mendelian,
    prior_b=association_parameters.prior_count,
    rationale=(
        "用在观测计数处的点似然 Binomial(N, 3/4).pmf(295) 作为 p(count | Mendel)；"
        "对照项用 p ~ Uniform[0, 1] 的 diffuse 先验，其任意单点计数的边际概率"
        "为解析解 1 / (N + 1)。这样所有参数都来自两个明确的假设，"
        "既没有 tolerance 窗口，也没有人为指定的替代二项参数。"
    ),
    label="mendel_count_association",
)

# -----------------------------------------------------------------------------
# Blending: three qualitative predictions, each clashing with a qualitative
# observation via contradict. Blending does NOT participate in associate, by
# design: it is not a generative model for the dominant/recessive count.
# -----------------------------------------------------------------------------

blending_predicts_intermediate_f1 = derive(
    "如果混合遗传模型成立，F1 后代应倾向于中间或混合表型，而不是统一表现某一亲本表型。",
    given=blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="连续平均模型把亲本性状视为在后代中均化。",
    label="blending_predicts_intermediate_f1",
)

f1_blending_conflict = contradict(
    blending_predicts_intermediate_f1,
    f1_uniform_dominant_observation,
    background=[monohybrid_cross_setup],
    rationale="F1 统一显性与混合模型的中间表型预测相冲突。",
    label="f1_blending_conflict",
)

blending_predicts_f2_continuous = derive(
    "如果亲本性状在 F1 中连续平均，F2 应形成单峰连续分布，"
    "不能被划分为清晰的显性/隐性两个离散类别。",
    given=blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="连续平均不保留可重新组合的离散遗传单位，因此不给出离散的表型分类。",
    label="blending_predicts_f2_continuous",
)

f2_discrete_classes_blending_conflict = contradict(
    blending_predicts_f2_continuous,
    f2_has_discrete_classes_observation,
    background=[monohybrid_cross_setup],
    rationale="F2 明确划分为两类离散表型，与混合模型的连续分布预测相冲突——"
    "这是 framework 级别的冲突：blending 否认的是 F2 可被分类这件事本身。",
    label="f2_discrete_classes_blending_conflict",
)

blending_predicts_no_recessive_reappearance = derive(
    "连续平均的性状不保留可以重新组合的离散遗传单位，"
    "因此原隐性表型不应作为离散类别在 F2 中重新出现。",
    given=blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="混合模型没有保留可重新组合的离散隐性因子。",
    label="blending_predicts_no_recessive_reappearance",
)

f2_reappearance_blending_conflict = contradict(
    blending_predicts_no_recessive_reappearance,
    f2_recessive_reappears_observation,
    background=[monohybrid_cross_setup],
    rationale="F2 隐性表型作为离散类别重新出现，与混合模型的预测相冲突。",
    label="f2_reappearance_blending_conflict",
)


__all__ = [
    "mendelian_segregation_model",
    "blending_inheritance_model",
    "competing_models",
    "f1_uniform_dominant_observation",
    "f2_has_discrete_classes_observation",
    "f2_recessive_reappears_observation",
    "f2_count_observation",
    "mendel_predicts_f1_dominance",
    "f1_mendel_match",
    "mendel_predicts_discrete_classes",
    "f2_discrete_classes_mendel_match",
    "mendel_predicts_recessive_reappearance",
    "f2_reappearance_mendel_match",
    "mendel_predicts_three_to_one_ratio",
    "f2_dominant_count_specific",
    "mendel_count_association",
    "blending_predicts_intermediate_f1",
    "f1_blending_conflict",
    "blending_predicts_f2_continuous",
    "f2_discrete_classes_blending_conflict",
    "blending_predicts_no_recessive_reappearance",
    "f2_reappearance_blending_conflict",
]
