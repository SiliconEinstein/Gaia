"""Zhao et al. Science 2022 — Accelerated aging of all-inorganic, interface-stabilized
perovskite solar cells. 2D Cs2PbI2Cl2 capping on CsPbI3 stabilizes the perovskite/HTL
interface, boosting PCE from 14.9% to 17.4% (highest for all-inorganic PSCs), with
Arrhenius-based extrapolation predicting T80 lifetime >5 years at 35C under illumination."""

from gaia.lang import claim, setting, question, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "All-inorganic CsPbI3 perovskite solar cells with FTO/TiO2/Al2O3/CsPbI3/2D Cs2PbI2Cl2/"
    "CuSCN/Cr/Au structure, with and without 2D Cs2PbI2Cl2 capping layer between the "
    "perovskite and CuSCN hole transport layer, encapsulated in N2 atmosphere for "
    "accelerated aging at 35-110C under constant 1-sun illumination at maximum power point"
)

cs2pbi2cl2_capping = claim(
    "2D Cs2PbI2Cl2 capping layer (~20 nm thick) deposited on CsPbI3 surface by treating "
    "with CsCl solution followed by thermal annealing; this fully inorganic 2D layer "
    "avoids the cation exchange problem that prevents organic 2D layers from forming on "
    "CsPbI3 due to stronger Cs+ binding compared to MA+ or FA+",
    prior=0.70,
)

arrhenius_accelerated_aging = claim(
    "Accelerated aging methodology using elevated temperatures (35, 59, 85, 110C) to "
    "quantify degradation rates under constant illumination at MPP, with Arrhenius "
    "temperature dependence of degradation rates yielding acceleration factors for "
    "lifetime extrapolation to standard operating conditions (1 sun, 35C)",
    prior=0.70,
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
capped_pce_17_4_pct = claim(
    "Capped CsPbI3 PSCs with 2D Cs2PbI2Cl2 layer achieve champion PCE of 17.4%, the "
    "highest among fully inorganic PSCs where all functional materials in the stack are "
    "inorganic, compared to 14.9% for uncapped devices",
    prior=0.90,
)

voc_and_ff_improvement = claim(
    "The 2D capping layer increases both Voc and FF in capped PSCs relative to uncapped "
    "devices, consistent with surface passivation reducing nonradiative recombination "
    "losses at the perovskite/HTL interface",
    prior=0.87,
)

trpl_lifetime_increase = claim(
    "Time-resolved photoluminescence shows the carrier lifetime increases from 14 ns "
    "(uncapped) to >62 ns (capped), indicating effective suppression of nonradiative "
    "recombination at the CsPbI3 surface and extended carrier diffusion length",
    prior=0.88,
)

no_degradation_at_35c = claim(
    "Capped PSCs show no noticeable PCE degradation after 3531 hours of continuous "
    "operation at 35C under constant 1-sun illumination at MPP in (65+/-26)% RH air",
    prior=0.92,
)

t80_2100h_at_110c = claim(
    "Capped PSCs exhibit T80 lifetime (time to 80% of initial PCE) of >2100 hours at "
    "110C under constant 1-sun illumination, while uncapped devices degrade substantially "
    "faster at all elevated temperatures",
    prior=0.90,
)

extrapolated_t80_5_years = claim(
    "Using experimentally determined acceleration factor of 24.2+/-3.5 for 110C operation, "
    "the extrapolated T80 lifetime for capped devices at 35C is 51,000+/-7,000 hours "
    "(>5 years) of continuous operation under illumination",
    prior=0.85,
)

single_degradation_mechanism = claim(
    "Degradation rates across the entire 35-110C temperature range can be described by a "
    "single Arrhenius function, confirming the same degradation mechanism dominates at all "
    "temperatures — a critical criterion for reliable accelerated aging tests",
    prior=0.88,
)

activation_energy_doubled = claim(
    "The activation energy for degradation (Ea) of capped PSCs is nearly twice that of "
    "uncapped PSCs, indicating that the 2D Cs2PbI2Cl2 layer substantially stabilizes the "
    "devices against thermal degradation",
    prior=0.87,
)

ion_migration_suppressed = claim(
    "XRD and XPS analysis after aging at 110C shows iodine migration from CsPbI3 into "
    "CuSCN in uncapped devices (evidenced by CuSCN crystallite degradation and I 3d signal "
    "in HTL), while capped devices show no appreciable iodine migration or CuSCN "
    "structural changes",
    prior=0.88,
)

ion_migration_activation_doubled = claim(
    "The activation energy for ion migration (Ea,ion) in capped films is nearly twice that "
    "of uncapped films as measured by temperature-dependent conductivity, indicating the "
    "2D cap frustrates ion migration by passivating iodine vacancies at the perovskite "
    "surface",
    prior=0.86,
)

universal_degradation_curve = claim(
    "When aging data from all temperatures are converted to equivalent operating time at "
    "35C using the acceleration factor, all data collapse onto a universal degradation "
    "curve for both capped and uncapped devices, confirming a single mechanism across "
    "temperatures",
    prior=0.87,
)

biexponential_degradation = claim(
    "PCE degradation at all temperatures follows a biexponential function with fast and "
    "slow decay rates; the fast and slow degradation activation energies are comparable "
    "within each device type, suggesting both rates probe a single physical process "
    "(ion migration)",
    prior=0.85,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
organic_psc_accelerated_aging = question(
    "Can this Arrhenius-based accelerated aging methodology with experimentally determined "
    "acceleration factors be applied to organic-inorganic hybrid perovskite compositions "
    "such as FAPbI3 and MAPbI3, which may have additional degradation pathways from "
    "organic cation volatility?"
)

ion_migration_suppression_mechanism = question(
    "Does the 2D Cs2PbI2Cl2 capping layer suppress ion migration primarily by passivating "
    "iodine vacancies at the CsPbI3 surface, or does it also create an energetic barrier "
    "to ion transport across the perovskite/HTL interface?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [trpl_lifetime_increase],
    voc_and_ff_improvement,
    reason="Suppressed surface nonradiative recombination (14 to >62 ns lifetime) directly "
    "increases Voc by reducing the dark saturation current and improves FF by reducing "
    "recombination losses at forward bias",
    prior=0.492,
)

support(
    [voc_and_ff_improvement],
    capped_pce_17_4_pct,
    reason="The simultaneous improvement in Voc and FF from 2D surface passivation, while "
    "maintaining Jsc, increases the PCE from 14.9% to 17.4%, the record for all-inorganic "
    "PSCs",
    prior=0.498,
)

support(
    [ion_migration_suppressed, ion_migration_activation_doubled],
    t80_2100h_at_110c,
    reason="The 2D Cs2PbI2Cl2 layer blocks iodine migration into CuSCN (confirmed by XPS) "
    "and doubles the ion migration activation energy, dramatically slowing the dominant "
    "degradation mechanism at elevated temperatures",
    prior=0.498,
)

support(
    [single_degradation_mechanism, t80_2100h_at_110c],
    extrapolated_t80_5_years,
    reason="A single Arrhenius degradation mechanism across 35-110C validates using the "
    "acceleration factor (24.2+/-3.5 at 110C) to reliably extrapolate T80 from the "
    "experimentally measured 2100 hours at 110C to 51,000+/-7,000 hours at 35C",
    prior=0.48,
)

support(
    [ion_migration_suppressed],
    activation_energy_doubled,
    reason="The 2D Cs2PbI2Cl2 layer passivates iodine vacancies at the CsPbI3 surface, "
    "reducing the concentration of mobile ions and raising the energy barrier for ion "
    "migration, which doubles both the degradation activation energy and the ion migration "
    "activation energy",
    prior=0.492,
)

support(
    [single_degradation_mechanism, biexponential_degradation],
    universal_degradation_curve,
    reason="Comparable fast and slow activation energies within each device type indicate "
    "both rates probe the same physical process (ion migration), so the Arrhenius "
    "extrapolation is valid and data collapse onto a universal curve",
    prior=0.48,
)

support(
    [ion_migration_suppressed],
    no_degradation_at_35c,
    reason="At 35C the thermal energy is insufficient to overcome the doubled ion migration "
    "activation energy barrier created by the 2D capping layer, so no degradation is "
    "observable within 3531 hours",
    prior=0.468,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [capped_pce_17_4_pct, extrapolated_t80_5_years],
    p_stability,
    reason="Arrhenius-validated prediction of >5 year continuous operational lifetime at "
    "35C with a quantitative acceleration factor provides the most rigorous stability "
    "assessment for PSCs to date, directly supporting the feasibility of long-term "
    "deployment",
    prior=0.45,
)

support(
    [capped_pce_17_4_pct],
    p_efficiency,
    reason="17.4% PCE is the highest for all-inorganic PSCs with fully inorganic device "
    "stacks, demonstrating that eliminating volatile organic cations does not preclude "
    "competitive efficiency",
    prior=0.372,
)

support(
    [cs2pbi2cl2_capping, activation_energy_doubled, ion_migration_suppressed],
    p_improvement,
    reason="All-inorganic 2D capping layers that double the ion migration activation energy "
    "represent a new interface engineering strategy combining surface passivation with "
    "ion migration suppression for continuous stability improvement",
    prior=0.408,
)

support(
    [extrapolated_t80_5_years, no_degradation_at_35c],
    p_viability,
    reason="All-inorganic CsPbI3 with no observable degradation at 35C over 3531 hours "
    "and >5 year predicted lifetime demonstrates that PSCs can achieve the durability "
    "required for practical applications",
    prior=0.39,
)

support(
    [arrhenius_accelerated_aging, universal_degradation_curve],
    p_industrialization,
    reason="The Arrhenius-based accelerated aging methodology with validated acceleration "
    "factors provides a quantitative framework for industrial lifetime certification, "
    "analogous to methods used for silicon and organic PV modules",
    prior=0.39,
)

__all__ = [
    "exp_context",
    "cs2pbi2cl2_capping",
    "arrhenius_accelerated_aging",
    "capped_pce_17_4_pct",
    "voc_and_ff_improvement",
    "trpl_lifetime_increase",
    "no_degradation_at_35c",
    "t80_2100h_at_110c",
    "extrapolated_t80_5_years",
    "single_degradation_mechanism",
    "activation_energy_doubled",
    "ion_migration_suppressed",
    "ion_migration_activation_doubled",
    "universal_degradation_curve",
    "biexponential_degradation",
    "organic_psc_accelerated_aging",
    "ion_migration_suppression_mechanism",
]
