"""Kim et al. Sci Rep 2012 — First all-solid-state mesoscopic perovskite solar cell
using CH3NH3PbI3 nanocrystals with spiro-MeOTAD hole conductor, achieving 9.7% PCE."""

from gaia.lang import claim, setting, question, support, deduction, contradiction
from pvsk_meta import p_viability, p_efficiency, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "All-solid-state mesoscopic heterojunction solar cell with CH3NH3PbI3 perovskite "
    "nanoparticles deposited on 0.6 um thick mesoporous TiO2, pores infiltrated with "
    "spiro-MeOTAD hole conductor, measured under AM 1.5G solar illumination at "
    "100 mW/cm2"
)

solid_state_device = claim(
    "Device structure: FTO / compact TiO2 / mesoporous TiO2 (0.6 um) infiltrated with "
    "CH3NH3PbI3 / spiro-MeOTAD / Au, fabricated without liquid electrolyte"
,
    prior=0.70,
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_9_7_pct = claim(
    "Solid-state CH3NH3PbI3 perovskite cell achieves PCE of 9.7% with "
    "Jsc=17.6 mA/cm2, Voc=0.888 V, and fill factor 0.62 under AM 1.5G illumination, "
    "the highest reported for perovskite-sensitized cells at the time",
    prior=0.90,
)

high_absorption_coefficient = claim(
    "CH3NH3PbI3 perovskite nanocrystals exhibit an absorption coefficient of "
    "1.5x10^4 cm-1 at 550 nm, approximately one order of magnitude higher than "
    "conventional N719 dye",
    prior=0.90,
)

optical_bandgap_direct = claim(
    "The optical band gap of CH3NH3PbI3 on TiO2 is 1.5 eV determined by Kubelka-Munk "
    "analysis, and the absorption occurs via a direct allowed transition",
    prior=0.88,
)

band_alignment = claim(
    "Valence band of CH3NH3PbI3 is at -5.43 eV below vacuum and conduction band at "
    "-3.93 eV, which is slightly higher than the TiO2 conduction band, providing "
    "well-aligned band positions for charge separation",
    prior=0.87,
)

hole_transfer_mechanism = claim(
    "Charge separation proceeds via hole injection from excited CH3NH3PbI3 into "
    "spiro-MeOTAD, confirmed by photo-induced absorption (PIA) showing oxidized "
    "spiro-MeOTAD signature at 1340 nm",
    prior=0.85,
)

submicron_sufficient = claim(
    "Submicron-thick (0.6 um) mesoporous TiO2 film can deliver over 9% PCE due to "
    "the large optical absorption cross-section of perovskite nanoparticles and "
    "complete pore filling by the hole conductor",
    prior=0.85,
)

ipce_plateau = claim(
    "IPCE reaches a broad maximum at 450 nm and remains above 50% up to 750 nm, "
    "indicating efficient photon harvesting by CH3NH3PbI3 nanoparticles in the "
    "0.6 um mesoporous TiO2 film",
    prior=0.85,
)

linear_photocurrent = claim(
    "Photocurrent density is linearly proportional to light intensity, indicating "
    "a non-space-charge-limited structure with little difference between electron "
    "and hole mobility at the TiO2/perovskite/spiro-MeOTAD junction",
    prior=0.82,
)

voc_thickness_dependence = claim(
    "Open-circuit voltage decreases from ~0.9 V to ~0.8 V as TiO2 film thickness "
    "increases from 0.6 um to 1.5 um, attributed to increased dark current that "
    "lowers electron concentration and quasi-Fermi level",
    prior=0.80,
)

reductive_quenching = claim(
    "Femtosecond transient absorption confirms rapid reductive quenching of excited "
    "CH3NH3PbI3 by spiro-MeOTAD, while no significant electron injection from "
    "perovskite into TiO2 is observed on the sub-ns timescale",
    prior=0.78,
)

solid_state_stability = claim(
    "Solid-state perovskite cell shows excellent long-term stability over 500 hours "
    "without encapsulation in air, with PCE improving ~14% after 200 hours due to "
    "fill factor improvement and remaining stable thereafter",
    prior=0.80,
)

liquid_cell_degradation = claim(
    "CH3NH3PbI3 perovskite nanoparticles are unstable in iodide-containing liquid "
    "electrolyte due to rapid dissolution, while solid-state architecture dramatically "
    "improves device stability",
    prior=0.88,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
electron_transfer_question = question(
    "Why is no significant electron injection from excited CH3NH3PbI3 into TiO2 "
    "observed on the sub-ns timescale despite favorable band alignment?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
deduction(
    [high_absorption_coefficient],
    submicron_sufficient,
    reason="The 10x higher absorption coefficient vs N719 dye enables sufficient "
    "light harvesting in submicron TiO2 films",
    prior=0.492,
)

support(
    [band_alignment],
    hole_transfer_mechanism,
    reason="Well-aligned band positions between perovskite, TiO2, and spiro-MeOTAD "
    "enable efficient hole transfer from excited perovskite to the HTM",
    prior=0.468,
)

support(
    [voc_thickness_dependence],
    pce_9_7_pct,
    reason="Optimizing TiO2 thickness to 0.6 um maximizes Voc while maintaining "
    "high Jsc, yielding the 9.7% PCE",
    prior=0.48,
)

support(
    [linear_photocurrent, ipce_plateau],
    pce_9_7_pct,
    reason="Non-space-charge-limited transport and efficient broadband photon "
    "harvesting support high photocurrent generation",
    prior=0.468,
)

contradiction(
    liquid_cell_degradation,
    solid_state_stability,
    reason="Liquid electrolyte dissolves perovskite, while solid-state spiro-MeOTAD "
    "architecture eliminates this degradation pathway",
    prior=0.75,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_9_7_pct, solid_state_stability],
    p_viability,
    reason="All-solid-state architecture demonstrates that perovskite solar cells "
    "can achieve both high efficiency and long-term stability",
    prior=0.39,
)

support(
    [pce_9_7_pct],
    p_efficiency,
    reason="9.7% PCE represents a major leap from the 3.8% of Kojima 2009, "
    "demonstrating rapid efficiency improvement potential",
    prior=0.36,
)

support(
    [solid_state_stability],
    p_stability,
    reason="500+ hours of stable operation without encapsulation in air shows "
    "promising stability for solid-state perovskite cells",
    prior=0.36,
)

support(
    [solid_state_device, high_absorption_coefficient],
    p_industrialization,
    reason="All-solid-state design using submicron films and high absorption "
    "coefficients reduces material usage and simplifies device architecture",
    prior=0.3,
)

__all__ = [
    "exp_context",
    "solid_state_device",
    "pce_9_7_pct",
    "high_absorption_coefficient",
    "optical_bandgap_direct",
    "band_alignment",
    "hole_transfer_mechanism",
    "submicron_sufficient",
    "ipce_plateau",
    "linear_photocurrent",
    "voc_thickness_dependence",
    "reductive_quenching",
    "solid_state_stability",
    "liquid_cell_degradation",
    "electron_transfer_question",
]
