"""Lin et al. (Park et al.) Nature 2021/2022 — All-perovskite tandem solar cells with
improved grain surface passivation. CF3-PA passivation of Pb-Sn narrow-bandgap subcells
enables certified 26.4% tandem PCE, exceeding the best single-junction perovskite cells."""
from gaia.lang import claim, setting, question, support, deduction, contradiction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = claim(
    "Monolithic all-perovskite tandem solar cells combining a wide-bandgap (~1.8 eV) "
    "mixed Br/I perovskite front cell with a narrow-bandgap (~1.2 eV) mixed Pb-Sn "
    "perovskite back cell, using CF3-PA (4-trifluoromethyl-phenylammonium) additive in "
    "the Pb-Sn precursor solution at 0.3 mol%"
,
    prior=0.70,
)

cf3_pa_passivator = setting(
    "4-trifluoromethyl-phenylammonium (CF3-PA) is an ammonium cation passivator where "
    "the highly electronegative fluorine atoms withdraw electron density from the "
    "aromatic ring, leaving higher electropositivity at the NH3+ side and enhancing "
    "binding with negatively charged defect sites on Pb-Sn perovskite surfaces"
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
tandem_26_4_certified = claim(
    "All-perovskite tandem solar cells achieve certified stabilized PCE of 26.4% "
    "(JET calibration), exceeding the best single-junction perovskite solar cell "
    "efficiency and comparable to the best single-crystalline silicon cells",
    prior=0.92,
)

tandem_26_7_best = claim(
    "The best tandem cell achieves PCE of 26.7% from reverse scan with Voc=2.03 V, "
    "Jsc=16.5 mA/cm2, and FF=79.9%, with stabilized PCE of 26.6%",
    prior=0.88,
)

cf3_pa_best_passivator = claim(
    "Among three passivators tested (PEA, PA, CF3-PA), CF3-PA produces the best Pb-Sn "
    "PSC performance across all PV parameters (Voc, Jsc, FF, PCE) with 1.2 um thick "
    "absorber layers",
    prior=0.87,
)

diffusion_length_5_um = claim(
    "CF3-PA passivation increases the carrier diffusion length in Pb-Sn perovskite "
    "films threefold from 1.8 um to 5.4 um, enabling 1.2 um thick absorber layers "
    "for high photocurrent density",
    prior=0.88,
)

pb_sn_psc_22_pct = claim(
    "CF3-PA passivated single-junction Pb-Sn PSCs with 1.2 um absorber achieve best "
    "PCE of 22.2% (stabilized 22.0%), with Voc=0.841 V, Jsc=33.0 mA/cm2, FF=80%, "
    "and average PCE of 20.8+/-0.5% across 237 devices",
    prior=0.88,
)

complete_surface_coverage = claim(
    "Ab initio molecular dynamics at 400 K show all 16 CF3-PA cations adsorb "
    "completely on the perovskite surface, compared to 15/16 for PA and 13/16 for PEA, "
    "indicating near-complete defect coverage during film formation",
    prior=0.82,
)

suppressed_iodine_vacancies = claim(
    "CF3-PA not only increases adsorption probability on perovskite surfaces but also "
    "suppresses iodide ion desorption at 400 K, reducing formation of both iodine "
    "vacancies and iodine interstitial defects",
    prior=0.80,
)

strongest_binding_energy = claim(
    "DFT calculations show CF3-PA has the strongest binding energy with acceptor-type "
    "defects (FA vacancy, Sn vacancy, I_Sn, I_Pb antisites) on Pb-Sn perovskite "
    "surfaces among all three passivators, and eliminates deep in-gap states from "
    "antisite defects",
    prior=0.82,
)

carrier_lifetime_966_ns = claim(
    "CF3-PA passivated Pb-Sn perovskite films exhibit effective carrier lifetime of "
    "966 ns, compared to 437 ns (PA), 365 ns (PEA), and 159 ns (control), as measured "
    "by time-resolved photoluminescence",
    prior=0.86,
)

no_2d_phase_formation = claim(
    "XRD patterns show that adding trace amounts of CF3-PA does not form 2D perovskite "
    "phases even at 20 mol% concentration, maintaining pure 3D perovskite structure "
    "beneficial for charge transport through thick absorber layers",
    prior=0.85,
)

sn_oxidation_suppressed = claim(
    "Angle-dependent XPS measurements confirm that CF3-PA passivation successfully "
    "suppresses surface Sn2+ oxidation in Pb-Sn perovskite films by passivating "
    "undercoordinated Sn atoms and Sn vacancies",
    prior=0.83,
)

large_area_25_3_pct = claim(
    "Large-area tandem device (aperture area 1.05 cm2) achieves PCE of 25.3% with "
    "Voc=2.03 V, Jsc=16 mA/cm2, FF=78%, demonstrating scalability",
    prior=0.85,
)

tandem_stability_90_pct_600h = claim(
    "Encapsulated CF3-PA tandem devices retain 90% of initial PCE after 600 h of "
    "continuous MPP tracking under 1-sun illumination in ambient air (30-50% humidity) "
    "at approximately 35C device temperature",
    prior=0.82,
)

thick_absorber_enables_high_jsc = claim(
    "Increasing Pb-Sn absorber thickness from 750 to 1200 nm with CF3-PA increases "
    "tandem Jsc from 15.4 to 16.5 mA/cm2 due to enhanced near-infrared light "
    "absorption in the back subcell",
    prior=0.85,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
tandem_long_term = question(
    "Can all-perovskite tandem solar cells achieve operational stability beyond 1000 "
    "hours under continuous illumination, and how does CF3-PA passivation affect "
    "long-term ion migration in the Pb-Sn subcell?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [complete_surface_coverage, strongest_binding_energy],
    cf3_pa_best_passivator,
    reason="CF3-PA achieves near-complete surface adsorption and strongest defect "
    "binding, eliminating more deep traps than PEA or PA, leading to the best "
    "passivation and device performance",
    prior=0.48,
)

support(
    [cf3_pa_best_passivator, carrier_lifetime_966_ns],
    diffusion_length_5_um,
    reason="CF3-PA passivation triples the carrier lifetime (159 to 966 ns) while "
    "maintaining similar carrier mobility (~80 cm2/V/s), directly increasing the "
    "diffusion length from 1.8 to 5.4 um",
    prior=0.492,
)

support(
    [diffusion_length_5_um, no_2d_phase_formation],
    thick_absorber_enables_high_jsc,
    reason="The tripling of diffusion length enables efficient charge extraction from "
    "1.2 um thick Pb-Sn absorbers without 2D phase barriers, allowing high NIR "
    "absorption and matched current density in tandem cells",
    prior=0.492,
)

support(
    [thick_absorber_enables_high_jsc, pb_sn_psc_22_pct],
    tandem_26_4_certified,
    reason="Thick NBG absorber with high Jsc (>16 mA/cm2) combined with efficient WBG "
    "front cell enables current matching and record tandem efficiency exceeding "
    "single-junction PSCs",
    prior=0.498,
)

support(
    [suppressed_iodine_vacancies, sn_oxidation_suppressed],
    tandem_stability_90_pct_600h,
    reason="Reduced defect density at grain surfaces suppresses ion migration and Sn "
    "oxidation pathways, leading to improved operational stability of tandem devices",
    prior=0.45,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [tandem_26_4_certified],
    p_efficiency,
    reason="Certified 26.4% tandem PCE exceeds the best single-junction perovskite and "
    "demonstrates the tandem architecture can surpass single-junction efficiency limits",
    prior=0.432,
)

support(
    [cf3_pa_best_passivator, diffusion_length_5_um],
    p_improvement,
    reason="Rational molecular design of passivators guided by ab initio molecular "
    "dynamics enables systematic improvement of perovskite material properties",
    prior=0.39,
)

support(
    [tandem_stability_90_pct_600h],
    p_stability,
    reason="Encapsulated tandem devices retaining 90% PCE after 600 h under ambient "
    "conditions show progress toward practical operational stability",
    prior=0.36,
)

support(
    [tandem_26_4_certified, large_area_25_3_pct],
    p_viability,
    reason="All-perovskite tandems with record efficiency and scalable large-area "
    "fabrication demonstrate a viable pathway beyond single-junction limits",
    prior=0.39,
)

support(
    [large_area_25_3_pct, exp_context],
    p_industrialization,
    reason="Solution-processed tandem cells exceeding 25% on >1 cm2 area with narrow "
    "efficiency distribution show promise for scalable manufacturing",
    prior=0.348,
)

__all__ = [
    "exp_context",
    "cf3_pa_passivator",
    "tandem_26_4_certified",
    "tandem_26_7_best",
    "cf3_pa_best_passivator",
    "diffusion_length_5_um",
    "pb_sn_psc_22_pct",
    "complete_surface_coverage",
    "suppressed_iodine_vacancies",
    "strongest_binding_energy",
    "carrier_lifetime_966_ns",
    "no_2d_phase_formation",
    "sn_oxidation_suppressed",
    "large_area_25_3_pct",
    "tandem_stability_90_pct_600h",
    "thick_absorber_enables_high_jsc",
    "tandem_long_term",
]
