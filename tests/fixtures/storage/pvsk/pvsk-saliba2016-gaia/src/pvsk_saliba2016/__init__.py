"""Saliba et al. Energy & Environmental Science 2016 — Cesium-containing triple cation
perovskite solar cells: improved stability, reproducibility and high efficiency."""

from gaia.lang import claim, setting, support, deduction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# --- Background ---
device_fabrication = setting(
    "Perovskite solar cells fabricated with triple cation Cs/(MA/FA) compositions "
    "in mesoporous TiO2 architecture, measured under standard AM1.5G illumination"
)

# --- Core claims ---
triple_cation_stable = claim(
    "Adding inorganic cesium to FA/MA mixed perovskite compositions produces "
    "thermally more stable perovskites with fewer phase impurities",
    prior=0.88,
)

less_processing_sensitive = claim(
    "Triple cation Cs-containing perovskite compositions are less sensitive to "
    "processing conditions than binary FA/MA compositions, enabling more reproducible "
    "device fabrication",
    prior=0.85,
)

stabilized_output_21_1_pct = claim(
    "Triple cation perovskite solar cells achieve a stabilized power output of 21.1%, "
    "representing the highest stabilized efficiency at the time of publication",
    prior=0.92,
)

operational_18_pct_250h = claim(
    "Triple cation devices maintain approximately 18% efficiency after 250 hours "
    "under operational conditions, demonstrating improved stability",
    prior=0.85,
)

cesium_reduces_impurities = claim(
    "Cs incorporation suppresses the formation of the non-perovskite delta-phase "
    "in FAPbI3-based compositions, producing monomorphic phase-pure perovskite films",
    prior=0.87,
)

reproducibility_improved = claim(
    "Triple cation devices show significantly improved batch-to-batch reproducibility "
    "compared to binary FA/MA compositions, with reduced standard deviation in PCE",
    prior=0.83,
)

black_phase_stable = claim(
    "The triple cation composition stabilizes the black perovskite phase at room "
    "temperature without requiring high-temperature annealing above 160C",
    prior=0.85,
)

morphology_improved = claim(
    "Cs-containing perovskite films exhibit smoother, more uniform morphology with "
    "larger grain size compared to binary FA/MA films",
    prior=0.80,
)

key_for_industrialization = claim(
    "The improved reproducibility, stability, and reduced processing sensitivity of "
    "triple cation compositions are key properties for industrialization of perovskite "
    "photovoltaics",
    prior=0.70,
)

# --- Internal reasoning ---
support(
    [cesium_reduces_impurities, morphology_improved],
    triple_cation_stable,
    reason="Cs eliminates phase impurities and improves film morphology, yielding "
    "thermally stable perovskite compositions",
    prior=0.492,
)

support(
    [triple_cation_stable, less_processing_sensitive],
    stabilized_output_21_1_pct,
    reason="Phase-pure stable compositions with reduced processing sensitivity enable "
    "consistent achievement of high stabilized efficiency",
    prior=0.51,
)

support(
    [triple_cation_stable, black_phase_stable],
    operational_18_pct_250h,
    reason="Thermal and phase stability of triple cation composition enables sustained "
    "performance under operational conditions",
    prior=0.48,
)

deduction(
    [reproducibility_improved, less_processing_sensitive],
    key_for_industrialization,
    reason="Manufacturing requires both high reproducibility and low sensitivity to "
    "processing variations — triple cation compositions address both",
    prior=0.42,
)

# --- Connection to meta propositions ---
support(
    [stabilized_output_21_1_pct],
    p_efficiency,
    reason="Achieving 21.1% stabilized power output demonstrates perovskite solar "
    "cells can exceed the 20% efficiency threshold for commercial competition",
    prior=0.42,
)

support(
    [operational_18_pct_250h, triple_cation_stable],
    p_stability,
    reason="Maintaining ~18% efficiency over 250 operational hours with improved "
    "thermal stability demonstrates progress toward practical stability requirements",
    prior=0.36,
)

support(
    [reproducibility_improved, less_processing_sensitive],
    p_industrialization,
    reason="Triple cation compositions address key manufacturing requirements: "
    "reproducibility and processing robustness",
    prior=0.36,
)

support(
    [cesium_reduces_impurities, morphology_improved, stabilized_output_21_1_pct],
    p_improvement,
    reason="Systematic compositional engineering through Cs addition produces clear "
    "improvements in phase purity, morphology, and efficiency over binary compositions",
    prior=0.39,
)

__all__ = [
    "device_fabrication",
    "triple_cation_stable",
    "less_processing_sensitive",
    "stabilized_output_21_1_pct",
    "operational_18_pct_250h",
    "cesium_reduces_impurities",
    "reproducibility_improved",
    "black_phase_stable",
    "morphology_improved",
    "key_for_industrialization",
]
