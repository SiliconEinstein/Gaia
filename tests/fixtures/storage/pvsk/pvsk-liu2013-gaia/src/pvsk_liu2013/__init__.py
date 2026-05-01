"""Liu et al. Nature 2013 — First vapour-deposited planar heterojunction perovskite
solar cell. Dual-source thermal evaporation of CH3NH3PbI3-xClx achieves certified 15.4%
PCE, proving nanostructuring is not necessary for high efficiency."""

from gaia.lang import claim, setting, question, support, deduction, contradiction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Planar heterojunction p-i-n solar cell with dual-source vapour-deposited "
    "CH3NH3PbI3-xClx perovskite: CH3NH3I and PbCl2 evaporated simultaneously at "
    "4:1 molar ratio under 10^-5 mbar onto compact TiO2/FTO substrate, annealed "
    "at 100C for 45 min, followed by solution-processed spiro-OMeTAD and evaporated "
    "Ag electrode, measured under AM 1.5 at 101 mW/cm2"
)

vapour_deposition_method = claim(
    "Dual-source thermal evaporation: CH3NH3I at ~116C (5.3 A/s) and PbCl2 at ~320C "
    "(1 A/s) for ~128 min, producing ~330 nm thick perovskite film after annealing. "
    "Substrate holder rotated and water-cooled to ~21C for uniform coating"
,
    prior=0.70,
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_15_4_pct = claim(
    "Best vapour-deposited planar heterojunction perovskite cell achieves PCE of "
    "15.4% with Jsc=21.5 mA/cm2, Voc=1.07 V, and fill factor 0.67, measured under "
    "AM 1.5 simulated sunlight at 101 mW/cm2",
    prior=0.92,
)

batch_average_12_3 = claim(
    "Average performance of 12 identically processed vapour-deposited cells is "
    "PCE=12.3% +/- 2.0%, Jsc=18.9 +/- 1.8 mA/cm2, Voc=1.05 +/- 0.03 V, "
    "FF=0.62 +/- 0.05",
    prior=0.90,
)

nanostructure_not_necessary = claim(
    "Nanostructuring (mesoporous scaffold) is not necessary to achieve high "
    "efficiency with perovskite absorbers; a simple planar heterojunction thin-film "
    "architecture can deliver over 15% PCE",
    prior=0.90,
)

vapour_film_uniformity = claim(
    "Vapour-deposited perovskite films are extremely uniform with crystalline features "
    "on the scale of hundreds of nanometres, in contrast to solution-processed films "
    "with partial coverage and crystalline platelets tens of micrometres in size",
    prior=0.90,
)

solution_planar_8_6_pct = claim(
    "Solution-processed planar heterojunction perovskite cell achieves 8.6% PCE with "
    "Jsc=17.6 mA/cm2, Voc=0.84 V, and FF=0.58, but with undulating film (50-410 nm "
    "thickness variation) and pinholes causing shunting paths",
    prior=0.87,
)

phase_purity = claim(
    "Vapour-deposited perovskite films show high phase purity with only minor PbI2 "
    "(12.65 degrees) and no measurable CH3NH3PbCl3 (15.68 degrees) XRD peaks, "
    "confirming well-formed mixed-halide perovskite",
    prior=0.87,
)

diffusion_length_lower_bound = claim(
    "The electron and hole diffusion length in CH3NH3PbI3-xClx perovskite is at "
    "least 330 nm (the film thickness), as evidenced by efficient charge collection "
    "in planar heterojunction cells",
    prior=0.85,
)

same_crystal_structure = claim(
    "Both vapour-deposited and solution-cast films produce the same mixed-halide "
    "perovskite with orthorhombic crystal structure, as confirmed by identical XRD "
    "peak positions at 14.12, 28.44, and 43.23 degrees",
    prior=0.88,
)

tandem_compatibility = claim(
    "Vapour-deposited perovskite technology is compatible with conventional silicon "
    "and CIGS processing, making it suitable as a top cell in hybrid tandem "
    "configurations",
    prior=0.65,
)

cl_apical_position = claim(
    "Cl atoms in the mixed-halide perovskite reside in apical positions out of the "
    "PbI4 plane rather than in equatorial octahedral sites, consistent with a slight "
    "contraction of the c-axis compared to CH3NH3PbI3",
    prior=0.72,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
diffusion_length_precise = question(
    "What are the precise electron and hole diffusion lengths in vapour-deposited "
    "CH3NH3PbI3-xClx, and what are the primary excitation and free-charge generation "
    "mechanisms?"
)

manufacturing_route = question(
    "Will vapour deposition emerge as the preferred route for perovskite solar cell "
    "manufacture, or will solution processing eventually match its film quality?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
deduction(
    [vapour_film_uniformity],
    pce_15_4_pct,
    reason="Extremely uniform vapour-deposited films eliminate pinholes and shunting "
    "paths, enabling high Voc (1.07 V) and fill factor (0.67)",
    prior=0.492,
)

support(
    [phase_purity, same_crystal_structure],
    pce_15_4_pct,
    reason="High phase purity and identical crystal structure to solution-processed "
    "perovskite confirm that vapour deposition produces the correct material with "
    "superior morphology",
    prior=0.468,
)

support(
    [pce_15_4_pct, batch_average_12_3],
    nanostructure_not_necessary,
    reason="15.4% PCE in a simple planar architecture without mesoporous scaffold "
    "proves that nanostructuring is not essential for high efficiency",
    prior=0.51,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_15_4_pct, nanostructure_not_necessary],
    p_efficiency,
    reason="15.4% PCE in a simplified planar architecture demonstrates efficiency "
    "competitive with established thin-film technologies",
    prior=0.39,
)

support(
    [pce_15_4_pct, nanostructure_not_necessary],
    p_viability,
    reason="Planar thin-film architecture is the simplest possible photovoltaic "
    "device structure, confirming perovskite as a fundamentally viable absorber",
    prior=0.39,
)

support(
    [pce_15_4_pct, batch_average_12_3],
    p_improvement,
    reason="Matching the 15% of Burschka 2013 mesoscopic cells with a planar "
    "architecture shows continued rapid progress through deposition method innovation",
    prior=0.36,
)

support(
    [tandem_compatibility, vapour_deposition_method],
    p_industrialization,
    reason="Vapour deposition is a mature technique in the glazing, LCD, and "
    "thin-film solar cell industries, making scale-up feasible with existing "
    "infrastructure",
    prior=0.36,
)

support(
    [diffusion_length_lower_bound],
    p_stability,
    reason="Long carrier diffusion lengths suggest robust electronic properties "
    "that could support stable operation",
    prior=0.3,
)

# ---------------------------------------------------------------------------
# Cross-paper: comparison with Burschka 2013 and Lee 2012
# ---------------------------------------------------------------------------
contradiction(
    solution_planar_8_6_pct,
    pce_15_4_pct,
    reason="Same planar architecture but solution processing yields 8.6% vs "
    "vapour deposition 15.4%, highlighting the critical role of film uniformity",
    prior=0.75,
)

__all__ = [
    "exp_context",
    "vapour_deposition_method",
    "pce_15_4_pct",
    "batch_average_12_3",
    "nanostructure_not_necessary",
    "vapour_film_uniformity",
    "solution_planar_8_6_pct",
    "phase_purity",
    "diffusion_length_lower_bound",
    "same_crystal_structure",
    "tandem_compatibility",
    "cl_apical_position",
    "diffusion_length_precise",
    "manufacturing_route",
]
