"""Mendel-style probability example for Gaia v0.5."""

from gaia.lang import associate, claim, contradict, derive, equal, exclusive, note, observe

from .probabilities import (
    DOMINANT_COUNT,
    RATIO_TOLERANCE,
    RECESSIVE_COUNT,
    mendel_data_association_parameters,
)


association_parameters = mendel_data_association_parameters()

monohybrid_cross_setup = note(
    "单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，"
    "另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。"
)

dominance_background = note("在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。")

binomial_sampling_model = note(
    "F2 的显性/隐性计数被视为有限样本；因此观测比例只需要落在理论比例附近，不需要严格等于理论比例。"
)

mendelian_segregation_model = claim(
    "孟德尔分离模型：遗传因子是离散的；每个个体对某一性状携带一对因子；"
    "形成配子时成对因子分离，受精时重新配对；显性因子会遮蔽隐性因子。"
)

blending_inheritance_model = claim(
    "混合遗传模型：亲本性状在后代中发生连续混合；一旦混合，原始隐性性状不应以离散类别稳定恢复。"
)

competing_models = exclusive(
    mendelian_segregation_model,
    blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="在同一个单因子性状解释上，离散分离模型和连续混合模型是竞争解释。",
    label="competing_models",
)

f1_uniform_dominant_observation = observe(
    "纯种显性亲本与纯种隐性亲本杂交后，F1 后代统一表现显性表型。",
    background=[monohybrid_cross_setup],
    rationale="这是单因子杂交实验中 F1 代的定性观察。",
    label="f1_uniform_dominant_observation",
)

f2_recessive_reappears_observation = observe(
    "F1 自交得到的 F2 后代中，隐性表型重新出现。",
    background=[monohybrid_cross_setup],
    rationale="这是单因子杂交实验中 F2 代的定性观察。",
    label="f2_recessive_reappears_observation",
)

f2_count_observation = observe(
    f"F2 计数为 {DOMINANT_COUNT} 个显性表型和 {RECESSIVE_COUNT} 个隐性表型，"
    "显性与隐性的比例约为 2.95:1。",
    background=[monohybrid_cross_setup, binomial_sampling_model],
    rationale="这是用于统计比较的 F2 显性/隐性计数数据。",
    label="f2_count_observation",
)

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
    "由于 AA 和 Aa 都表现显性，F2 表型比例应接近显性:隐性 = 3:1。",
    given=mendelian_segregation_model,
    background=[monohybrid_cross_setup, dominance_background],
    rationale="F1 的两个配子类型等概率结合，产生 1:2:1 的基因型比例。",
    label="mendel_predicts_three_to_one_ratio",
)

f2_ratio_near_three_to_one = derive(
    f"观测到的 F2 比例 2.95:1 落在 3:1 附近 ±{RATIO_TOLERANCE} 的统计窗口内。",
    given=f2_count_observation,
    background=[binomial_sampling_model],
    rationale="该结论由显性/隐性计数直接计算得到，是后续统计相容性比较的数据事件。",
    label="f2_ratio_near_three_to_one",
)

mendel_data_association = associate(
    mendelian_segregation_model,
    f2_ratio_near_three_to_one,
    background=[monohybrid_cross_setup, binomial_sampling_model],
    p_a_given_b=association_parameters.p_mendelian_given_ratio,
    p_b_given_a=association_parameters.p_ratio_given_mendelian,
    prior_a=association_parameters.prior_mendelian,
    prior_b=association_parameters.prior_ratio,
    rationale=(
        "2.95:1 的 F2 比例事件在孟德尔 3:1 模型下的二项窗口概率显著高于"
        "混合遗传替代模型；这里的 associate 参数由 probabilities.py 计算得到。"
    ),
    label="mendel_data_association",
)
mendel_data_association.label = "mendel_data_association"

blending_predicts_intermediate_f1 = derive(
    "如果混合遗传模型成立，F1 后代应倾向于中间或混合表型，而不是统一表现某一亲本表型。",
    given=blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="连续混合模型把亲本性状视为在后代中混合。",
    label="blending_predicts_intermediate_f1",
)

f1_blending_conflict = contradict(
    blending_predicts_intermediate_f1,
    f1_uniform_dominant_observation,
    background=[monohybrid_cross_setup],
    rationale="F1 统一显性与混合模型的中间表型预测相冲突。",
    label="f1_blending_conflict",
)

blending_predicts_no_discrete_reappearance = derive(
    "如果亲本性状在 F1 中连续混合，原始隐性表型不应在 F2 中作为离散类别稳定恢复。",
    given=blending_inheritance_model,
    background=[monohybrid_cross_setup],
    rationale="混合模型没有保留可重新组合的离散隐性因子。",
    label="blending_predicts_no_discrete_reappearance",
)

f2_reappearance_blending_conflict = contradict(
    blending_predicts_no_discrete_reappearance,
    f2_recessive_reappears_observation,
    background=[monohybrid_cross_setup],
    rationale="F2 隐性表型重新出现与混合模型的预测相冲突。",
    label="f2_reappearance_blending_conflict",
)

blending_predicts_no_stable_three_to_one = derive(
    "混合遗传模型不自然预测 F2 显性/隐性表型会稳定落在 3:1 附近。",
    given=blending_inheritance_model,
    background=[monohybrid_cross_setup, binomial_sampling_model],
    rationale="连续混合模型不是离散 1:2:1 基因型分离模型，因此不直接给出 3:1 表型比例。",
    label="blending_predicts_no_stable_three_to_one",
)

ratio_blending_conflict = contradict(
    blending_predicts_no_stable_three_to_one,
    f2_ratio_near_three_to_one,
    background=[binomial_sampling_model],
    rationale="F2 比例落在 3:1 附近，与混合模型不预测稳定 3:1 的说法相冲突。",
    label="ratio_blending_conflict",
)

__all__ = [
    "mendelian_segregation_model",
    "blending_inheritance_model",
    "competing_models",
    "f1_uniform_dominant_observation",
    "f2_recessive_reappears_observation",
    "f2_count_observation",
    "mendel_predicts_f1_dominance",
    "f1_mendel_match",
    "mendel_predicts_recessive_reappearance",
    "f2_reappearance_mendel_match",
    "mendel_predicts_three_to_one_ratio",
    "f2_ratio_near_three_to_one",
    "mendel_data_association",
    "blending_predicts_intermediate_f1",
    "f1_blending_conflict",
    "blending_predicts_no_discrete_reappearance",
    "f2_reappearance_blending_conflict",
    "blending_predicts_no_stable_three_to_one",
    "ratio_blending_conflict",
]
