"""Min et al. Science 2020 — Efficient, stable solar cells by using the inherent bandgap
of alpha-phase FAPbI3. MDACl2 doping stabilizes alpha-FAPbI3 without MA/Cs/Br additives,
achieving certified 23.7% PCE with the highest Jsc (26.1-26.7 mA/cm2) among FA-based PSCs."""

from gaia.lang import claim, setting, question, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = claim(
    "FAPbI3 perovskite solar cells on mesoporous TiO2/FTO substrates using anti-solvent "
    "method with methylenediammonium dichloride (MDACl2) added to the FAPbI3 precursor "
    "at 1.9-5.7 mol%, with CuPC (copper phthalocyanine) or spiro-OMeTAD as hole transport "
    "material, Au electrode, measured under AM 1.5G at 100 mW/cm2",
    prior=0.70,
)

mdac12_dopant = setting(
    "Methylenediammonium dichloride (MDACl2) is a divalent diammonium dopant with ionic "
    "radius (262 pm) comparable to FA+ (256 pm); MDA2+ can form more hydrogen bonds with "
    "I- than FA+ or MA+ due to having more H atoms, potentially stabilizing the alpha-FAPbI3 "
    "phase in smaller amounts than MA"
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
certified_23_7_pct = claim(
    "FAPbI3:3.8 mol% MDACl2 PSC achieves certified stabilized PCE of 23.73% via "
    "quasi-steady-state method at Newport, with Jsc=26.1 mA/cm2, Voc=1.15 V, FF=79.0%, "
    "the highest reported for mp-TiO2-based PSCs",
    prior=0.92,
)

record_jsc_26_7 = claim(
    "A second certified device achieves Jsc=26.70 mA/cm2 (highest reported for "
    "FAPbI3-based PSCs) with Voc=1.144 V and FF=77.56%, corresponding to stabilized "
    "PCE of 23.69%",
    prior=0.90,
)

uncertified_24_66_pct = claim(
    "The best-performing lab-measured device achieves PCE of 24.66% under reverse scan "
    "with Jsc=26.50 mA/cm2, Voc=1.14 V, and FF=81.77%",
    prior=0.88,
)

alpha_phase_stabilization = claim(
    "Adding 3.8-5.7 mol% MDACl2 to FAPbI3 stabilizes the alpha-phase against transition "
    "to the delta-phase even after 24 hours at 80% humidity, whereas pure FAPbI3 and "
    "FAPbI3 with only 1.9 mol% MDACl2 completely convert to the delta-phase",
    prior=0.90,
)

inherent_bandgap_preserved = claim(
    "MDACl2 addition preserves the inherent narrow bandgap of FAPbI3: PL emission shifts "
    "minimally from 826 nm (pristine) to 822 nm (3.8 mol%), compared to 816 nm for the "
    "MAPbBr3-stabilized control, enabling higher photocurrent through broader absorption",
    prior=0.88,
)

mida_hbond_mechanism = claim(
    "MDA2+ stabilizes alpha-FAPbI3 through two mechanisms: (1) stronger hydrogen bonding "
    "with I- due to more H atoms than FA+ or MA+, and (2) stronger ionic interaction from "
    "its divalent charge state, enabling stabilization in smaller amounts than MA",
    prior=0.80,
)

cl_residue_at_interface = claim(
    "XPS and TOF-SIMS show higher residual Cl- content in FAPbI3:3.8 mol% MDACl2 than in "
    "the MAPbBr3 control, concentrated at the TiO2/perovskite interface, which is expected "
    "to enhance light stability of the PSC",
    prior=0.85,
)

defect_density_low = claim(
    "Space-charge-limited current measurements show electron trap densities of "
    "5.7x10^15 cm-3 for FAPbI3:3.8 mol% MDACl2, lower than 1.0x10^16 cm-3 for the "
    "MAPbBr3 control, indicating that FA vacancy defects do not act as deep electron traps",
    prior=0.85,
)

carrier_lifetime_1562_ns = claim(
    "FAPbI3:3.8 mol% MDACl2 films exhibit nonradiative recombination lifetime of 1562 ns "
    "on quartz, more than double the control value of 715 ns, indicating reduced trap-assisted "
    "recombination",
    prior=0.87,
)

humidity_stability_85rh = claim(
    "Unencapsulated target device retains >90% of initial PCE after 70 hours at 85% RH "
    "and 25C, while the MAPbBr3-stabilized control degrades to 40% of initial PCE",
    prior=0.87,
)

thermal_stability_150c = claim(
    "Unencapsulated target device retains >90% of initial PCE after 20 hours annealing at "
    "150C in air (~25% RH), while the control degrades to <20% of initial PCE due to MA "
    "evaporation from the MAPbBr3 component",
    prior=0.88,
)

photostability_600h_mppt = claim(
    "Encapsulated target device with spiro-OMeTAD HTM maintains ~90% of initial PCE "
    "(>23.0%) over 600 hours of maximum power point tracking under full solar illumination "
    "(AM 1.5G, 100 mW/cm2) in ambient conditions without UV filter",
    prior=0.85,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
optimal_mda_concentration = question(
    "What is the optimal MDACl2 concentration window for balancing alpha-phase stability "
    "against defect formation from FA vacancies, and does the MDACl2 approach transfer "
    "to mixed-halide or mixed-cation perovskite compositions?"
)

long_term_operational_stability = question(
    "Can MDACl2-stabilized FAPbI3 devices maintain >90% PCE beyond 1000 hours of "
    "continuous operation under damp-heat conditions (85C/85% RH), which is the "
    "industry standard IEC 61215 test?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [mida_hbond_mechanism],
    alpha_phase_stabilization,
    reason="MDA2+ with more H atoms and divalent charge forms stronger H-bonds and ionic "
    "interactions with I- in the perovskite lattice, preventing the alpha-to-delta phase "
    "transition even under high humidity conditions",
    prior=0.492,
)

support(
    [alpha_phase_stabilization, inherent_bandgap_preserved],
    record_jsc_26_7,
    reason="Stable alpha-FAPbI3 with preserved narrow bandgap (~1.47 eV) enables broader "
    "solar absorption and higher Jsc than MAPbBr3-stabilized compositions that have "
    "widened bandgaps",
    prior=0.492,
)

support(
    [defect_density_low, cl_residue_at_interface, carrier_lifetime_1562_ns],
    certified_23_7_pct,
    reason="Low defect density, Cl-enhanced interface stability, and long carrier lifetime "
    "jointly contribute to high Voc, FF, and Jsc, yielding record PCE for mp-TiO2 devices",
    prior=0.498,
)

support(
    [alpha_phase_stabilization, cl_residue_at_interface],
    humidity_stability_85rh,
    reason="Phase-stable alpha-FAPbI3 resists humidity-induced degradation, and Cl at the "
    "TiO2 interface further enhances stability against environmental stress",
    prior=0.48,
)

support(
    [alpha_phase_stabilization],
    thermal_stability_150c,
    reason="MA-free composition eliminates the volatile MA+ cation, while MDA2+ with "
    "stronger ionic bonding maintains structural integrity at 150C",
    prior=0.492,
)

support(
    [cl_residue_at_interface, alpha_phase_stabilization],
    photostability_600h_mppt,
    reason="High Cl concentration at the TiO2/perovskite interface suppresses "
    "photocatalytic degradation, and alpha-phase stability prevents light-induced "
    "phase transitions even without UV filtering",
    prior=0.48,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [certified_23_7_pct, record_jsc_26_7],
    p_efficiency,
    reason="Certified 23.7% PCE with record Jsc demonstrates that using the inherent "
    "bandgap of alpha-FAPbI3 enables commercially competitive efficiency without "
    "bandgap-widening additives",
    prior=0.42,
)

support(
    [inherent_bandgap_preserved, mida_hbond_mechanism],
    p_improvement,
    reason="Doping with divalent diammonium cations to stabilize the alpha-phase while "
    "preserving the optimal bandgap represents a new materials engineering pathway for "
    "efficiency improvement",
    prior=0.39,
)

support(
    [humidity_stability_85rh, thermal_stability_150c, photostability_600h_mppt],
    p_stability,
    reason="Simultaneous humidity, thermal, and photostability improvements through a "
    "single additive, with MA-free composition eliminating a key degradation pathway, "
    "demonstrates progress toward practical operational stability",
    prior=0.39,
)

support(
    [certified_23_7_pct, inherent_bandgap_preserved],
    p_viability,
    reason="Achieving high efficiency from the pure FAPbI3 bandgap without relying on "
    "mixed cation/anion compositions simplifies the material system and strengthens the "
    "case for perovskite PV viability",
    prior=0.36,
)

support(
    [exp_context, uncertified_24_66_pct],
    p_industrialization,
    reason="Simple solution-processable additive compatible with existing anti-solvent "
    "fabrication methods and mesoporous TiO2 architecture, facilitating scale-up",
    prior=0.33,
)

__all__ = [
    "exp_context",
    "mdac12_dopant",
    "certified_23_7_pct",
    "record_jsc_26_7",
    "uncertified_24_66_pct",
    "alpha_phase_stabilization",
    "inherent_bandgap_preserved",
    "mida_hbond_mechanism",
    "cl_residue_at_interface",
    "defect_density_low",
    "carrier_lifetime_1562_ns",
    "humidity_stability_85rh",
    "thermal_stability_150c",
    "photostability_600h_mppt",
    "optimal_mda_concentration",
    "long_term_operational_stability",
]
