#!/usr/bin/env bash
#
# CLI-authored Mendel walkthrough (bayes + Variable + multi-file)
#
# Bundled with `gaia example mendel`. The placeholder
# './mendel-cli-mirror-gaia' is substituted by the cli verb when
# `--target NAME` is passed. Run the cli verb to print or save this
# script:
#
#     gaia example mendel
#     gaia example mendel --target ./my-demo
#     gaia example mendel --out walkthrough.sh
#
set -euo pipefail


# 1. Scaffold the package skeleton

gaia pkg scaffold \
    --target ./mendel-cli-mirror-gaia \
    --name mendel-v0-5-gaia \
    --namespace example

python -c "
import pathlib
p = pathlib.Path('mendel-cli-mirror-gaia/src/mendel_v0_5/__init__.py')
src = p.read_text()
end = src.find('hypothesis = claim(')
if end > 0:
    p.write_text(src[:end].rstrip() + '\n')
"


# 2. Declare the two `Variable(...)` typed terms

gaia author variable \
  --label f2_total_count --symbol n_f2 --domain Nat --value 395 \
  --target ./mendel-cli-mirror-gaia

gaia author variable \
  --label f2_dominant_count --symbol k_dominant --domain Nat --value 295 \
  --target ./mendel-cli-mirror-gaia


# 3. Author the three contextual notes

gaia author note \
  "单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。" \
  --label monohybrid_cross_setup \
  --target ./mendel-cli-mirror-gaia

gaia author note \
  "在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。" \
  --label dominance_background \
  --target ./mendel-cli-mirror-gaia

gaia author note \
  "F2 的显性/隐性计数是有限样本，因此用点似然（二项 PMF 在观测计数处的取值）衡量模型与数据的贴合度；对手理论取 p ~ Uniform[0,1] 的 diffuse 先验作为参考尺度，不引入任何具体的替代二项参数。" \
  --label finite_sample_background \
  --target ./mendel-cli-mirror-gaia


# 4. Author the two competing model claims + the `exclusive` operator

gaia author claim \
  "孟德尔分离模型：遗传因子是离散的；每个个体对某一性状携带一对因子；形成配子时成对因子分离，受精时重新配对；显性因子会遮蔽隐性因子。" \
  --label mendelian_segregation_model \
  --target ./mendel-cli-mirror-gaia

gaia author claim \
  "混合遗传模型：亲本性状在后代中连续平均；一旦平均，离散的显性/隐性类别就不应在 F2 中作为可计数的类型存在。" \
  --label blending_inheritance_model \
  --target ./mendel-cli-mirror-gaia

gaia author exclusive \
  --a mendelian_segregation_model --b blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "在同一个单因子性状解释上，离散分离模型和连续混合模型是竞争解释。" \
  --label competing_models \
  --target ./mendel-cli-mirror-gaia


# 5. Author the observations

gaia author observe \
  --observation-prose "纯种显性亲本与纯种隐性亲本杂交后，F1 后代统一表现显性表型。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F1 代的定性观察。" \
  --label f1_uniform_dominant_observation \
  --target ./mendel-cli-mirror-gaia

gaia author observe \
  --observation-prose "F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F2 代的定性观察：表型呈两类，不是连续分布。" \
  --label f2_has_discrete_classes_observation \
  --target ./mendel-cli-mirror-gaia

gaia author observe \
  --observation-prose "F1 自交得到的 F2 后代中，原隐性表型作为离散类别重新出现。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F2 代的定性观察。" \
  --label f2_recessive_reappears_observation \
  --target ./mendel-cli-mirror-gaia

gaia author observe \
  --conclusion f2_dominant_count \
  --value 295 \
  --background monohybrid_cross_setup,f2_has_discrete_classes_observation \
  --rationale "这是用于贝叶斯点似然比较的 F2 显性/隐性计数数据。" \
  --label f2_count_observation \
  --target ./mendel-cli-mirror-gaia


# 6. Author the five Mendel qualitative derivations + three matches

gaia author derive \
  --conclusion-prose "如果孟德尔分离模型成立，纯种显性亲本与纯种隐性亲本杂交后，F1 后代都应携带一个显性因子和一个隐性因子，并表现显性表型。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "显性因子在杂合 F1 个体中遮蔽隐性因子。" \
  --label mendel_predicts_f1_dominance \
  --target ./mendel-cli-mirror-gaia

gaia author equal \
  --a mendel_predicts_f1_dominance --b f1_uniform_dominant_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型对 F1 统一显性的预测与观察相符。" \
  --label f1_mendel_match \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "孟德尔分离模型下 F2 的基因型组合为 AA:Aa:aa = 1:2:1，显性因子遮蔽效应把这三个基因型映射到显性和隐性两个离散表型类别，因此 F2 应呈现清晰的两类离散表型而非连续谱。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "离散因子 + 遮蔽 → 两个离散表型类别。" \
  --label mendel_predicts_discrete_classes \
  --target ./mendel-cli-mirror-gaia

gaia author equal \
  --a mendel_predicts_discrete_classes --b f2_has_discrete_classes_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。" \
  --label f2_discrete_classes_mendel_match \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "如果 F1 个体仍携带被遮蔽的隐性因子，那么 F1 自交后，部分 F2 个体会继承两个隐性因子并重新表现隐性表型。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "分离模型保留了隐性因子，并允许它在 F2 中重新组合为纯合隐性。" \
  --label mendel_predicts_recessive_reappearance \
  --target ./mendel-cli-mirror-gaia

gaia author equal \
  --a mendel_predicts_recessive_reappearance --b f2_recessive_reappears_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型对 F2 隐性重现的预测与观察相符。" \
  --label f2_reappearance_mendel_match \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "如果 F1 个体自交，成对因子分离会给出 AA:Aa:aa = 1:2:1 的基因型比例；由于 AA 和 Aa 都表现显性，F2 显性/隐性计数应服从 Binomial(N, 3/4)，期望表型比约为 3:1。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background,finite_sample_background \
  --rationale "F1 配子等概率结合，给出 1:2:1 的基因型分布，即每个 F2 个体独立以概率 3/4 表现为显性。" \
  --label mendel_predicts_three_to_one_ratio \
  --target ./mendel-cli-mirror-gaia


# 7. Author the quantitative bayes comparison

gaia bayes model \
  --hypothesis mendelian_segregation_model \
  --observable f2_dominant_count \
  --distribution 'Binomial("F2 dominant count under Mendel 3:1", n=395, p=3/4)' \
  --background monohybrid_cross_setup,dominance_background,finite_sample_background \
  --rationale "孟德尔分离模型给出 F2 每个个体以概率 3/4 表现显性的生成模型，因此显性计数服从 Binomial(N, 3/4)。" \
  --label mendel_count_model \
  --target ./mendel-cli-mirror-gaia

gaia bayes model \
  --hypothesis blending_inheritance_model \
  --observable f2_dominant_count \
  --distribution 'BetaBinomial("F2 dominant count under p ~ Uniform[0, 1]", n=395, alpha=1.0, beta=1.0)' \
  --background monohybrid_cross_setup,finite_sample_background \
  --rationale "把对照项写成 p ~ Uniform[0, 1] 下的 BetaBinomial(N, 1, 1) 预测分布；它给出任意具体计数的边际概率 1 / (N + 1)，不人为指定第二个二项参数。" \
  --label diffuse_count_model \
  --target ./mendel-cli-mirror-gaia

gaia bayes compare \
  --data f2_count_observation \
  --model mendel_count_model \
  --against diffuse_count_model \
  --background monohybrid_cross_setup,finite_sample_background \
  --rationale "直接比较观测到的 F2 显性计数在 Mendel 点模型和 diffuse 参考模型下的 log likelihood；观测可靠性仍留在 f2_count_observation 的 prior 中。" \
  --label mendel_count_likelihood \
  --target ./mendel-cli-mirror-gaia


# 8. Author the three Blending derivations + three contradictions

gaia author derive \
  --conclusion-prose "如果混合遗传模型成立，F1 后代应倾向于中间或混合表型，而不是统一表现某一亲本表型。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "连续平均模型把亲本性状视为在后代中均化。" \
  --label blending_predicts_intermediate_f1 \
  --target ./mendel-cli-mirror-gaia

gaia author contradict \
  --a blending_predicts_intermediate_f1 --b f1_uniform_dominant_observation \
  --background monohybrid_cross_setup \
  --rationale "F1 统一显性与混合模型的中间表型预测相冲突。" \
  --label f1_blending_conflict \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "如果亲本性状在 F1 中连续平均，F2 应形成单峰连续分布，不能被划分为清晰的显性/隐性两个离散类别。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "连续平均不保留可重新组合的离散遗传单位，因此不给出离散的表型分类。" \
  --label blending_predicts_f2_continuous \
  --target ./mendel-cli-mirror-gaia

gaia author contradict \
  --a blending_predicts_f2_continuous --b f2_has_discrete_classes_observation \
  --background monohybrid_cross_setup \
  --rationale "F2 明确划分为两类离散表型，与混合模型的连续分布预测相冲突——这是 framework 级别的冲突：blending 否认的是 F2 可被分类这件事本身。" \
  --label f2_discrete_classes_blending_conflict \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "连续平均的性状不保留可以重新组合的离散遗传单位，因此原隐性表型不应作为离散类别在 F2 中重新出现。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "混合模型没有保留可重新组合的离散隐性因子。" \
  --label blending_predicts_no_recessive_reappearance \
  --target ./mendel-cli-mirror-gaia

gaia author contradict \
  --a blending_predicts_no_recessive_reappearance --b f2_recessive_reappears_observation \
  --background monohybrid_cross_setup \
  --rationale "F2 隐性表型作为离散类别重新出现，与混合模型的预测相冲突。" \
  --label f2_reappearance_blending_conflict \
  --target ./mendel-cli-mirror-gaia


# 9. Scaffold `priors.py` and register the six priors

gaia pkg add-module --name priors --imports register_prior \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim mendelian_segregation_model --value 0.5 \
  --justification "在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim blending_inheritance_model --value 0.5 \
  --justification "在观察单因子杂交结果之前，让混合遗传模型保持中性先验。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f1_uniform_dominant_observation --value 0.95 \
  --justification "把 F1 统一显性作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f2_has_discrete_classes_observation --value 0.95 \
  --justification "把 F2 呈两类离散表型作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f2_recessive_reappears_observation --value 0.95 \
  --justification "把 F2 隐性表型重新出现作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f2_count_observation --value 0.95 \
  --justification "把 F2 显性/隐性计数作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

cd mendel-cli-mirror-gaia
gaia build compile
# → Compiled 44 knowledge, 9 strategies, 7 operators
gaia build check
