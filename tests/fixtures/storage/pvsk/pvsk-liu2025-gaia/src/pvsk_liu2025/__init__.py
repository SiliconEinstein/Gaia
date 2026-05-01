"""Liu et al. Nature 2025 — All-perovskite tandem solar cells with dipolar
passivation achieving 30.6% PCE (certified stabilized 30.1%)."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_viability, p_efficiency, p_improvement, p_stability

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "All-perovskite tandem solar cells with WBG (~1.78 eV) FA0.8Cs0.2Pb"
    "(I0.62Br0.38)3 top cell and NBG (~1.25 eV) Pb-Sn perovskite bottom "
    "cell. Device areas 0.049 cm2 and 1.05 cm2. Certified by JET (Japan "
    "Electrical Safety and Environment Technology Laboratories). "
    "PEDOT:PSS HTL with sulfanilic acid (SA) dipolar passivation."
)

buried_interface_problem = setting(
    "Deep-level traps at the buried perovskite/HTL interface in mixed Pb-Sn "
    "NBG subcells cause severe non-radiative recombination. Conventional "
    "long-chain amine passivation improves Voc but impairs charge transport, "
    "reducing Jsc and FF due to insulating barriers."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
dipolar_passivation_strategy = claim(
    "A dipolar-passivation strategy using sulfanilic acid (SA) at the "
    "HTL/Pb-Sn perovskite interface reduces trap density while enabling "
    "precise energy-level alignment through oriented dipoles, simultaneously "
    "suppressing recombination and enhancing carrier extraction",
    title="dipolar_passivation_strategy",
    prior=0.85,
)

nbg_pce_249 = claim(
    "Dipolar-passivated Pb-Sn PSCs achieve 24.9% PCE with Voc of 0.911 V, "
    "Jsc of 33.1 mA cm-2, and FF of 82.6%, representing one of the highest "
    "reported PCEs for mixed Pb-Sn PSCs",
    title="nbg_pce_24_9_percent",
    prior=0.88,
)

tandem_pce_306 = claim(
    "All-perovskite tandem solar cells with dipolar passivation achieve "
    "30.6% PCE (certified stabilized 30.1% by JET) for 0.049 cm2 area",
    title="tandem_pce_30_6_percent",
    prior=0.90,
)

large_tandem_296 = claim(
    "Large-area all-perovskite tandem (1.05 cm2) achieves certified "
    "stabilized PCE of 29.6%, demonstrating scalability",
    title="large_tandem_29_6_percent",
    prior=0.88,
)

diffusion_length_62um = claim(
    "Dipolar passivation extends carrier diffusion length to 6.2 um "
    "(versus 4.8 um for control) with mobility of 113.5 cm2 V-1 s-1 "
    "(versus 67.5 cm2 V-1 s-1), as measured by terahertz spectroscopy",
    title="diffusion_length_6_2_um",
    prior=0.85,
)

ohmic_contact = claim(
    "The oriented SA dipoles create type-II energy-level alignment with "
    "ohmic contact at the HTL/Pb-Sn perovskite interface, facilitating "
    "efficient hole injection into PEDOT:PSS while repelling electrons "
    "from the interface",
    title="ohmic_contact_dipolar",
    prior=0.82,
)

elqy_705 = claim(
    "Dipolar-passivation devices show electroluminescence quantum yield of "
    "7.05% versus 2.40% for controls at 1-sun current density, corresponding "
    "to Voc loss reduction from 103 mV to 73 mV",
    title="elqy_7_05_percent",
    prior=0.85,
)

dark_storage_1000h = claim(
    "Dipolar-passivated devices show no significant PCE degradation after "
    "over 1000 hours in a nitrogen glovebox without encapsulation",
    title="dark_storage_1000h",
    prior=0.78,
)

sa_molecular_orientation = claim(
    "SA molecules adopt a preferred orientation with -NH3+ anchoring to the "
    "perovskite bottom surface and -SO3- directed towards PEDOT:PSS, "
    "confirmed by AIMD simulations and KPFM measurements showing surface "
    "potential decrease from -80 mV to -162 mV",
    title="sa_molecular_orientation",
    prior=0.82,
)

tandem_voc_50mv_gain = claim(
    "Dipolar-passivation tandem devices show average Voc 50 mV higher than "
    "controls, with average PCE of 30.3 +/- 0.3% versus 29.1 +/- 0.2%",
    title="tandem_voc_50mv_gain",
    prior=0.85,
)

wbg_subcell_205 = claim(
    "The wide-bandgap subcell achieves 20.5% PCE with Voc of 1.329 V, Jsc "
    "of 18.4 mA cm-2, and FF of 83.8%, using SAM-modified NiO HTL",
    title="wbg_subcell_20_5_percent",
    prior=0.82,
)

qfls_improvement = claim(
    "Dipolar passivation improves QFLS from 904 meV to 940 meV at the "
    "HTL/perovskite interface (full device stack), with the primary QFLS "
    "loss reduction attributed to enhanced HTL interface quality",
    title="qfls_improvement_dipolar",
    prior=0.82,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [sa_molecular_orientation, ohmic_contact],
    dipolar_passivation_strategy,
    reason="Oriented SA dipoles simultaneously passivate defects (NH3+ "
    "anchors to perovskite) and create favorable energy alignment (SO3- "
    "towards HTL), resolving the recombination-transport trade-off",
    prior=0.48,
)

support(
    [dipolar_passivation_strategy, diffusion_length_62um, elqy_705],
    nbg_pce_249,
    reason="Type-II energy alignment with ohmic contact enables efficient "
    "carrier extraction (6.2 um diffusion length) while oriented dipoles "
    "suppress non-radiative recombination (7% ELQY), yielding record "
    "Pb-Sn single-junction efficiency",
    prior=0.48,
)

support(
    [nbg_pce_249, tandem_voc_50mv_gain, wbg_subcell_205],
    tandem_pce_306,
    reason="Improved NBG subcell performance (higher Voc and FF from "
    "dipolar passivation) combined with a 20.5% WBG subcell enables "
    "all-perovskite tandem to surpass 30% PCE",
    prior=0.48,
)

support(
    [tandem_pce_306],
    large_tandem_296,
    reason="The dipolar passivation strategy is robust and scalable, "
    "maintaining high performance at 1.05 cm2 area with only 1% PCE loss",
    prior=0.45,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [tandem_pce_306, large_tandem_296],
    p_efficiency,
    reason="30.6% PCE (certified 30.1%) is the record for all-perovskite "
    "tandems, demonstrating that this architecture can surpass 30% and "
    "competes with perovskite/Si tandems in efficiency",
    prior=0.51,
)

support(
    [tandem_pce_306, nbg_pce_249],
    p_improvement,
    reason="Progression from 28.5% (Lin et al. 2023) to 30.6% certified "
    "all-perovskite tandem efficiency in two years demonstrates continued "
    "rapid improvement through interface engineering innovations",
    prior=0.48,
)

support(
    [dark_storage_1000h],
    p_stability,
    reason="1000 hours of stable dark storage without encapsulation shows "
    "improved material stability from dipolar passivation",
    prior=0.36,
)

support(
    [large_tandem_296, dipolar_passivation_strategy],
    p_viability,
    reason="All-perovskite tandems offer a fully solution-processable, "
    "low-cost alternative to perovskite/Si tandems with competitive "
    "efficiency approaching 30% at cm2 scale",
    prior=0.42,
)

__all__ = [
    "exp_context",
    "buried_interface_problem",
    "dipolar_passivation_strategy",
    "nbg_pce_249",
    "tandem_pce_306",
    "large_tandem_296",
    "diffusion_length_62um",
    "ohmic_contact",
    "elqy_705",
    "dark_storage_1000h",
    "sa_molecular_orientation",
    "tandem_voc_50mv_gain",
    "wbg_subcell_205",
    "qfls_improvement",
]
