"""Burschka et al. Nature 2013 — Sequential (two-step) deposition method for
perovskite formation within nanoporous TiO2, achieving certified 14.14% and lab 15% PCE
with excellent reproducibility and 500-hour stability."""

from gaia.lang import claim, setting, question, support, deduction, contradiction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Mesoscopic solar cell fabricated by sequential deposition: PbI2 first introduced "
    "from DMF solution (~1 M, 70C) into 350 nm mesoporous TiO2, then transformed to "
    "CH3NH3PbI3 by dipping in CH3NH3I/2-propanol (10 mg/ml) for 20 seconds, with "
    "spiro-MeOTAD HTM doped with Co(III) complex (10 mol%), measured under AM 1.5G"
)

sequential_method = claim(
    "Two-step deposition method: PbI2 infiltrated into mesoporous TiO2 (pore size "
    "~22 nm confines PbI2 crystals), then converted to perovskite by CH3NH3I solution. "
    "The layered PbI2 structure (I-Pb-I planes with weak interlayer van der Waals "
    "bonding) facilitates cation insertion"
,
    prior=0.70,
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_15_pct = claim(
    "Best-performing sequential-deposition cell achieves PCE of 15.0% with "
    "Jsc=20.0 mA/cm2, Voc=0.993 V, and fill factor 0.73, measured at 96.4 mW/cm2",
    prior=0.92,
)

pce_certified_14_14 = claim(
    "An accredited photovoltaic calibration laboratory certifies PCE of 14.14% "
    "under standard AM 1.5G reporting conditions, confirming the validity of the "
    "lab measurements",
    prior=0.93,
)

fast_conversion = claim(
    "Conversion of nanoconfined PbI2 to CH3NH3PbI3 perovskite is complete within "
    "seconds of exposure to CH3NH3I solution, as shown by immediate disappearance "
    "of PbI2 XRD (001) peak and appearance of tetragonal perovskite reflections",
    prior=0.90,
)

nanoconfinement_enhances_kinetics = claim(
    "Confining PbI2 crystals to ~22 nm within mesoporous TiO2 drastically enhances "
    "their rate of conversion to perovskite compared to bulk PbI2 films (50-200 nm "
    "crystallites), where conversion remains incomplete even after 45 minutes",
    prior=0.88,
)

apce_near_unity = claim(
    "The absorbed-photon-to-current conversion efficiency (APCE) is greater than 90% "
    "over the whole visible region without correction for reflective losses, indicating "
    "near-unity quantum yield for charge carrier generation and collection",
    prior=0.90,
)

ipce_peak_90_pct = claim(
    "IPCE reaches peak values exceeding 90% in the short-wavelength visible region, "
    "with photocurrent generation starting at 800 nm consistent with the CH3NH3PbI3 "
    "bandgap",
    prior=0.88,
)

typical_device_12_9 = claim(
    "Typical device shows PCE of 12.9% with Jsc=17.1 mA/cm2, Voc=0.992 V, and "
    "fill factor 0.73 at 95.6 mW/cm2; batch average 12.0% +/- 0.5% (n=10)",
    prior=0.90,
)

high_reproducibility = claim(
    "Sequential deposition greatly increases reproducibility with standard deviation "
    "of only 0.5% PCE across 10 devices, compared to large morphological variations "
    "and performance spread in single-step deposition",
    prior=0.87,
)

stability_500h = claim(
    "Sealed cell maintained under constant light soaking (~100 mW/cm2, 45C) with "
    "maximum-power-point tracking retains >80% of initial PCE after 500 hours, with "
    "no change in short-circuit photocurrent",
    prior=0.85,
)

no_photodegradation = claim(
    "No photodegradation of the perovskite light harvester is observed during 500 "
    "hours of light soaking; the PCE decrease is solely due to Voc and fill factor "
    "decline from reduced shunt resistance",
    prior=0.83,
)

co_dopant_htm = claim(
    "Using a Co(III) complex as p-type dopant for spiro-MeOTAD at 10 mol% doping "
    "level ensures sufficient conductivity and low series resistance in the HTM",
    prior=0.82,
)

prewetting_improves = claim(
    "A pre-wetting step (dipping in 2-propanol for 1-2 s before CH3NH3I solution) "
    "locally decreases CH3NH3I concentration, inducing growth of larger perovskite "
    "crystals and increased light scattering for improved long-wavelength response",
    prior=0.78,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
degradation_mechanism = question(
    "What is the precise mechanism causing the decrease in shunt resistance during "
    "500-hour light soaking, and can it be eliminated through interface engineering?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
deduction(
    [nanoconfinement_enhances_kinetics, fast_conversion],
    high_reproducibility,
    reason="Fast and complete conversion within nanopores yields uniform perovskite "
    "morphology, eliminating the large morphological variations of single-step deposition",
    prior=0.492,
)

support(
    [apce_near_unity, ipce_peak_90_pct],
    pce_15_pct,
    reason="Near-unity quantum yield for charge generation and collection across the "
    "visible spectrum directly supports the record 15% PCE",
    prior=0.48,
)

support(
    [prewetting_improves, co_dopant_htm],
    pce_15_pct,
    reason="Pre-wetting increases perovskite loading and light scattering for higher "
    "photocurrent, while Co-doped HTM reduces series resistance for better fill factor",
    prior=0.468,
)

support(
    [stability_500h, no_photodegradation],
    p_stability,
    reason="Perovskite itself is photostable over 500 hours; degradation is limited "
    "to interfacial effects, suggesting stability can be engineered",
    prior=0.39,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_15_pct, pce_certified_14_14],
    p_efficiency,
    reason="Certified 14.14% and lab 15% PCE represent the highest efficiencies for "
    "any solution-processed or organic/hybrid solar cell at the time",
    prior=0.39,
)

support(
    [pce_15_pct, high_reproducibility],
    p_viability,
    reason="Certified high efficiency with excellent reproducibility validates "
    "perovskite solar cells as a practical photovoltaic technology",
    prior=0.39,
)

support(
    [pce_15_pct, pce_certified_14_14],
    p_improvement,
    reason="Progression from 10.9% (Lee 2012) to 15% PCE via sequential deposition "
    "demonstrates rapid improvement through process engineering",
    prior=0.36,
)

support(
    [sequential_method, high_reproducibility],
    p_industrialization,
    reason="Two-step solution process with tight reproducibility is inherently more "
    "scalable than single-step methods with uncontrolled precipitation",
    prior=0.33,
)

# ---------------------------------------------------------------------------
# Cross-paper: contradiction with single-step deposition
# ---------------------------------------------------------------------------
contradiction(
    high_reproducibility,
    # Conceptual claim: single-step perovskite deposition produces uncontrolled
    # precipitation with large morphological variations
    claim(
        "Single-step perovskite deposition from mixed PbX2/CH3NH3X solution produces "
        "large morphological variations and wide spread of photovoltaic performance",
        prior=0.85,
    ),
    reason="Sequential deposition confines PbI2 in nanopores and converts uniformly "
    "in seconds, whereas single-step allows uncontrolled crystal growth from solution",
    prior=0.75,
)

__all__ = [
    "exp_context",
    "sequential_method",
    "pce_15_pct",
    "pce_certified_14_14",
    "fast_conversion",
    "nanoconfinement_enhances_kinetics",
    "apce_near_unity",
    "ipce_peak_90_pct",
    "typical_device_12_9",
    "high_reproducibility",
    "stability_500h",
    "no_photodegradation",
    "co_dopant_htm",
    "prewetting_improves",
    "degradation_mechanism",
]
