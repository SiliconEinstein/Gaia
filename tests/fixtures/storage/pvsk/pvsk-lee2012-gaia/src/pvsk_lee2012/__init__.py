"""Lee et al. Science 2012 — Meso-superstructured solar cell (MSSC) concept using
CH3NH3PbI2Cl perovskite with insulating Al2O3 scaffold, achieving 10.9% PCE and >1.1 V
open-circuit voltage."""

from gaia.lang import claim, setting, question, support, deduction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Meso-superstructured solar cell (MSSC) using mixed-halide perovskite "
    "CH3NH3PbI2Cl processed from DMF precursor via spin-coating in ambient "
    "conditions, with either mesoporous TiO2 or insulating Al2O3 scaffold, "
    "spiro-OMeTAD hole conductor, and Ag electrode, measured under AM 1.5 "
    "100 mW/cm2 simulated sunlight"
)

mixed_halide_perovskite = setting(
    "CH3NH3PbI2Cl mixed-halide perovskite with tetragonal structure (a=8.825 A, "
    "b=8.835 A, c=11.24 A), long-range crystalline domains >200 nm, and remarkable "
    "stability to processing in air, unlike CH3NH3PbI3"
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_10_9_pct = claim(
    "Al2O3-based meso-superstructured solar cell achieves PCE of 10.9% with "
    "Jsc=17.8 mA/cm2, Voc=0.98 V, and fill factor 0.63, the highest reported for "
    "perovskite or hybrid solar cells at the time",
    prior=0.92,
)

voc_above_1_1v = claim(
    "An Al2O3-based device achieves Voc above 1.13 V with Jsc=15.4 mA/cm2 and "
    "fill factor 0.45, yielding 7.8% PCE, demonstrating exceptionally high "
    "photovoltage generation",
    prior=0.88,
)

tio2_cell_7_6_pct = claim(
    "Perovskite-sensitized TiO2 solar cell achieves PCE of 7.6% with "
    "Jsc=17.8 mA/cm2, Voc=0.80 V, and fill factor 0.53",
    prior=0.88,
)

al2o3_increases_voc = claim(
    "Replacing mesoporous TiO2 with insulating Al2O3 increases Voc by >200 mV "
    "while maintaining comparable Jsc, because electrons are confined in the "
    "perovskite rather than injected into the metal oxide",
    prior=0.88,
)

perovskite_n_type_transport = claim(
    "The perovskite layer functions as both absorber and n-type semiconductor, "
    "transporting electrons through the film thickness, as demonstrated by charge "
    "collection faster by a factor >10 in Al2O3 cells vs TiO2 cells",
    prior=0.87,
)

chemical_capacitance_explanation = claim(
    "The increased Voc in Al2O3 cells is caused by substantial reduction of chemical "
    "capacitance: without mesoporous TiO2 sub-bandgap states, the quasi-Fermi level "
    "for electrons moves nearer to the conduction band for the same charge density",
    prior=0.82,
)

low_energy_losses = claim(
    "The difference between optical bandgap (1.55 eV) and Voc (1.1 V) is only 0.45 eV, "
    "competitive with the best thin-film photovoltaic technologies and far superior "
    "to typical 0.7-0.8 eV losses in dye-sensitized and organic solar cells",
    prior=0.85,
)

absorption_stability = claim(
    "CH3NH3PbI2Cl perovskite film maintains absorbance ~1.8 at 500 nm (98.4% "
    "absorption) over 1000 hours of constant simulated full sunlight illumination "
    "without UV filtration",
    prior=0.87,
)

hole_transfer_effective = claim(
    "Hole transfer from photoexcited perovskite to spiro-OMeTAD is highly effective "
    "in both TiO2 and Al2O3 architectures, confirmed by PIA showing oxidized "
    "spiro-OMeTAD features at 525, 750, and 1200 nm",
    prior=0.85,
)

planar_junction_feasible = claim(
    "A planar-junction diode (FTO/TiO2/CH3NH3PbI2Cl/spiro-OMeTAD/Ag) with ~150 nm "
    "perovskite film achieves Jsc=7.13 mA/cm2, Voc=0.64 V, FF=0.4, and PCE=1.8%, "
    "confirming perovskite can function without mesoporous scaffold",
    prior=0.80,
)

perovskite_conductivity = claim(
    "The perovskite absorber has conductivity on the order of 10^-3 S/cm, while "
    "spiro-OMeTAD is less conductive (~10^-5 S/cm), requiring careful balance "
    "between shunt and series resistance",
    prior=0.78,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
excitonic_vs_pn = question(
    "Is the MSSC fundamentally excitonic or a distributed p-n junction? Do free "
    "charges generate in the bulk or are highly mobile excitons quenched at the "
    "perovskite-spiro-OMeTAD interface?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
deduction(
    [al2o3_increases_voc, perovskite_n_type_transport],
    pce_10_9_pct,
    reason="Eliminating the n-type TiO2 scaffold reduces chemical capacitance and "
    "faster electron transport through perovskite, jointly enabling higher Voc and "
    "better fill factor",
    prior=0.492,
)

support(
    [chemical_capacitance_explanation],
    al2o3_increases_voc,
    reason="Without sub-bandgap states in mesoporous TiO2, the electron quasi-Fermi "
    "level is closer to the conduction band, directly increasing Voc",
    prior=0.468,
)

support(
    [low_energy_losses, absorption_stability],
    p_viability,
    reason="Minimal energy losses and photostability over 1000 hours demonstrate "
    "perovskite as a robust photovoltaic absorber",
    prior=0.39,
)

support(
    [pce_10_9_pct, voc_above_1_1v],
    p_efficiency,
    reason="10.9% PCE and Voc exceeding 1.1 V represent significant progress toward "
    "commercially competitive efficiencies",
    prior=0.36,
)

support(
    [absorption_stability],
    p_stability,
    reason="Perovskite absorber maintains optical properties over 1000 hours of "
    "continuous simulated sunlight exposure",
    prior=0.36,
)

support(
    [planar_junction_feasible, perovskite_n_type_transport],
    p_industrialization,
    reason="Demonstration that mesoporous scaffolds are not essential opens pathways "
    "to simplified thin-film manufacturing processes",
    prior=0.33,
)

support(
    [pce_10_9_pct],
    p_improvement,
    reason="Advancing from 9.7% (Kim 2012) to 10.9% PCE through the MSSC concept "
    "shows continuous improvement via architectural innovation",
    prior=0.33,
)

# ---------------------------------------------------------------------------
# Cross-paper connection: builds on Kojima 2009 and Kim 2012
# ---------------------------------------------------------------------------
support(
    [absorption_stability, low_energy_losses],
    p_improvement,
    reason="Replacing the n-type oxide scaffold with insulator eliminates fundamental "
    "energy losses from disordered TiO2, a conceptual advance for further optimization",
    prior=0.33,
)

__all__ = [
    "exp_context",
    "mixed_halide_perovskite",
    "pce_10_9_pct",
    "voc_above_1_1v",
    "tio2_cell_7_6_pct",
    "al2o3_increases_voc",
    "perovskite_n_type_transport",
    "chemical_capacitance_explanation",
    "low_energy_losses",
    "absorption_stability",
    "hole_transfer_effective",
    "planar_junction_feasible",
    "perovskite_conductivity",
    "excitonic_vs_pn",
]
