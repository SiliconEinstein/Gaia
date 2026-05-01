"""Gu et al. Nat Energy 2023 — Bifacial perovskite minimodules with front
efficiency comparable to monofacial counterparts and 6000-hour stability."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_viability, p_efficiency, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Bifacial perovskite minimodules using p-i-n architecture with PTAA/C60 "
    "as HTL/ETL. Perovskite compositions MA0.7FA0.3PbI3 and FA0.92Cs0.08PbI3. "
    "Aperture areas of 14.3-25.1 cm2. ITO rear electrode with Ag grids, "
    "ALD SnO2 buffer layer. Blade-coated at room temperature in ambient air."
)

bifacial_advantage = setting(
    "Bifacial modules harvest reflected and diffused sunlight from the rear "
    "side, gaining 5-30% more power than monofacial modules depending on "
    "albedo. Average albedo of 0.2 or higher is common in many locations."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
bifacial_front_20 = claim(
    "Bifacial perovskite minimodules achieve a front aperture efficiency of "
    "20.2% and rear aperture efficiency of 15.0%, with NREL-certified "
    "stabilized front efficiency of 19.2% and rear efficiency of 14.1%",
    title="bifacial_minimodule_20_front",
    prior=0.88,
)

power_generation_density = claim(
    "Bifacial minimodules achieve a power-generation density of over "
    "23 mW cm-2 at albedo of 0.2, higher than the best certified monofacial "
    "modules, and up to 24.7 mW cm-2 at albedo of 0.3",
    title="bifacial_pgd_23_mw",
    prior=0.85,
)

small_cell_264_pgd = claim(
    "Small-area single-junction bifacial PSCs achieve a power-generation "
    "density of 26.4 mW cm-2 under 1 sun and albedo of 0.2",
    title="small_cell_264_pgd",
    prior=0.85,
)

light_soaking_6000h = claim(
    "Bifacial minimodules retain 97% of initial PCE after over 6000 hours "
    "of light soaking under 1 sun at 60+/-5 C, the most stable reported "
    "perovskite minimodule at the time of publication",
    title="light_soaking_6000h_t97",
    prior=0.88,
)

damp_heat_1000h = claim(
    "Bifacial minimodules maintain approximately 84% of initial efficiency "
    "after damp-heat testing for over 1000 hours (85 C, 85% RH)",
    title="damp_heat_1000h_84_percent",
    prior=0.80,
)

tpfb_moisture_protection = claim(
    "Adding hydrophobic tris(pentafluorophenyl)borane (TPFB) to the PTAA "
    "hole transport layer spreads to the perovskite surface and significantly "
    "enhances moisture resistance during ALD processing, improving device "
    "reproducibility for large-area modules",
    title="tpfb_moisture_protection",
    prior=0.80,
)

sio2_np_scattering = claim(
    "Embedding 500 nm SiO2 nanoparticles in perovskite films recovers "
    "absorption loss from the absent reflective metal electrode by scattering "
    "red and NIR light, increasing Jsc by 0.8 mA cm-2 without introducing "
    "additional non-radiative recombination",
    title="sio2_np_light_scattering",
    prior=0.82,
)

ag_grid_optimization = claim(
    "Optimally spaced silver grids (2 mm spacing) on the rear ITO electrode "
    "reduce resistance loss from 8.6% to less than 0.9% while maintaining "
    "bifaciality of 74.3%",
    title="ag_grid_optimization",
    prior=0.80,
)

ald_sno2_stability = claim(
    "ALD SnO2 buffer layer greatly reduces perovskite damage during laser "
    "scribing and stabilizes the C60/BCP interface by replacing the "
    "thermally unstable BCP layer",
    title="ald_sno2_module_stability",
    prior=0.75,
)

bifaciality_74 = claim(
    "Bifacial minimodules achieve a bifaciality of 74.3% and gain 15% more "
    "power output at albedo of 0.2 compared with monofacial modules",
    title="bifaciality_74_percent",
    prior=0.80,
)

module_reproducibility = claim(
    "Across eight bifacial minimodules with Ag grids, average front and rear "
    "aperture efficiencies reach 19.5% and 14.5% respectively, demonstrating "
    "good fabrication reproducibility",
    title="module_reproducibility",
    prior=0.75,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [tpfb_moisture_protection, sio2_np_scattering, ag_grid_optimization],
    bifacial_front_20,
    reason="Three innovations address the key challenges of bifacial modules: "
    "moisture protection (TPFB), light absorption recovery (SiO2 NPs), and "
    "resistance reduction (Ag grids), enabling front efficiency matching "
    "monofacial modules",
    prior=0.468,
)

support(
    [bifacial_front_20, bifaciality_74],
    power_generation_density,
    reason="Combining high front efficiency with good bifaciality yields "
    "power-generation density exceeding monofacial modules",
    prior=0.468,
)

support(
    [ald_sno2_stability, tpfb_moisture_protection],
    light_soaking_6000h,
    reason="ALD SnO2 prevents scribing damage and stabilizes interfaces, "
    "while TPFB enhances moisture resistance, together enabling record "
    "minimodule operational stability",
    prior=0.45,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [bifacial_front_20, power_generation_density],
    p_industrialization,
    reason="Demonstration of large-area (20+ cm2) bifacial minimodules "
    "fabricated by blade coating at room temperature with certified "
    "efficiency validates scalable manufacturing approaches",
    prior=0.45,
)

support(
    [light_soaking_6000h, damp_heat_1000h],
    p_stability,
    reason="6000 hours of light soaking (T97) and 1000 hours of damp-heat "
    "testing demonstrate module-level stability meeting industrial "
    "requirements",
    prior=0.42,
)

support(
    [bifacial_front_20, small_cell_264_pgd],
    p_efficiency,
    reason="Bifacial architecture achieves equivalent front efficiency to "
    "monofacial modules with additional rear-side energy harvesting, "
    "yielding higher effective power-generation density",
    prior=0.42,
)

support(
    [light_soaking_6000h, bifacial_front_20],
    p_viability,
    reason="Simultaneously achieving record minimodule stability and "
    "efficiency demonstrates practical viability of perovskite technology "
    "at the module level",
    prior=0.39,
)

__all__ = [
    "exp_context",
    "bifacial_advantage",
    "bifacial_front_20",
    "power_generation_density",
    "small_cell_264_pgd",
    "light_soaking_6000h",
    "damp_heat_1000h",
    "tpfb_moisture_protection",
    "sio2_np_scattering",
    "ag_grid_optimization",
    "ald_sno2_stability",
    "bifaciality_74",
    "module_reproducibility",
]
