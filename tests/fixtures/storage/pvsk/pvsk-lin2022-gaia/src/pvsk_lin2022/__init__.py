"""Azmi et al. (Lin et al.) Science 2022 — Damp heat-stable perovskite solar cells with
tailored-dimensionality 2D/3D heterojunctions. OLAI-formed 2D perovskite passivation layers
at the electron-selective contact enable 24.3% PCE and >95% retention after >1000h damp-heat
testing (85C/85%RH), passing IEC 61215:2016 industrial stability standards."""

from gaia.lang import claim, setting, question, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Experimental settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Inverted (p-i-n) perovskite solar cells with glass/ITO/2PACz/3D perovskite/2D "
    "perovskite/C60/BCP/Ag architecture, using oleylammonium iodide (OLAI) post-treatment "
    "to form 2D perovskite passivation layers on the 3D perovskite surface at the "
    "electron-selective contact, encapsulated with vacuum-laminated glass/encapsulant "
    "and butyl rubber edge sealing for stability testing"
)

olai_passivation = claim(
    "Oleylammonium iodide (OLAI) molecules applied as post-treatment on 3D perovskite "
    "surfaces form Ruddlesden-Popper-phase 2D perovskite layers; the dimensionality (n) "
    "is controlled by annealing conditions: thermal annealing (2D-TA) produces n=1 "
    "dominated layers, while room-temperature processing (2D-RT) yields mixed n=1 and "
    "n=2 layers with more pronounced n=2 character",
    prior=0.70,
)

iec_61215_standard = setting(
    "IEC 61215:2016 industrial standard requires photovoltaic modules to pass damp-heat "
    "testing at 85C and 85% relative humidity for >1000 hours with <5% relative loss in "
    "PCE, representing a critical benchmark for commercial viability"
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
pce_24_3_pct = claim(
    "2D-RT passivated inverted PSCs achieve maximum PCE of 24.3% with stabilized PCE "
    "of ~24%, Voc=1.20 V, and FF=~82%, representing ~2% absolute PCE gain over "
    "unpassivated control devices",
    prior=0.90,
)

energy_loss_0_34_ev = claim(
    "2D-RT passivation minimizes device energy loss (Eg - qVoc) to 0.34 eV, representing "
    "~96% of the thermodynamic Voc limit (1.262 V) for a bandgap of 1.55 eV, comparable "
    "to state-of-the-art GaAs solar cells at 98%",
    prior=0.88,
)

damp_heat_t95_over_1000h = claim(
    "2D-RT passivated encapsulated devices retain >95% of initial PCE (T95) after "
    ">1200 hours at damp-heat conditions (85C/85%RH), passing the IEC 61215:2016 "
    "industrial stability standard",
    prior=0.92,
)

post_dh_pce_19_3_pct = claim(
    "After >1000 hours of damp-heat testing, three devices show average PCE of "
    "19.3+/-0.69%, representing a very high retained PCE compared to prior reports",
    prior=0.88,
)

room_temp_higher_dimensionality = claim(
    "Room-temperature OLAI processing (2D-RT) forms higher-dimensionality 2D perovskite "
    "layers (n=1 and n=2 mixed, with more pronounced n=2) while thermal annealing (2D-TA) "
    "produces only n=1 layers; higher-n layers have lower formation energy and better "
    "electronic alignment with C60",
    prior=0.87,
)

cbm_alignment_with_c60 = claim(
    "The conduction band minimum (CBM) of 2D-RT films is closer to the CBM of C60 at the "
    "n-type contact, enabling more efficient charge transfer at the 2D/3D perovskite "
    "interface; 2D-TA films have higher CBM with less efficient charge transfer",
    prior=0.85,
)

reduced_trap_recombination = claim(
    "2D-passivated devices exhibit longer charge recombination lifetime and lower ideality "
    "factor than control devices, confirming reduced trap-assisted recombination at "
    "3D/C60 interfaces",
    prior=0.85,
)

universal_passivation = claim(
    "The OLAI 2D-RT passivation approach is universal across various perovskite "
    "compositions (various bandgaps) and deposition techniques (one-step, two-step, "
    "blade-coating), yielding systematic absolute PCE enhancement of 1.5-2.0%",
    prior=0.83,
)

mppt_95_pct_500h = claim(
    "Encapsulated 2D-RT devices retain up to ~95% of initial PCE after >500 hours of "
    "maximum power point tracking under simulated 1-sun illumination in ambient air, "
    "while control devices retain <90% for only ~100 hours",
    prior=0.85,
)

structural_robustness_500h_85c = claim(
    "No substantial change in structural and optical properties of 2D perovskite "
    "passivation films (both 3D and 2D perovskites) after >500 hours of thermal annealing "
    "at 85C under dark conditions, confirming robustness of the 2D passivation approach",
    prior=0.85,
)

reproducibility_high = claim(
    "The 2D-RT passivation approach shows less than 0.5% deviation for person-to-person "
    "variations among seven different researchers, confirming high reproducibility",
    prior=0.87,
)

c60_weak_bonding_problem = claim(
    "C60 is only weakly bonded to perovskite layers, inducing high energetic disorder "
    "between perovskite and C60 that limits device performance at elevated operating "
    "temperatures, and a thin C60 layer is insufficient to protect against moisture or "
    "oxygen ingress",
    prior=0.83,
)

# ---------------------------------------------------------------------------
# Questions
# ---------------------------------------------------------------------------
scale_up_2d_rt = question(
    "Can the 2D-RT passivation approach be scaled to module-level fabrication using "
    "slot-die or blade-coating processes, and does the room-temperature processing "
    "advantage translate to industrial throughput?"
)

long_term_outdoor_stability = question(
    "How do 2D-RT passivated devices perform under real outdoor conditions with daily "
    "thermal cycling, UV exposure, and varying humidity beyond the 1000-hour damp-heat "
    "benchmark?"
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [room_temp_higher_dimensionality, cbm_alignment_with_c60],
    energy_loss_0_34_ev,
    reason="Higher-dimensionality n=2 layers formed at room temperature have CBM closer "
    "to C60, enabling efficient charge transfer and minimizing energy loss at the "
    "electron-selective contact to reach 96% of the thermodynamic Voc limit",
    prior=0.492,
)

support(
    [reduced_trap_recombination, energy_loss_0_34_ev],
    pce_24_3_pct,
    reason="Reduced trap-assisted recombination at the 3D/C60 interface combined with "
    "minimized energy loss yields ~2% absolute PCE improvement over control devices "
    "to reach 24.3%",
    prior=0.498,
)

support(
    [olai_passivation, structural_robustness_500h_85c],
    damp_heat_t95_over_1000h,
    reason="2D perovskite passivation layers simultaneously serve as ion-migration-blocking "
    "barriers and moisture/oxygen ingress barriers, while the structural integrity of both "
    "2D and 3D perovskites is maintained at 85C over extended periods",
    prior=0.492,
)

support(
    [damp_heat_t95_over_1000h],
    post_dh_pce_19_3_pct,
    reason="Devices starting at ~20% PCE retain >95% after >1000 hours of damp-heat "
    "testing, yielding ~19.3% average PCE post-aging",
    prior=0.498,
)

support(
    [c60_weak_bonding_problem],
    cbm_alignment_with_c60,
    reason="The energetic mismatch between 3D perovskite and weakly-bonded C60 at "
    "elevated temperatures makes 2D perovskite interlayers essential for bridging the "
    "energy level gap at the electron-selective contact",
    prior=0.468,
)

support(
    [universal_passivation],
    reproducibility_high,
    reason="The robustness of the 2D-RT approach across compositions, deposition methods, "
    "and operators confirms that it is a reliable and transferable passivation strategy",
    prior=0.48,
)

# ---------------------------------------------------------------------------
# Connection to meta propositions
# ---------------------------------------------------------------------------
support(
    [pce_24_3_pct, energy_loss_0_34_ev],
    p_efficiency,
    reason="24.3% PCE with 96% of the thermodynamic Voc limit demonstrates that inverted "
    "PSCs can reach efficiency levels competitive with regular-structure devices and "
    "approach fundamental limits",
    prior=0.432,
)

support(
    [room_temp_higher_dimensionality, universal_passivation],
    p_improvement,
    reason="Tailoring 2D perovskite dimensionality via processing temperature is a "
    "generalizable interface engineering strategy applicable across compositions and "
    "deposition methods for continuous improvement",
    prior=0.39,
)

support(
    [damp_heat_t95_over_1000h, post_dh_pce_19_3_pct, mppt_95_pct_500h],
    p_stability,
    reason="Passing the IEC 61215:2016 damp-heat test at 85C/85%RH with >95% PCE "
    "retention after >1000 hours represents the most critical industrial stability "
    "benchmark, demonstrating that PSCs can meet the standard required for 25-30 year "
    "module lifetime",
    prior=0.45,
)

support(
    [pce_24_3_pct, damp_heat_t95_over_1000h],
    p_viability,
    reason="Simultaneously achieving high efficiency (24.3%) and passing the industrial "
    "damp-heat standard demonstrates that perovskite solar cells can meet both performance "
    "and reliability requirements for commercial deployment",
    prior=0.408,
)

support(
    [damp_heat_t95_over_1000h, universal_passivation, reproducibility_high],
    p_industrialization,
    reason="Passing IEC 61215 with a reproducible, composition-agnostic passivation "
    "approach compatible with blade-coating directly addresses the key barrier to "
    "perovskite PV industrialization",
    prior=0.39,
)

__all__ = [
    "exp_context",
    "olai_passivation",
    "iec_61215_standard",
    "pce_24_3_pct",
    "energy_loss_0_34_ev",
    "damp_heat_t95_over_1000h",
    "post_dh_pce_19_3_pct",
    "room_temp_higher_dimensionality",
    "cbm_alignment_with_c60",
    "reduced_trap_recombination",
    "universal_passivation",
    "mppt_95_pct_500h",
    "structural_robustness_500h_85c",
    "reproducibility_high",
    "c60_weak_bonding_problem",
    "scale_up_2d_rt",
    "long_term_outdoor_stability",
]
