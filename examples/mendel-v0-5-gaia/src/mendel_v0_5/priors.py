"""Prior records for the Mendel v0.5 example package.

Priors are registered through :func:`gaia.lang.register_prior` rather than the
legacy ``PRIORS = {...}`` dict (removed in v0.5+). Each call records a
multi-source ``PriorRecord``; the package-default ``ResolutionPolicy`` (see
:func:`gaia.ir.default_resolution_policy`) selects the winning value at
compile time and writes it to ``metadata['prior']`` for downstream BP /
render / brief consumers.
"""

from gaia.lang import register_prior
from mendel_v0_5 import (
    blending_inheritance_model,
    f1_uniform_dominant_observation,
    f2_count_observation,
    f2_has_discrete_classes_observation,
    f2_recessive_reappears_observation,
    mendelian_segregation_model,
)
from mendel_v0_5.probabilities import PRIOR_MENDELIAN_MODEL

register_prior(
    mendelian_segregation_model,
    value=PRIOR_MENDELIAN_MODEL,
    justification="在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。",
)
register_prior(
    blending_inheritance_model,
    value=1.0 - PRIOR_MENDELIAN_MODEL,
    justification="在观察单因子杂交结果之前，让混合遗传模型保持中性先验。",
)
register_prior(
    f1_uniform_dominant_observation,
    value=0.95,
    justification="把 F1 统一显性作为可靠的实验观察。",
)
register_prior(
    f2_has_discrete_classes_observation,
    value=0.95,
    justification="把 F2 呈两类离散表型作为可靠的实验观察。",
)
register_prior(
    f2_recessive_reappears_observation,
    value=0.95,
    justification="把 F2 隐性表型重新出现作为可靠的实验观察。",
)
register_prior(
    f2_count_observation,
    value=0.95,
    justification="把 F2 显性/隐性计数作为可靠的实验观察。",
)
