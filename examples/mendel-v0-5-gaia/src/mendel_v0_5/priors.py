"""Prior records for the Mendel v0.5 example package."""

from mendel_v0_5 import (
    blending_inheritance_model,
    f1_uniform_dominant_observation,
    f2_count_observation,
    f2_dominant_count_specific,
    f2_has_discrete_classes_observation,
    f2_recessive_reappears_observation,
    mendel_count_association_parameters,
    mendelian_segregation_model,
)
from mendel_v0_5.probabilities import PRIOR_MENDELIAN_MODEL

association_parameters = mendel_count_association_parameters()

PRIORS = {
    mendelian_segregation_model: (
        PRIOR_MENDELIAN_MODEL,
        "在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。",
    ),
    blending_inheritance_model: (
        1.0 - PRIOR_MENDELIAN_MODEL,
        "在观察单因子杂交结果之前，让混合遗传模型保持中性先验。",
    ),
    f1_uniform_dominant_observation: (
        0.95,
        "把 F1 统一显性作为可靠的实验观察。",
    ),
    f2_has_discrete_classes_observation: (
        0.95,
        "把 F2 呈两类离散表型作为可靠的实验观察。",
    ),
    f2_recessive_reappears_observation: (
        0.95,
        "把 F2 隐性表型重新出现作为可靠的实验观察。",
    ),
    f2_count_observation: (
        0.95,
        "把 F2 显性/隐性计数作为可靠的实验观察。",
    ),
    f2_dominant_count_specific: (
        association_parameters.prior_count,
        "把具体计数事件在 {Mendel, diffuse} 混合模型下的 Bayes 边际作为"
        "该中间命题的 prior；它不是观测报告可靠性。",
    ),
}
