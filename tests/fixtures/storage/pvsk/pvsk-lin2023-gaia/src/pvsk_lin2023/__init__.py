"""Lin et al. Nature 2023 — All-perovskite tandem solar cells with 3D/3D
bilayer perovskite heterojunction achieving 28.5% PCE (certified 28.0%)."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "All-perovskite tandem solar cells with WBG (~1.78 eV) FA0.8Cs0.2Pb"
    "(I0.62Br0.38)3 top cell and NBG (~1.25 eV) Pb-Sn perovskite bottom "
    "cell. Device area 0.049 cm2 (small) and 1.05 cm2 (large). SAM-modified "
    "NiO HTL for WBG subcell. Encapsulated devices tested under simulated "
    "AM 1.5G at ambient conditions."
)

nbg_challenge = setting(
    "Mixed Pb-Sn narrow-bandgap perovskite subcells constrain all-perovskite "
    "tandem performance due to high trap density at the film surface. "
    "Conventional 2D/3D heterojunctions reduce surface recombination but "
    "induce transport losses that limit device fill factors."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
phj_concept = claim(
    "An immiscible 3D/3D bilayer perovskite heterojunction (PHJ) with type-II "
    "band structure at the Pb-Sn perovskite/ETL interface can simultaneously "
    "suppress interfacial non-radiative recombination and facilitate charge "
    "extraction without transport losses from 2D interlayers",
    title="phj_3d_3d_bilayer_concept",
    prior=0.85,
)

nbg_pce_238 = claim(
    "The 3D/3D bilayer PHJ enables Pb-Sn PSCs with 1.2 um absorber to reach "
    "23.8% PCE with Voc of 0.873 V and FF of 82.6%, substantially higher "
    "than the 21.0% control",
    title="nbg_pce_23_8_percent",
    prior=0.88,
)

tandem_pce_285 = claim(
    "All-perovskite tandem solar cells with PHJ in the NBG subcell achieve a "
    "record PCE of 28.5% (certified stabilized 28.0% by JET) with Voc of "
    "2.112 V, Jsc of 16.5 mA cm-2, and FF of 81.9%",
    title="tandem_pce_28_5_percent",
    prior=0.90,
)

hybrid_deposition = claim(
    "A hybrid evaporation-solution processing method enables non-destructive "
    "deposition of a 50 nm Pb-halide wide-bandgap perovskite (FA0.7Cs0.3Pb"
    "(I0.85Br0.14)3) on top of the Pb-Sn NBG perovskite, forming a clearly "
    "defined 3D/3D bilayer heterostructure with limited metal-ion intermixing",
    title="hybrid_deposition_phj",
    prior=0.82,
)

type_ii_band = claim(
    "The PHJ creates type-II band alignment between Pb-Sn NBG and FL-WBG "
    "perovskites that reduces hole concentration near the defective interface "
    "layer and facilitates electron extraction into C60, confirmed by "
    "ultrafast TA spectroscopy showing charge transfer from Pb-Sn to FL-WBG",
    title="type_ii_band_alignment",
    prior=0.82,
)

elqy_improvement = claim(
    "PHJ devices show electroluminescence quantum yield of 3.09% versus "
    "0.47% for controls at 1-sun current density, corresponding to Voc loss "
    "reduction from 147 mV to 97 mV",
    title="elqy_improvement_phj",
    prior=0.85,
)

phj_structural_stability = claim(
    "The 3D/3D PHJ retains its distinct heterostructure with no evidence of "
    "Sn diffusion into the FL-WBG layer after 60 days of storage in N2 "
    "glovebox, confirmed by EDX and ToF-SIMS",
    title="phj_structural_stability",
    prior=0.80,
)

tandem_operational_stability = claim(
    "Encapsulated tandem devices with PHJ retain over 90% of initial "
    "performance after 600 hours of continuous MPP tracking under simulated "
    "1-sun illumination",
    title="tandem_operational_stability_600h",
    prior=0.82,
)

large_area_tandem_269 = claim(
    "Large-area all-perovskite tandem devices (1.05 cm2) achieve 26.9% PCE "
    "with Voc of 2.149 V, Jsc of 15.7 mA cm-2, and FF of 79.8%",
    title="large_area_tandem_26_9_percent",
    prior=0.82,
)

voc_ff_improvement = claim(
    "PHJ in the NBG subcell improves average Voc by 45 mV (0.824 to 0.869 V) "
    "and FF by 2.3% (78.5% to 80.8%) compared with controls, while Jsc "
    "remains similar",
    title="voc_ff_improvement_phj",
    prior=0.85,
)

tandem_ff_improvement = claim(
    "PHJ tandems show substantially improved FF from 78.0% to 81.4% and PCE "
    "from 26.0% to 27.7% compared with control tandems, because the tandem "
    "FF is limited by the subpar NBG subcell under current matching",
    title="tandem_ff_improvement_phj",
    prior=0.82,
)

beyond_30_outlook = claim(
    "Combining optical and electrical loss reductions, an all-perovskite "
    "tandem PCE higher than 30% is achievable by empirically assuming "
    "Voc of 2.2 V, Jsc of 17 mA cm-2, and FF of 82%",
    title="beyond_30_percent_outlook",
    prior=0.50,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [hybrid_deposition, type_ii_band],
    phj_concept,
    reason="The hybrid deposition method creates a sharp 3D/3D interface, "
    "and the type-II band alignment enables charge separation without the "
    "transport losses inherent in 2D interlayers",
    prior=0.48,
)

support(
    [phj_concept, elqy_improvement, voc_ff_improvement],
    nbg_pce_238,
    reason="Type-II band alignment suppresses non-radiative recombination "
    "(3x higher ELQY, 50 mV Voc gain) while maintaining efficient charge "
    "transport (82.6% FF), yielding record NBG single-junction efficiency",
    prior=0.48,
)

support(
    [nbg_pce_238, tandem_ff_improvement],
    tandem_pce_285,
    reason="Improved NBG subcell FF and Voc directly enhance tandem FF and "
    "Voc under current matching, achieving record all-perovskite tandem "
    "efficiency",
    prior=0.48,
)

support(
    [phj_structural_stability],
    tandem_operational_stability,
    reason="Structural stability of the PHJ prevents degradation of the "
    "heterojunction during operation",
    prior=0.39,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [tandem_pce_285, large_area_tandem_269],
    p_efficiency,
    reason="Record 28.5% PCE for all-perovskite tandems surpasses best "
    "single-junction PSC records, demonstrating the efficiency advantage of "
    "the tandem approach",
    prior=0.48,
)

support(
    [tandem_pce_285, beyond_30_outlook],
    p_improvement,
    reason="Progression from previous all-perovskite tandem records "
    "(24.8%) to 28.5% shows rapid improvement, with clear pathway to >30%",
    prior=0.45,
)

support(
    [tandem_operational_stability],
    p_stability,
    reason="90% retention after 600 hours of MPP tracking demonstrates "
    "improving operational stability of all-perovskite tandems",
    prior=0.36,
)

support(
    [tandem_pce_285],
    p_viability,
    reason="All-perovskite tandems combine high efficiency with low-cost "
    "solution processing, offering a viable path to next-generation PV",
    prior=0.39,
)

__all__ = [
    "exp_context",
    "nbg_challenge",
    "phj_concept",
    "nbg_pce_238",
    "tandem_pce_285",
    "hybrid_deposition",
    "type_ii_band",
    "elqy_improvement",
    "phj_structural_stability",
    "tandem_operational_stability",
    "large_area_tandem_269",
    "voc_ff_improvement",
    "tandem_ff_improvement",
    "beyond_30_outlook",
]
