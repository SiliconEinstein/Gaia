"""Mendel-style probability example — v0.6 unified Bayes interface.

Architecture
------------

Two theories compete for the same single-factor cross:

* ``mendelian_segregation_model`` — discrete particulate inheritance with a
  clean ``P(dominant) = 3/4`` generative model for F2 counts.
* ``blending_inheritance_model`` — continuous averaging of parental traits;
  denies that discrete dominant/recessive classes exist in F2 at all.

The quantitative count comparison uses the v0.6 unified Bayes surface
(``bayes.model / observe / bayes.compare``) rather than the earlier
alpha trio (``bayes.model / bayes.data / bayes.likelihood``):

* Mendel is represented by ``Binomial(name, n=395, p=3/4)``.
* The diffuse alternative is represented by
  ``BetaBinomial(name, n=395, alpha=1, beta=1)``, which is the predictive
  distribution obtained by integrating ``Binomial(n, p)`` over
  ``p ~ Uniform[0, 1]``.
* The observed count is recorded via ``observe(f2_dominant_count,
  value=DOMINANT_COUNT)`` directly on the count Variable — no separate
  data-formula claim is needed.

Predictive distributions are :class:`Distribution` Knowledge objects from
``gaia.engine.lang``, so each distribution carries a human-readable name
("F2 dominant count under Mendel 3:1") and is independently reviewable.
"""

import gaia.engine.bayes as bayes
from gaia.engine.lang import (
    BetaBinomial,
    Binomial,
    Nat,
    Variable,
    claim,
    contradict,
    derive,
    equal,
    exclusive,
    note,
    observe,
)

from .probabilities import (
    DOMINANT_COUNT,
    MENDELIAN_DOMINANT_PROBABILITY,
    RECESSIVE_COUNT,
    TOTAL_COUNT,
)

f2_total_count = Variable(symbol="n_f2", domain=Nat, value=TOTAL_COUNT)
f2_dominant_count = Variable(symbol="k_dominant", domain=Nat, value=DOMINANT_COUNT)

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
    f2_dominant_count,
    value=DOMINANT_COUNT,
    background=[monohybrid_cross_setup, f2_has_discrete_classes_observation],
    rationale=(
        f"F2 计数：{DOMINANT_COUNT} 个显性表型，{RECESSIVE_COUNT} 个隐性表型，"
        f"共 {TOTAL_COUNT} 个个体。这是用于贝叶斯点似然比较的 F2 计数数据 [@Mendel1866]。"
    ),
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
# Quantitative count comparison via gaia.engine.bayes (v0.6 unified surface)
# -----------------------------------------------------------------------------
#
# model(...) declares the predictive distribution as a named Distribution
# Knowledge object (reviewable in its own right). compare(data, models=[...])
# evaluates the log-likelihood of f2_count_observation under each predictive
# distribution and emits one infer factor per hypothesis. The observation
# itself is a Variable-targeted observe(...) — no formula plumbing.

mendel_count_model = bayes.model(
    mendelian_segregation_model,
    observable=f2_dominant_count,
    distribution=Binomial(
        "F2 dominant count under Mendel 3:1",
        n=TOTAL_COUNT,
        p=MENDELIAN_DOMINANT_PROBABILITY,
    ),
    background=[monohybrid_cross_setup, dominance_background, finite_sample_background],
    rationale=(
        "孟德尔分离模型给出 F2 每个个体以概率 3/4 表现显性的生成模型，"
        "因此显性计数服从 Binomial(N, 3/4)。"
    ),
    label="mendel_count_model",
)

diffuse_count_model = bayes.model(
    blending_inheritance_model,
    observable=f2_dominant_count,
    distribution=BetaBinomial(
        "F2 dominant count under p ~ Uniform[0, 1]",
        n=TOTAL_COUNT,
        alpha=1.0,
        beta=1.0,
    ),
    background=[monohybrid_cross_setup, finite_sample_background],
    rationale=(
        "把对照项写成 p ~ Uniform[0, 1] 下的 BetaBinomial(N, 1, 1) 预测分布；"
        "它给出任意具体计数的边际概率 1 / (N + 1)，不人为指定第二个二项参数。"
    ),
    label="diffuse_count_model",
)

mendel_count_likelihood = bayes.compare(
    f2_count_observation,
    models=[mendel_count_model, diffuse_count_model],
    background=[monohybrid_cross_setup, finite_sample_background],
    rationale=(
        "直接比较观测到的 F2 显性计数在 Mendel 点模型和 diffuse 参考模型下的"
        "log likelihood；观测可靠性仍留在 f2_count_observation 的 prior 中。"
    ),
    # ``exclusivity`` defaults to ``"exhaustive_pairwise_complement"``;
    # the external ``competing_models = exclusive(...)`` declared above
    # already covers (mendelian_segregation_model,
    # blending_inheritance_model), so compare() deduplicates against it
    # rather than re-emitting a second Exclusive helper. The earlier
    # ``exclusivity="none"`` workaround is no longer needed.
    label="mendel_count_likelihood",
)

# -----------------------------------------------------------------------------
# Blending: three qualitative predictions, each clashing with a qualitative
# observation via contradict.
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
    "blending_inheritance_model",
    "blending_predicts_f2_continuous",
    "blending_predicts_intermediate_f1",
    "blending_predicts_no_recessive_reappearance",
    "competing_models",
    "diffuse_count_model",
    "f1_blending_conflict",
    "f1_mendel_match",
    "f1_uniform_dominant_observation",
    "f2_count_observation",
    "f2_discrete_classes_blending_conflict",
    "f2_discrete_classes_mendel_match",
    "f2_has_discrete_classes_observation",
    "f2_reappearance_blending_conflict",
    "f2_reappearance_mendel_match",
    "f2_recessive_reappears_observation",
    "mendel_count_likelihood",
    "mendel_count_model",
    "mendel_predicts_discrete_classes",
    "mendel_predicts_f1_dominance",
    "mendel_predicts_recessive_reappearance",
    "mendel_predicts_three_to_one_ratio",
    "mendelian_segregation_model",
]
