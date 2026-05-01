"""Jeong et al. Nature 2021 — Pseudo-halide anion engineering for alpha-FAPbI3
perovskite solar cells. Formate (HCOO-) anion passivation of iodide vacancies yields
25.6% PCE (certified 25.2%) with improved stability."""
from gaia.lang import claim, setting, question, support, deduction, contradiction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = claim(
    "FAPbI3 perovskite solar cells fabricated on mesoporous TiO2/FTO substrates using "
    "anti-solvent method with 2 mol% formamidinium formate (FAHCOO) added to the "
    "FAPbI3 precursor solution, 35 mol% MACl additive, Spiro-OMeTAD hole transport "
    "layer, Au electrode, measured under AM 1.5G at 100 mW/cm2"
,
    prior=0.70,
)

formate_passivation = claim(
    "Pseudo-halide formate anion (HCOO-) introduced via formamidinium formate (FAHCOO) "
    "into FAPbI3 precursor at 1-4 mol%; formate does not substitute iodide in the "
    "perovskite lattice but passivates surface iodide vacancy defects at grain boundaries"
,
    prior=0.70,
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_25_6_pct = claim(
    "FAPbI3 PSC with 2% formate additive achieves maximum PCE of 25.59% with "
    "Jsc=26.35 mA/cm2, Voc=1.189 V, and fill factor 81.7%, under reverse scan",
    prior=0.90,
)

certified_25_2_pct = claim(
    "Target FAPbI3 PSC certified at Newport with quasi-steady-state PCE of 25.21%, "
    "Voc=1.174 V, Jsc=26.25 mA/cm2, fill factor 81.8%",
    prior=0.92,
)

voc_96_pct_sql = claim(
    "The Voc of 1.21 V achieved in the formate-treated cell represents 96% of the "
    "Shockley-Queisser limit of 1.25 V for FAPbI3, the highest Voc ratio yet obtained",
    prior=0.88,
)

fivefold_el_reduction = claim(
    "Formate treatment results in a fivefold reduction in non-radiative recombination "
    "rate, with EQE_EL increasing from 2.2% (reference) to 10.1% (target) at "
    "injection current density corresponding to 1-sun Jsc",
    prior=0.88,
)

ideality_factor_reduction = claim(
    "The ideality factor (n_id) of the formate-treated cell is 1.18, lower than the "
    "reference cell value of 1.52 and the previously reported best of 1.27, indicating "
    "reduced trap-assisted recombination",
    prior=0.85,
)

formate_not_in_lattice = claim(
    "Solid-state NMR (207Pb and 13C) measurements confirm that HCOO- anions do not "
    "substitute for iodide in the alpha-FAPbI3 lattice; the 207Pb resonance remains "
    "unchanged at 1543 ppm even with 5% FAHCOO addition",
    prior=0.90,
)

formate_passivates_vacancies = claim(
    "HCOO- anions passivate iodide vacancy defects at grain surfaces and boundaries "
    "by binding to undercoordinated Pb2+ sites, with the highest binding energy among "
    "all tested anions (Cl-, Br-, I-, BF4-) at I-vacant sites",
    prior=0.87,
)

formate_enhances_crystallinity = claim(
    "Adding 2% FAHCOO strongly enhances the crystallinity of alpha-FAPbI3 films, "
    "eliminating the delta-phase under high humidity (100% RH, 30C) and reducing "
    "XRD peak full-width at half-maximum",
    prior=0.85,
)

shelf_life_improvement = claim(
    "Unencapsulated formate-treated PSCs show only 10% PCE degradation after 1000 h "
    "shelf-life storage in the dark at 25C and 20% RH, compared to 35% degradation "
    "for the reference cell",
    prior=0.83,
)

thermal_stability_improvement = claim(
    "Target PSC retains approximately 80% of initial efficiency after 1000 h annealing "
    "at 60C under 20% RH, compared to only 40% for the reference cell",
    prior=0.83,
)

operational_stability_improvement = claim(
    "Under continuous 1-sun MPP tracking in N2 atmosphere, the target cell loses only "
    "~15% of initial efficiency over 450 h while the reference cell loses ~30%, "
    "measured at approximately 35C device temperature without active cooling",
    prior=0.82,
)

carrier_lifetime_increase = claim(
    "Formate-treated FAPbI3 films show significantly longer charge-carrier recombination "
    "lifetimes as measured by time-resolved photoluminescence, consistent with reduced "
    "trap-mediated non-radiative recombination confirmed by EQE_EL and SCLC",
    prior=0.84,
)

md_simulation_formate_binding = claim(
    "Ab initio molecular dynamics simulations show HCOO- coordinates strongly with "
    "Pb2+ in precursor solution, slowing crystal growth to produce larger stacked "
    "grains; HCOO- forms hydrogen-bonded networks with FA+ at the perovskite surface",
    prior=0.78,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
optimal_formate_conc = question(
    "What is the optimal FAHCOO concentration for balancing passivation effectiveness "
    "against potential adverse effects at higher concentrations, and does this optimum "
    "transfer to other perovskite compositions?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [formate_not_in_lattice, formate_passivates_vacancies],
    fivefold_el_reduction,
    reason="By passivating iodide vacancies without disrupting the lattice, formate "
    "eliminates deep trap states that cause non-radiative recombination, directly "
    "increasing radiative efficiency (EQE_EL)",
    prior=0.492,
)

support(
    [fivefold_el_reduction, ideality_factor_reduction],
    voc_96_pct_sql,
    reason="Reduction in non-radiative recombination (high EQE_EL, low n_id) directly "
    "increases Voc toward the Shockley-Queisser radiative limit",
    prior=0.498,
)

support(
    [md_simulation_formate_binding, formate_enhances_crystallinity],
    formate_passivates_vacancies,
    reason="Molecular dynamics and NMR evidence show formate binds strongly to "
    "undercoordinated Pb at vacancy sites and enhances crystal quality, with the "
    "highest binding energy among tested anions",
    prior=0.48,
)

support(
    [formate_enhances_crystallinity, carrier_lifetime_increase],
    pce_25_6_pct,
    reason="Improved crystallinity and reduced trap density lead to higher Jsc, Voc, "
    "and FF simultaneously, yielding the record efficiency",
    prior=0.492,
)

support(
    [formate_passivates_vacancies, formate_enhances_crystallinity],
    operational_stability_improvement,
    reason="Fewer defects and better crystallinity reduce degradation starting points "
    "at grain boundaries, and low halide vacancy levels prevent photoinduced iodine "
    "loss under illumination",
    prior=0.468,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_25_6_pct, certified_25_2_pct],
    p_efficiency,
    reason="Certified 25.2% PCE surpasses the 25% threshold and demonstrates that "
    "perovskite solar cells can achieve commercially competitive efficiency",
    prior=0.42,
)

support(
    [voc_96_pct_sql, fivefold_el_reduction],
    p_improvement,
    reason="Achieving 96% of the SQ Voc limit through pseudo-halide anion engineering "
    "shows systematic improvement is still possible by targeting specific defect types",
    prior=0.39,
)

support(
    [shelf_life_improvement, thermal_stability_improvement, operational_stability_improvement],
    p_stability,
    reason="Simultaneous improvement in shelf-life, thermal, and operational stability "
    "through a single additive demonstrates defect passivation as a viable route to "
    "practical device stability",
    prior=0.39,
)

support(
    [formate_passivation, pce_25_6_pct],
    p_viability,
    reason="A simple solution-processable additive achieving record efficiency and "
    "improved stability strengthens the case for perovskite PV as a viable technology",
    prior=0.36,
)

support(
    [formate_passivation, exp_context],
    p_industrialization,
    reason="The formate approach uses solution processing compatible with scalable "
    "manufacturing, and the additive is simply mixed into the precursor solution",
    prior=0.33,
)

__all__ = [
    "exp_context",
    "formate_passivation",
    "pce_25_6_pct",
    "certified_25_2_pct",
    "voc_96_pct_sql",
    "fivefold_el_reduction",
    "ideality_factor_reduction",
    "formate_not_in_lattice",
    "formate_passivates_vacancies",
    "formate_enhances_crystallinity",
    "shelf_life_improvement",
    "thermal_stability_improvement",
    "operational_stability_improvement",
    "carrier_lifetime_increase",
    "md_simulation_formate_binding",
    "optimal_formate_conc",
]
