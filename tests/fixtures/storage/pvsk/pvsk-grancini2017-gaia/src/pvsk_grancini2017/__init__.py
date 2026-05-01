"""Grancini et al. Nature Communications 2017 — One-year stable perovskite solar cells
by 2D/3D interface engineering. Ultra-stable 2D/3D perovskite junction for long-term operation."""

from gaia.lang import claim, setting, support, deduction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# --- Background ---
htmc_free_config = claim(
    "HTM-free solar cells and modules using hydrophobic carbon electrodes "
    "instead of organic hole transporting materials, reducing cost and improving stability"
,
    prior=0.70,
)

# --- Core claims ---
two_d_three_d_interface = claim(
    "Engineering a 2D/3D (HOOC(CH2)4NH3)2PbI4/CH3NH3PbI3 perovskite junction creates "
    "an exceptional gradually-organized multi-dimensional interface that combines "
    "2D perovskite stability with 3D perovskite charge transport",
    prior=0.85,
)

one_year_stability = claim(
    "2D/3D engineered perovskite devices maintain stable performance for over one year, "
    "corresponding to >10,000 hours of operation",
    prior=0.88,
)

carbon_cell_12_9_pct = claim(
    "2D/3D perovskite achieves up to 12.9% efficiency in carbon-based architecture "
    "and 14.6% in standard mesoporous solar cells",
    prior=0.85,
)

module_10x10_stable = claim(
    "10x10 cm2 solar modules fabricated by fully printable industrial-scale process "
    "deliver 11.2% efficiency stable for >10,000 hours with zero loss in performance "
    "measured under controlled standard conditions",
    prior=0.87,
)

two_d_water_resistant = claim(
    "2D perovskites exhibit superior stability and water resistance compared to "
    "3D perovskites, preventing hydrolysis and irreversible degradation under moisture",
    prior=0.83,
)

gradual_interface = claim(
    "The 2D/3D interface forms a gradually-organized multi-dimensional structure that "
    "provides continuous charge transport pathways while maintaining enhanced stability",
    prior=0.80,
)

scalable_printable = claim(
    "The 2D/3D perovskite architecture is compatible with fully printable "
    "industrial-scale processes for large-area module fabrication",
    prior=0.78,
)

oxygen_moisture_tolerant = claim(
    "2D/3D perovskite modules maintain stable performance under controlled standard "
    "conditions in the presence of oxygen and moisture",
    prior=0.80,
)

market_requirements_approach = claim(
    "Achieving >10,000 hours stability approaches the market requirement of <10% drop "
    "in PCE for at least 1,000 hours on standard accelerated aging tests",
    prior=0.65,
)

# --- Internal reasoning ---
support(
    [two_d_water_resistant, gradual_interface],
    two_d_three_d_interface,
    reason="Combining water-resistant 2D perovskite with panchromatic 3D perovskite "
    "creates an interface that preserves both stability and efficiency",
    prior=0.492,
)

support(
    [two_d_three_d_interface, htmc_free_config],
    one_year_stability,
    reason="2D/3D interface protection combined with HTM-free carbon electrode "
    "eliminates major degradation pathways for ultra-long stability",
    prior=0.48,
)

support(
    [scalable_printable, one_year_stability],
    module_10x10_stable,
    reason="Printable industrial process combined with inherent material stability "
    "enables large-area modules with sustained performance",
    prior=0.468,
)

deduction(
    [module_10x10_stable, oxygen_moisture_tolerant],
    market_requirements_approach,
    reason="Large-area modules with >10,000 hour stability under real conditions "
    "approach the requirements for commercial deployment",
    prior=0.36,
)

# --- Connection to meta propositions ---
support(
    [one_year_stability, module_10x10_stable],
    p_stability,
    reason="One-year stable operation of 10x10 cm2 modules with zero efficiency loss "
    "demonstrates practical deployment stability",
    prior=0.42,
)

support(
    [scalable_printable, module_10x10_stable],
    p_industrialization,
    reason="Fully printable industrial-scale fabrication of 10x10 cm2 modules with "
    "stable 11.2% efficiency demonstrates manufacturing scalability",
    prior=0.39,
)

support(
    [two_d_three_d_interface, carbon_cell_12_9_pct],
    p_improvement,
    reason="2D/3D interface engineering is a novel approach that enables simultaneous "
    "efficiency and stability improvement through structural design",
    prior=0.36,
)

__all__ = [
    "htmc_free_config",
    "two_d_three_d_interface",
    "one_year_stability",
    "carbon_cell_12_9_pct",
    "module_10x10_stable",
    "two_d_water_resistant",
    "gradual_interface",
    "scalable_printable",
    "oxygen_moisture_tolerant",
    "market_requirements_approach",
]
