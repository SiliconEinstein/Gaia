"""Liu et al. Science 2023 — Bimolecular passivation enables efficient and
stable inverted (p-i-n) perovskite solar cells with 25.1% certified QSS PCE."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Inverted (p-i-n) PSCs with FTO/NiOx/Me-4PACz/perovskite/passivation/"
    "C60/BCP/Ag architecture, using normal bandgap (~1.5 eV) perovskite. "
    "Active areas of 0.05 cm2 and 1.5 cm2 tested. Thermal stability tested "
    "under ISOS-D-2 (85 C in N2) and operational stability under ISOS-L-3 "
    "(1 sun, 65 C, ambient air)."
)

pin_gap_setting = setting(
    "Inverted p-i-n PSCs have potential stability and tandem-compatibility "
    "advantages over regular n-i-p, but their PCEs rarely surpass 24% under "
    "quasi-steady-state (QSS) protocol due to higher recombination at the "
    "perovskite/C60 interface."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
dmdp_strategy = claim(
    "A dual-molecule passivation strategy combining diammonium (PDAI2) for "
    "field-effect passivation with sulfur-modified methylthio (3MTPAI) for "
    "chemical passivation simultaneously suppresses both interface and surface "
    "recombination at the perovskite/C60 top interface",
    title="dmdp_bimolecular_passivation",
    prior=0.85,
)

certified_pce_251 = claim(
    "The DMDP strategy achieves a certified quasi-steady-state PCE of 25.1% "
    "for inverted PSCs (NREL certification, 0.05 cm2), the first inverted "
    "PSC to exceed 25% under QSS protocol",
    title="certified_qss_pce_25_1_percent",
    prior=0.90,
)

champion_pce_264 = claim(
    "The champion DMDP device achieves a PCE of 26.4% with Jsc of "
    "26.2 mA cm-2, Voc of 1.17 V, and FF of 85.8%",
    title="champion_pce_26_4_percent",
    prior=0.85,
)

carrier_lifetime_5x = claim(
    "DMDP passivation leads to a fivefold longer carrier lifetime and "
    "one-third the photoluminescence quantum yield loss compared to control",
    title="carrier_lifetime_5x_improvement",
    prior=0.85,
)

operational_stability_2000h = claim(
    "Encapsulated DMDP devices maintain 96% of initial PCE after 2000 hours "
    "of continuous 1-sun operation at 65 C in ambient air (ISOS-L-3 protocol)",
    title="operational_stability_2000h",
    prior=0.85,
)

thermal_stability = claim(
    "DMDP devices retain 95% of initial PCE after 1600 hours of thermal "
    "aging at 85 C in nitrogen (ISOS-D-2 protocol)",
    title="thermal_stability_95_percent_1600h",
    prior=0.80,
)

methylthio_binding = claim(
    "The sulfur-modified methylthio molecule (3MTPA) has stronger binding "
    "energy to iodide vacancy defects on the perovskite surface compared to "
    "conventional alkyl ammonium ligands, driven by S-Pb coordination bonding "
    "and enhanced hydrogen bonding with formamidinium",
    title="methylthio_stronger_binding",
    prior=0.80,
)

field_effect_passivation = claim(
    "Diammonium ligands (PDAI2) induce n-type doping and a surface dipole "
    "that repels minority carriers (holes) from the perovskite/C60 interface, "
    "achieving field-effect passivation that reduces contact-induced interface "
    "recombination",
    title="field_effect_passivation_diammonium",
    prior=0.80,
)

dark_current_reduction = claim(
    "DMDP-treated devices show a dark saturation current (J0) reduction by "
    "two orders of magnitude compared with control devices",
    title="dark_current_2_orders_reduction",
    prior=0.80,
)

tandem_281 = claim(
    "The DMDP strategy is applicable to monolithic all-perovskite tandem "
    "solar cells, achieving 28.1% PCE with Voc of 2.14 V and stabilized PCE "
    "of 27.1% under MPPT",
    title="all_perovskite_tandem_28_1_percent",
    prior=0.85,
)

universal_bandgap = claim(
    "The DMDP strategy improves PCE by 13-14% for both narrow-bandgap (~1.2 eV) "
    "and wide-bandgap (~1.8 eV) perovskite compositions, demonstrating "
    "universality across perovskite bandgaps",
    title="dmdp_universal_bandgap",
    prior=0.75,
)

large_area_24 = claim(
    "DMDP-treated devices with 1.5 cm2 area deliver a PCE of 24.0%, "
    "demonstrating scalability of the passivation approach",
    title="large_area_24_percent",
    prior=0.75,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [methylthio_binding, field_effect_passivation],
    dmdp_strategy,
    reason="Combining chemical passivation (3MTPAI binds defect sites) with "
    "field-effect passivation (PDAI2 repels minority carriers) addresses both "
    "surface and interface recombination simultaneously",
    prior=0.48,
)

support(
    [dmdp_strategy, carrier_lifetime_5x, dark_current_reduction],
    certified_pce_251,
    reason="Reduced non-radiative recombination (5x lifetime, 2 orders lower "
    "J0) directly translates to higher Voc and FF, enabling record certified "
    "QSS efficiency for inverted architecture",
    prior=0.48,
)

support(
    [dmdp_strategy],
    operational_stability_2000h,
    reason="DMDP suppresses delta-FAPbI3 formation and passivates surface "
    "defects, improving ambient stability of the perovskite film",
    prior=0.42,
)

support(
    [dmdp_strategy, universal_bandgap],
    tandem_281,
    reason="Applicability across bandgaps enables simultaneous improvement of "
    "both WBG and NBG subcells in the tandem configuration",
    prior=0.45,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [certified_pce_251, champion_pce_264],
    p_efficiency,
    reason="First inverted PSC exceeding 25% QSS certified efficiency and "
    "26.4% champion demonstrate that p-i-n architecture can match n-i-p "
    "efficiency records",
    prior=0.45,
)

support(
    [operational_stability_2000h, thermal_stability],
    p_stability,
    reason="2000 hours of stable operation at 65 C in air and 1600 hours at "
    "85 C in N2 represent industrial-grade stability benchmarks for PSCs",
    prior=0.42,
)

support(
    [certified_pce_251, tandem_281],
    p_improvement,
    reason="Continuous advancement of inverted PSC efficiency from below 24% "
    "to above 25% QSS, and all-perovskite tandem to 28.1%, demonstrates "
    "ongoing improvement trajectory",
    prior=0.42,
)

support(
    [large_area_24, tandem_281],
    p_viability,
    reason="Large-area devices and tandem configurations demonstrate "
    "practical viability of the inverted perovskite technology",
    prior=0.36,
)

__all__ = [
    "exp_context",
    "pin_gap_setting",
    "dmdp_strategy",
    "certified_pce_251",
    "champion_pce_264",
    "carrier_lifetime_5x",
    "operational_stability_2000h",
    "thermal_stability",
    "methylthio_binding",
    "field_effect_passivation",
    "dark_current_reduction",
    "tandem_281",
    "universal_bandgap",
    "large_area_24",
]
