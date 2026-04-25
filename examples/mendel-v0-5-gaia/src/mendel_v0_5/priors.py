from mendel_v0_5 import (
    blending_inheritance_model,
    f1_uniform_dominant_observation,
    f2_count_observation,
    f2_recessive_reappears_observation,
    mendelian_segregation_model,
)
from mendel_v0_5.probabilities import mendel_data_association_parameters


association_parameters = mendel_data_association_parameters()


PRIORS = {
    mendelian_segregation_model: (
        association_parameters.prior_mendelian,
        "在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。",
    ),
    blending_inheritance_model: (
        association_parameters.prior_blending,
        "在观察单因子杂交结果之前，让混合遗传模型保持中性先验。",
    ),
    f1_uniform_dominant_observation: (
        0.95,
        "把 F1 统一显性作为可靠的实验观察。",
    ),
    f2_recessive_reappears_observation: (
        0.95,
        "把 F2 隐性表型重新出现作为可靠的实验观察。",
    ),
    f2_count_observation: (
        0.95,
        "把 F2 显性/隐性计数作为可靠的实验观察。",
    ),
}
