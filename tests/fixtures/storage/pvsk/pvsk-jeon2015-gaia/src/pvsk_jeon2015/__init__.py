"""Jeon et al. Nature 2015 — Compositional engineering of perovskite materials
for high-performance solar cells. FAPbI3/MAPbBr3 mixed perovskites achieve >18% PCE."""

from gaia.lang import claim, setting, support, deduction
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability

# --- Background ---
bilayer_architecture = setting(
    "Bilayer solar-cell architecture with perovskite-infiltrated mesoporous TiO2 "
    "electrodes and upper perovskite layer obtained by solvent engineering techniques"
)

# --- Core claims ---
fa_narrower_bandgap = claim(
    "FAPbI3 has a bandgap of 1.48 eV with absorption edge of 840 nm, narrower than "
    "MAPbI3 (1.5-1.6 eV, edge ~800 nm), enabling broader solar spectrum absorption",
    prior=0.88,
)

fa_phase_unstable = claim(
    "Pure FAPbI3 black perovskite phase (alpha-phase) is thermally unstable, "
    "converting to yellow delta-phase at room temperature in humid atmosphere",
    prior=0.85,
)

mapbbr3_stabilizes_fapbi3 = claim(
    "Incorporation of MAPbBr3 into FAPbI3 stabilizes the perovskite phase of FAPbI3 "
    "and prevents conversion to the non-perovskite delta-phase",
    prior=0.85,
)

optimal_composition_x15 = claim(
    "Optimal composition (FAPbI3)0.85(MAPbBr3)0.15 achieves maximum Jsc of 22 mA/cm2, "
    "Voc of 1.08 V, fill factor 73%, and PCE >18% under standard AM1.5G illumination",
    prior=0.90,
)

negligible_hysteresis = claim(
    "FAPbI3/MAPbBr3 mixed perovskite solar cells show negligible hysteresis in J-V "
    "curves compared to MAPbI3-based cells, due to better balance of electron and "
    "hole transport",
    prior=0.82,
)

pce_over_18_pct = claim(
    "The (FAPbI3)0.85(MAPbBr3)0.15 composition achieves stabilized power conversion "
    "efficiency exceeding 18% under standard illumination of 100 mW/cm2",
    prior=0.90,
)

hole_diffusion_superior = claim(
    "FAPbI3 has a hole-diffusion length (~813 nm) 4.6 times longer than its "
    "electron-diffusion length (~177 nm), contrasting with MAPbI3 where electron "
    "diffusion length exceeds hole diffusion length",
    prior=0.83,
)

bandgap_tunable = claim(
    "The bandgap of (FAPbI3)1-x(MAPbBr3)x is tunable by adjusting the molar ratio x, "
    "with absorption edge shifting from 840 nm (x=0) to shorter wavelengths as x increases",
    prior=0.85,
)

carrier_balance_improved = claim(
    "Mixing FAPbI3 with MAPbBr3 improves the balance between electron and hole "
    "transport, which is critical for high-efficiency perovskite solar cells",
    prior=0.78,
)

thermal_stability_improved = claim(
    "The mixed FAPbI3/MAPbBr3 composition shows improved thermal stability compared to "
    "pure FAPbI3, with the perovskite phase remaining stable at 100C annealing temperature",
    prior=0.80,
)

# --- Internal reasoning ---
support(
    [fa_narrower_bandgap, mapbbr3_stabilizes_fapbi3],
    optimal_composition_x15,
    reason="Narrower bandgap of FAPbI3 enables broader absorption while MAPbBr3 "
    "stabilizes the perovskite phase, together achieving optimal performance",
    prior=0.492,
)

support(
    [optimal_composition_x15, negligible_hysteresis],
    pce_over_18_pct,
    reason="Optimal composition combined with reduced hysteresis yields reliable "
    "stabilized efficiency above 18%",
    prior=0.51,
)

deduction(
    [mapbbr3_stabilizes_fapbi3, thermal_stability_improved],
    carrier_balance_improved,
    reason="Phase stabilization enables proper crystal formation and balanced "
    "carrier transport properties",
    prior=0.45,
)

support(
    [fa_narrower_bandgap, bandgap_tunable],
    optimal_composition_x15,
    reason="Bandgap tunability through compositional engineering allows optimization "
    "of the absorption spectrum for maximum efficiency",
    prior=0.48,
)

# --- Connection to meta propositions ---
support(
    [pce_over_18_pct, optimal_composition_x15],
    p_efficiency,
    reason="Compositional engineering achieves >18% PCE, approaching the 20% "
    "threshold for commercially competitive efficiency",
    prior=0.33,
)

support(
    [mapbbr3_stabilizes_fapbi3, thermal_stability_improved],
    p_improvement,
    reason="Compositional engineering of A-site cations provides a systematic approach "
    "to improve both efficiency and stability through rational material design",
    prior=0.39,
)

support(
    [thermal_stability_improved, negligible_hysteresis],
    p_stability,
    reason="Improved thermal stability and reduced hysteresis in mixed compositions "
    "address key operational stability concerns",
    prior=0.33,
)

__all__ = [
    "bilayer_architecture",
    "fa_narrower_bandgap",
    "fa_phase_unstable",
    "mapbbr3_stabilizes_fapbi3",
    "optimal_composition_x15",
    "negligible_hysteresis",
    "pce_over_18_pct",
    "hole_diffusion_superior",
    "bandgap_tunable",
    "carrier_balance_improved",
    "thermal_stability_improved",
]
