"""He et al. Nature 2025 — Efficient perovskite/silicon tandem with asymmetric
self-assembly molecule HTL201, achieving 34.58% certified PCE (~35%)."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_industrialization

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Perovskite/silicon tandem solar cells on silicon heterojunction bottom "
    "cells. Perovskite bandgap 1.69 eV. Device stack: IZO/HTL201/perovskite/"
    "LiF/EDAI/C60/SnO2/IZO/Ag/MgF2. Device area 1.004 cm2. Certified by "
    "European Solar Test Installation (ESTI)."
)

sam_challenge = setting(
    "Self-assembled monolayers (SAMs) serve as hole-selective layers in "
    "inverted PSCs. Symmetric SAMs like Me-4PACz and MeO-4PACz have limited "
    "coverage on TCO substrates and non-optimal interaction with perovskites, "
    "constraining tandem device performance."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
certified_34_58 = claim(
    "Perovskite/silicon tandem solar cells using asymmetric SAM HTL201 "
    "achieve a certified PCE of 34.58% (ESTI certification) with Voc of "
    "nearly 2.00 V, representing a record efficiency for perovskite/silicon "
    "tandem solar cells",
    title="certified_34_58_percent",
    prior=0.92,
)

champion_34_60 = claim(
    "The champion tandem device achieves an in-house PCE of 34.60% with Voc "
    "of 2.001 V, Jsc of 20.64 mA cm-2, and FF of 83.79%",
    title="champion_34_60_percent",
    prior=0.88,
)

asymmetric_sam_htl201 = claim(
    "An asymmetric self-assembled monolayer (HTL201) featuring an anchoring "
    "group and spacer flanking a carbazole core shows minimized steric "
    "hindrance and improved coverage on IZO recombination layer compared "
    "to symmetric SAMs (Me-4PACz, MeO-4PACz)",
    title="asymmetric_sam_htl201",
    prior=0.85,
)

enhanced_coverage = claim(
    "HTL201 forms denser monolayer coverage on IZO substrates than Me-4PACz "
    "and MeO-4PACz, with higher coverage factor confirmed by XPS and "
    "molecular dynamics simulations showing stronger adsorption energy",
    title="enhanced_sam_coverage",
    prior=0.82,
)

buried_interface_passivation = claim(
    "Strong coordination interaction between HTL201 and perovskite film "
    "effectively reduces non-radiative recombination at the buried interface, "
    "achieving PLQY of 0.399% (versus 0.346% for Me-4PACz) and QFLS of "
    "1.270 V on textured silicon substrates",
    title="buried_interface_passivation",
    prior=0.82,
)

voc_near_2v = claim(
    "The optimized energy-level alignment between perovskite and HTL201 "
    "enables Voc approaching 2.00 V for perovskite/silicon tandems, among "
    "the highest reported voltages for this architecture",
    title="voc_near_2_volts",
    prior=0.85,
)

carrier_lifetime_5860ns = claim(
    "Perovskite films on HTL201 show carrier lifetime of 5,860 ns versus "
    "5,574 ns on Me-4PACz and 1,813 ns on MeO-4PACz, indicating lower "
    "trap density at the buried interface",
    title="carrier_lifetime_5860_ns",
    prior=0.82,
)

avg_pce_34_22 = claim(
    "Devices using HTL201 achieve an average PCE of 34.22% across 20 "
    "devices, compared with 32.18% for Me-4PACz and 33.34% for MeO-4PACz",
    title="avg_pce_34_22_percent",
    prior=0.85,
)

asymmetric_design_general = claim(
    "The asymmetric molecular design strategy is generally successful: "
    "HTL201-like derivatives HTL207 (n=2) and HTL203 (n=4) also deliver "
    "higher efficiency than Me-4PACz and MeO-4PACz, with HTL201 being "
    "optimal",
    title="asymmetric_design_general",
    prior=0.78,
)

delayed_crystallization = claim(
    "HTL201-coated substrates delay perovskite nucleation and crystallization "
    "(nucleation at 540 s vs 180 s for Me-4PACz), effectively improving "
    "perovskite film quality and (100) plane orientation",
    title="delayed_crystallization",
    prior=0.78,
)

mppt_stability_25c = claim(
    "Encapsulated HTL201-based tandem devices show stable MPP tracking at "
    "25 C under continuous 1-sun illumination, demonstrating promising "
    "operational stability",
    title="mppt_stability_25c",
    prior=0.70,
)

mppt_stability_45c = claim(
    "Encapsulated HTL201-based tandem devices show degraded but still "
    "functional MPP tracking at 45 C, indicating thermal sensitivity of "
    "perovskite/Si tandems requires further improvement",
    title="mppt_stability_45c",
    prior=0.65,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [asymmetric_sam_htl201, enhanced_coverage, buried_interface_passivation],
    voc_near_2v,
    reason="Denser SAM coverage reduces pinholes and interfacial defects, "
    "while strong coordination between HTL201 and perovskite passivates "
    "buried interface traps, together enabling higher QFLS and Voc",
    prior=0.468,
)

support(
    [voc_near_2v, carrier_lifetime_5860ns, avg_pce_34_22],
    certified_34_58,
    reason="Near-2V Voc combined with high carrier lifetime and consistent "
    "device performance yields record certified tandem efficiency",
    prior=0.492,
)

support(
    [delayed_crystallization, enhanced_coverage],
    carrier_lifetime_5860ns,
    reason="Delayed crystallization produces larger grains and higher "
    "crystallinity, while dense SAM coverage minimizes interfacial defects, "
    "both contributing to longer carrier lifetime",
    prior=0.432,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [certified_34_58, champion_34_60],
    p_efficiency,
    reason="34.58% certified PCE represents the record efficiency for "
    "perovskite/silicon tandems, approaching the practical efficiency limit "
    "for two-junction devices and confirming perovskite PV's potential to "
    "exceed silicon-only performance",
    prior=0.51,
)

support(
    [certified_34_58],
    p_improvement,
    reason="Progression from 33.89% (Hou et al. 2024) to 34.58% certified "
    "in less than one year shows continuous rapid improvement in tandem "
    "technology through interface engineering",
    prior=0.48,
)

support(
    [mppt_stability_25c, avg_pce_34_22],
    p_viability,
    reason="Average PCE of 34.22% across 20 devices combined with MPP "
    "stability demonstrates reproducible high-performance tandem technology",
    prior=0.42,
)

support(
    [asymmetric_design_general, avg_pce_34_22],
    p_industrialization,
    reason="SAM-based hole-selective layers are scalable, dopant-free, "
    "low-cost and compatible with textured silicon wafers, supporting "
    "industrial tandem cell manufacturing",
    prior=0.42,
)

__all__ = [
    "exp_context",
    "sam_challenge",
    "certified_34_58",
    "champion_34_60",
    "asymmetric_sam_htl201",
    "enhanced_coverage",
    "buried_interface_passivation",
    "voc_near_2v",
    "carrier_lifetime_5860ns",
    "avg_pce_34_22",
    "asymmetric_design_general",
    "delayed_crystallization",
    "mppt_stability_25c",
    "mppt_stability_45c",
]
