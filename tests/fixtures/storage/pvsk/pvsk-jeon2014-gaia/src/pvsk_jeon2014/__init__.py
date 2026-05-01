"""Jeon et al. Nat Mater 2014 — Solvent engineering for high-performance perovskite
solar cells. Toluene drop-casting during spin-coating creates uniform dense perovskite
via MAI-PbI2-DMSO intermediate phase, achieving certified 16.2% PCE with no hysteresis."""

from gaia.lang import claim, setting, question, support, deduction, contradiction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Bilayer architecture perovskite solar cell: glass/FTO/bl-TiO2/mp-TiO2-perovskite "
    "nanocomposite/perovskite upper layer (100-300 nm)/PTAA/Au. Uses MAPb(I1-xBrx)3 "
    "(x=0.1-0.15) as absorber and poly(triarylamine) (PTAA) as hole-transporting "
    "material, fully solution-processed"
)

solvent_engineering = claim(
    "Perovskite deposited by spin-coating from GBL+DMSO mixed solvent followed by "
    "toluene drop-casting during spinning. The toluene rapidly removes excess DMSO "
    "and freezes constituents into a uniform MAI-PbI2-DMSO intermediate phase, which "
    "converts to perovskite upon annealing at 100C for 10 min"
,
    prior=0.70,
)

mixed_halide_composition = setting(
    "MAPb(I1-xBrx)3 with x=0.1-0.15 used because 10-15 mol% Br substitution for I "
    "greatly improves stability in ambient atmosphere while maintaining similar "
    "photovoltaic performance over the compositional range"
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_certified_16_2 = claim(
    "Fully solution-processed perovskite solar cell achieves certified PCE of 16.2% "
    "under standard reporting conditions with no hysteresis, using MAPb(I0.85Br0.15)3 "
    "and PTAA hole transporter",
    prior=0.93,
)

intermediate_phase = claim(
    "The MAI-PbI2-DMSO intermediate phase is a new crystalline compound (confirmed by "
    "XRD peaks at 6.55, 7.21, and 9.17 degrees and FTIR showing both N-H and S-O "
    "deformation modes) that converts to perovskite upon annealing at 130C",
    prior=0.88,
)

toluene_critical = claim(
    "Without toluene drop-casting, the film adopts a textile-like inhomogeneous layer "
    "that does not fully cover the substrate. The toluene drip is critically important "
    "for producing uniform, dense, and fully covering perovskite films",
    prior=0.90,
)

rms_roughness_6nm = claim(
    "The intermediate phase film has RMS roughness of 6.0 nm and the resulting "
    "perovskite film has RMS roughness of 8.3 nm (AFM over 3x3 um2), demonstrating "
    "extremely smooth and uniform surface morphology",
    prior=0.87,
)

bilayer_architecture = claim(
    "The bilayer architecture combining mesoscopic mp-TiO2-perovskite nanocomposite "
    "base with a planar perovskite upper layer (100-300 nm) effectively absorbs light "
    "and collects charges, merging advantages of mesoscopic and planar structures",
    prior=0.85,
)

dmpso_retards_reaction = claim(
    "DMSO in the MAI-PbI2-DMSO intermediate phase retards the rapid reaction between "
    "PbI2 and MAI during solvent evaporation, enabling controlled crystallization "
    "and uniform film formation",
    prior=0.83,
)

br_improves_ambient_stability = claim(
    "Substituting 10-15 mol% Br- for I- in MAPbI3 greatly improves stability in "
    "ambient atmosphere while the dual halide material demonstrates similar "
    "photovoltaic performance over the compositional range",
    prior=0.82,
)

conversion_at_130c = claim(
    "The MAI-PbI2-DMSO intermediate phase coexists with perovskite at 100C and "
    "completely converts to perovskite at 130C, as monitored by in situ high-temperature "
    "XRD",
    prior=0.85,
)

ptaa_htm = claim(
    "Poly(triarylamine) (PTAA) used as hole-transporting material achieves high "
    "performance in combination with the bilayer perovskite architecture, enabling "
    "the certified 16.2% PCE",
    prior=0.82,
)

no_hysteresis = claim(
    "The solvent-engineered perovskite solar cells show no hysteresis in J-V "
    "measurements, indicating balanced charge transport and minimal ion migration "
    "effects in the bilayer architecture",
    prior=0.80,
)

gbl_only_inhomogeneous = claim(
    "In pure GBL solvent (without DMSO), perovskite crystals form immediately during "
    "spin-coating, producing inhomogeneous islands with low surface coverage regardless "
    "of toluene drip treatment",
    prior=0.85,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
intermediate_mechanism = question(
    "What is the precise atomic structure of the MAI-PbI2-DMSO intermediate phase, "
    "and how does the guest molecule arrangement control the subsequent perovskite "
    "crystallization?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
deduction(
    [intermediate_phase, toluene_critical, dmpso_retards_reaction],
    rms_roughness_6nm,
    reason="The MAI-PbI2-DMSO intermediate phase acts as a template: DMSO retards "
    "crystallization during spinning and toluene freezes the uniform amorphous state, "
    "which converts smoothly to perovskite upon annealing",
    prior=0.48,
)

support(
    [rms_roughness_6nm, bilayer_architecture, ptaa_htm],
    pce_certified_16_2,
    reason="Uniform dense perovskite layer enables complete surface coverage and "
    "optimal charge collection, while bilayer architecture combines mesoscopic and "
    "planar advantages",
    prior=0.492,
)

support(
    [br_improves_ambient_stability],
    pce_certified_16_2,
    reason="Br substitution maintains high performance while improving ambient "
    "stability, enabling practical device fabrication",
    prior=0.45,
)

contradiction(
    gbl_only_inhomogeneous,
    toluene_critical,
    reason="Pure GBL produces inhomogeneous films even with toluene drip; the "
    "DMSO+GBL mixed solvent is essential for the intermediate phase formation that "
    "enables uniform films",
    prior=0.80,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_certified_16_2],
    p_efficiency,
    reason="Certified 16.2% PCE surpasses all prior perovskite records and approaches "
    "commercially competitive efficiency thresholds",
    prior=0.408,
)

support(
    [pce_certified_16_2, no_hysteresis],
    p_viability,
    reason="High certified efficiency with no hysteresis in a fully solution-processed "
    "device confirms practical viability of perovskite photovoltaics",
    prior=0.39,
)

support(
    [br_improves_ambient_stability],
    p_stability,
    reason="10-15% Br substitution significantly improves ambient stability of the "
    "perovskite absorber, a key requirement for practical deployment",
    prior=0.36,
)

support(
    [solvent_engineering, pce_certified_16_2],
    p_industrialization,
    reason="Fully solution-processed fabrication with spin-coating and toluene "
    "drip is inherently scalable and compatible with roll-to-roll or slot-die "
    "coating processes",
    prior=0.36,
)

support(
    [pce_certified_16_2, bilayer_architecture],
    p_improvement,
    reason="Advancing from 15% (Burschka 2013) and 15.4% (Liu 2013) to certified "
    "16.2% through solvent engineering demonstrates continued efficiency gains via "
    "process innovation",
    prior=0.36,
)

__all__ = [
    "exp_context",
    "solvent_engineering",
    "mixed_halide_composition",
    "pce_certified_16_2",
    "intermediate_phase",
    "toluene_critical",
    "rms_roughness_6nm",
    "bilayer_architecture",
    "dmpso_retards_reaction",
    "br_improves_ambient_stability",
    "conversion_at_130c",
    "ptaa_htm",
    "no_hysteresis",
    "gbl_only_inhomogeneous",
    "intermediate_mechanism",
]
