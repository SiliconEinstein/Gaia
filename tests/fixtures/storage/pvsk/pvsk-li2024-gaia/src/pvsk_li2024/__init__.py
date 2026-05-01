"""Li et al. Nat Energy 2024 — Homogeneous coverage of low-dimensional
perovskite passivation layer for formamidinium-caesium perovskite solar
modules, achieving 23.6% mini-module and 17.6% fully printed 802 cm2 module."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "FA-dominated perovskite (FA0.93Cs0.07PbI3) with antisolvent-free "
    "deposition. Module structure: glass/FTO/SnO2/perovskite/passivator/"
    "spiro-OMeTAD/Au. Small devices (0.14 cm2), large devices (1.04 cm2), "
    "mini-modules (13.44 cm2), and fully slot-die printed large modules "
    "(310 cm2 and 802 cm2)."
)

phase_problem = setting(
    "Phase separation occurs in double-halide alloyed 2D perovskites with "
    "long-chain (>10) alkylamine ligands, producing uneven n-value "
    "distribution on 3D perovskite surfaces. This energy disorder "
    "deteriorates interfacial charge transport in large-area modules."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
phase_separation_discovery = claim(
    "Long-chain alkylamine ligands (>10 carbons) cause phase separation in "
    "double-halide alloyed 2D perovskites, while triple-halide compositions "
    "successfully eliminate the problematic phase separation",
    title="phase_separation_discovery",
    prior=0.85,
)

homogeneous_2d_passivation = claim(
    "Incorporating formamidinium bromide (FABr) into n-dodecylammonium halide "
    "(DAX) post-treatment enables growth of phase-pure n=2 2D perovskite "
    "capping layer with homogeneous morphology on 3D perovskite surfaces",
    title="homogeneous_2d_passivation",
    prior=0.85,
)

small_cell_2561 = claim(
    "Champion active-area efficiency of 25.61% for 0.14 cm2 small devices "
    "using the DABr/FABr homogeneous 2D passivation strategy with "
    "antisolvent-free processing",
    title="small_cell_25_61_percent",
    prior=0.87,
)

large_cell_2462 = claim(
    "Champion active-area efficiency of 24.62% for 1.04 cm2 large devices, "
    "demonstrating less than 5% efficiency loss per ten times magnification",
    title="large_cell_24_62_percent",
    prior=0.85,
)

mini_module_2360 = claim(
    "Champion active-area efficiency of 23.60% for 13.44 cm2 mini-modules, "
    "maintaining the small efficiency loss scaling trend",
    title="mini_module_23_60_percent",
    prior=0.85,
)

printed_module_310 = claim(
    "Fully slot-die printed large modules achieve champion aperture-area "
    "efficiency of 18.90% for 20 cm x 20 cm modules (310 cm2 aperture area)",
    title="printed_module_310_cm2",
    prior=0.85,
)

printed_module_802 = claim(
    "Fully slot-die printed modules achieve champion aperture-area efficiency "
    "of 17.59% for 30 cm x 30 cm modules (802 cm2 aperture area), "
    "demonstrating the feasibility of upscaling manufacturing",
    title="printed_module_802_cm2",
    prior=0.85,
)

module_mppt_stability = claim(
    "Encapsulated mini-modules exhibit remarkable operational stability with "
    "T80 lifetime exceeding 2000 hours at MPPT under continuous light "
    "illumination",
    title="module_mppt_t80_2000h",
    prior=0.82,
)

triple_halide_mechanism = claim(
    "Triple-halide compositions (I/Br/Cl) have lower formation enthalpy than "
    "double-halide alloys for n=2 2D perovskite, enabling preferential "
    "formation of phase-pure n=2 structure confirmed by in situ PL and "
    "GIWAXS",
    title="triple_halide_mechanism",
    prior=0.80,
)

fabr_accelerated_growth = claim(
    "FABr addition accelerates the formation of n=2 2D perovskite, appearing "
    "at 33 seconds during spin coating versus 40 seconds for DABr alone, "
    "enabling homogeneous coverage even at room temperature",
    title="fabr_accelerated_growth",
    prior=0.78,
)

universal_ligand = claim(
    "The FABr-assisted homogeneous passivation strategy is universal, "
    "successfully suppressing phase separation for most conventional 2D "
    "ligands including BA, OA, DA, PMA, PEA, and NMA",
    title="universal_ligand_strategy",
    prior=0.75,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [phase_separation_discovery, triple_halide_mechanism],
    homogeneous_2d_passivation,
    reason="Understanding that triple-halide compositions eliminate phase "
    "separation and that FABr lowers formation enthalpy for n=2 structure "
    "enables rational design of homogeneous 2D capping layers",
    prior=0.48,
)

support(
    [homogeneous_2d_passivation, fabr_accelerated_growth],
    small_cell_2561,
    reason="Phase-pure n=2 2D passivation provides superior defect passivation "
    "and charge transport compared to mixed-phase 2D layers",
    prior=0.468,
)

support(
    [small_cell_2561, homogeneous_2d_passivation],
    mini_module_2360,
    reason="Homogeneous passivation coverage is critical for large-area "
    "devices where uneven passivation causes local losses that scale with area",
    prior=0.468,
)

support(
    [homogeneous_2d_passivation, universal_ligand],
    printed_module_802,
    reason="The strategy is compatible with slot-die printing, enabling "
    "fabrication of 802 cm2 modules with good efficiency",
    prior=0.432,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [printed_module_802, printed_module_310],
    p_industrialization,
    reason="Fully slot-die printed 30x30 cm modules at 17.59% efficiency "
    "demonstrate industrial-scale manufacturing capability for perovskite "
    "solar modules",
    prior=0.48,
)

support(
    [mini_module_2360, large_cell_2462, small_cell_2561],
    p_efficiency,
    reason="Systematic scaling from 25.61% (0.14 cm2) to 23.60% (13.44 cm2) "
    "with less than 5% loss per 10x area increase demonstrates efficient "
    "module technology",
    prior=0.45,
)

support(
    [module_mppt_stability],
    p_stability,
    reason="T80 lifetime exceeding 2000 hours at MPPT demonstrates "
    "module-level stability suitable for practical deployment",
    prior=0.42,
)

support(
    [printed_module_802, mini_module_2360],
    p_improvement,
    reason="Printed module efficiencies reaching 17-19% for large areas "
    "show continuous improvement in scalable manufacturing quality",
    prior=0.42,
)

__all__ = [
    "exp_context",
    "phase_problem",
    "phase_separation_discovery",
    "homogeneous_2d_passivation",
    "small_cell_2561",
    "large_cell_2462",
    "mini_module_2360",
    "printed_module_310",
    "printed_module_802",
    "module_mppt_stability",
    "triple_halide_mechanism",
    "fabr_accelerated_growth",
    "universal_ligand",
]
