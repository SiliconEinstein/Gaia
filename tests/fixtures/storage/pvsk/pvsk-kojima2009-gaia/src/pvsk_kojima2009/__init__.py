"""Kojima et al. JACS 2009 — First demonstration of organometal halide perovskites
as visible-light sensitizers for photovoltaic cells. CH3NH3PbBr3 and CH3NH3PbI3 on
mesoporous TiO2 achieved 3.8% PCE."""

from gaia.lang import claim, setting, question, support, deduction
from pvsk_meta import p_viability, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Photoelectrochemical cells constructed with CH3NH3PbX3 (X=Br, I) nanocrystalline "
    "particles self-organized on mesoporous TiO2 (8-12 um thick) deposited on FTO glass, "
    "using organic electrolyte with lithium halide/halogen redox couple, measured under "
    "AM 1.5 simulated sunlight at 100 mW/cm2"
)

perovskite_materials = claim(
    "Organolead halide perovskite compounds CH3NH3PbBr3 (cubic, a=5.9 A) and "
    "CH3NH3PbI3 (tetragonal, a=8.855 A, c=12.659 A) synthesized from abundant sources "
    "Pb, C, N, and halogen, deposited from precursor solutions via spin-coating"
,
    prior=0.70,
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_3_8_pct = claim(
    "CH3NH3PbI3-sensitized photoelectrochemical cell achieves power conversion "
    "efficiency of 3.81% under AM 1.5 simulated sunlight at 100 mW/cm2, with "
    "Jsc=11.0 mA/cm2, Voc=0.61 V, and fill factor 0.57",
    prior=0.90,
)

high_voc_bromide = claim(
    "CH3NH3PbBr3-sensitized cell yields a high open-circuit voltage of 0.96 V with "
    "Jsc=5.57 mA/cm2, fill factor 0.59, and PCE of 3.13%",
    prior=0.90,
)

perovskite_sensitizes_tio2 = claim(
    "Organolead halide perovskite nanocrystalline particles efficiently sensitize "
    "mesoporous TiO2 for visible-light conversion, confirmed by anodic photocurrent "
    "generation and IPCE measurements",
    prior=0.88,
)

ipce_bromide_65_pct = claim(
    "CH3NH3PbBr3/TiO2 cell achieves maximum IPCE of 65% in the visible region "
    "(lambda < 600 nm) with sharp band-gap absorption onset near 570 nm",
    prior=0.88,
)

ipce_iodide_extended = claim(
    "CH3NH3PbI3/TiO2 cell shows extended spectral response to 800 nm but lower "
    "peak IPCE of 45%, reflecting broader but less intense absorption",
    prior=0.85,
)

bandgap_bathochromic_shift = claim(
    "Halogen substitution from Br to I in CH3NH3PbX3 causes a bathochromic shift "
    "in absorption, analogous to silver halide ionic crystals",
    prior=0.85,
)

valence_band_levels = claim(
    "Valence-band levels of CH3NH3PbBr3 and CH3NH3PbI3 are at ~5.38 and 5.44 eV "
    "versus vacuum level, respectively, as measured by photoelectron spectroscopy",
    prior=0.85,
)

conduction_band_levels = claim(
    "Conduction-band levels of CH3NH3PbBr3 and CH3NH3PbI3 are at ~3.36 and 4.0 eV "
    "respectively, allowing electron injection into the TiO2 conduction band (~4.0 eV)",
    prior=0.83,
)

high_voc_origin = claim(
    "The high Voc of 0.96 V in CH3NH3PbBr3 cells is due to the more positive "
    "electrochemical potential of the Br2/Br- redox couple compared to I2/I-, "
    "expanding the range of photovoltage",
    prior=0.78,
)

exceeds_quantum_dots = claim(
    "The 3.81% PCE of the CH3NH3PbI3 cell is significantly higher than efficiencies "
    "obtained to date with non-organic sensitizers and quantum dots (CdS, CdSe, PbS, "
    "InP, InAs)",
    prior=0.85,
)

perovskite_series_potential = claim(
    "A series of organic-inorganic perovskite materials CH3NH3MX3 (M=Pb, Sn; X=halogen) "
    "with different energy gaps are targets for optimizing photovoltaic cell performance",
    prior=0.65,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
durability_question = claim(
    "How can the photocurrent decay observed under continuous irradiation for open "
    "cells exposed to air be mitigated to improve perovskite photovoltaic cell lifetime?"
,
    prior=0.50,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [valence_band_levels, conduction_band_levels],
    perovskite_sensitizes_tio2,
    reason="Energy level alignment shows that perovskite valence bands are more "
    "positive than halide oxidation potentials and conduction bands allow electron "
    "injection into TiO2, enabling efficient charge separation",
    prior=0.48,
)

deduction(
    [bandgap_bathochromic_shift],
    ipce_iodide_extended,
    reason="The iodide perovskite has a narrower bandgap than bromide, shifting "
    "absorption to longer wavelengths but with lower peak IPCE",
    prior=0.492,
)

support(
    [high_voc_origin],
    high_voc_bromide,
    reason="The more positive Br2/Br- redox potential expands the photovoltage "
    "range, yielding Voc close to 1.0 V",
    prior=0.468,
)

support(
    [perovskite_sensitizes_tio2, pce_3_8_pct],
    exceeds_quantum_dots,
    reason="Perovskite-sensitized TiO2 produces higher photocurrents and efficiency "
    "than any quantum dot sensitizer reported at the time",
    prior=0.48,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_3_8_pct, perovskite_sensitizes_tio2],
    p_viability,
    reason="First demonstration that organometal halide perovskites can function as "
    "effective visible-light sensitizers in photovoltaic cells",
    prior=0.36,
)

support(
    [pce_3_8_pct, perovskite_series_potential],
    p_improvement,
    reason="The initial 3.81% efficiency with room for optimization through halogen "
    "substitution and material tuning suggests significant improvement potential",
    prior=0.33,
)

support(
    [durability_question],
    p_stability,
    reason="Photocurrent decay under continuous irradiation highlights stability as "
    "a key challenge for perovskite photovoltaic cells",
    prior=0.3,
)

support(
    [perovskite_materials],
    p_industrialization,
    reason="Perovskite materials are synthesized from abundant sources (Pb, C, N, "
    "halogen) using solution processing, suggesting low-cost manufacturing potential",
    prior=0.27,
)

__all__ = [
    "exp_context",
    "perovskite_materials",
    "pce_3_8_pct",
    "high_voc_bromide",
    "perovskite_sensitizes_tio2",
    "ipce_bromide_65_pct",
    "ipce_iodide_extended",
    "bandgap_bathochromic_shift",
    "valence_band_levels",
    "conduction_band_levels",
    "high_voc_origin",
    "exceeds_quantum_dots",
    "perovskite_series_potential",
    "durability_question",
]
