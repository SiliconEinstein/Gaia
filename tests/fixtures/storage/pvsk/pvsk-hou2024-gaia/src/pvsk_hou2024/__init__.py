"""Hou et al. Nature 2024 — Perovskite/silicon tandem solar cells with
bilayer interface passivation achieving 33.89% certified PCE, the first
two-junction tandem exceeding the single-junction Shockley-Queisser limit."""

from gaia.lang import claim, setting, support
from pvsk_meta import p_efficiency, p_improvement, p_stability, p_industrialization

# ---------------------------------------------------------------------------
# Background settings
# ---------------------------------------------------------------------------
exp_context = setting(
    "Two-terminal monolithic perovskite/silicon tandem solar cells built on "
    "double-side-textured Czochralski-based silicon heterojunction cells. "
    "Perovskite bandgap 1.69 eV. Inverted p-i-n configuration. Device area "
    "1.0 cm2. NREL-certified performance."
)

asymmetric_texture = setting(
    "The silicon bottom cell uses asymmetrically sized textures: mildly "
    "textured front surface (0.5-1 um pyramids) for solution-processed "
    "perovskite coverage, and heavily textured rear surface (>3 um pyramids) "
    "for uncompromised rear passivation and improved infrared response."
)

# ---------------------------------------------------------------------------
# Core claims
# ---------------------------------------------------------------------------
certified_33_89 = claim(
    "The perovskite/silicon tandem achieves an independently certified "
    "stabilized PCE of 33.89% with FF of 83.0% and Voc of nearly 1.97 V, "
    "the first double-junction tandem exceeding the single-junction "
    "Shockley-Queisser limit of 33.7%",
    title="certified_33_89_percent",
    prior=0.92,
)

champion_34_1 = claim(
    "The champion tandem cell achieves an in-house PCE of 34.1% with Jsc of "
    "20.68 mA cm-2, Voc of 1.980 V, and FF of 83.2%",
    title="champion_pce_34_1_percent",
    prior=0.88,
)

bilayer_passivation = claim(
    "A bilayer interface passivation strategy combining nanoscale discretely "
    "distributed LiF ultrathin layer with diammonium diiodide (EDAI) molecule "
    "achieves optimal trade-off between passivation and charge extraction at "
    "the perovskite/C60 interface",
    title="bilayer_lif_edai_passivation",
    prior=0.85,
)

edai_chemical_passivation = claim(
    "EDAI molecules chemically passivate uncoordinated Pb2+ surface defects "
    "by forming coordinate bonds, eliminating metallic Pb(0) peaks observed "
    "in XPS, while LiF alone does not provide this chemical passivation",
    title="edai_chemical_passivation",
    prior=0.82,
)

intertwined_structure = claim(
    "The LiF and EDAI layers are intertwined at the nanoscale: the "
    "discontinuous LiF layer allows EDAI to locally contact the perovskite "
    "surface, creating nanoscale localized contacts that balance electron "
    "tunnelling (through LiF) with direct transport (through EDAI/C60)",
    title="intertwined_nanocale_contacts",
    prior=0.80,
)

asymmetric_texture_benefit = claim(
    "The asymmetrically textured silicon wafer (small front pyramids, large "
    "rear pyramids) preserves minority carrier lifetime of 3.4 ms (comparable "
    "to 3.2 ms for standard double-sided texture) and improves infrared "
    "EQE response compared with double-sided mild texture",
    title="asymmetric_texture_benefit",
    prior=0.82,
)

voc_progression = claim(
    "The bilayer passivation improves average Voc from below 1.90 V "
    "(unpassivated) to 1.96 V (LiF/EDAI), and FF from 76.2% to 80.8% for "
    "single-junction perovskite devices",
    title="voc_ff_progression_passivation",
    prior=0.85,
)

storage_stability = claim(
    "Devices with LiF/EDAI bilayer passivation retain approximately 90% of "
    "original PCE after 53 days of air storage, compared with 82% for "
    "LiF-treated control devices",
    title="storage_stability_90_percent_53d",
    prior=0.78,
)

mppt_stability_1200h = claim(
    "The bilayer-treated tandem retains approximately 80% of initial PCE "
    "after 1200 hours of MPP tracking under simulated 1-sun at room "
    "temperature, compared with less than 60% for LiF-treated control",
    title="mppt_stability_1200h",
    prior=0.78,
)

average_pce_33 = claim(
    "The bilayer-treated tandem devices achieve an average PCE exceeding 33% "
    "with some devices reaching above 33.8%, demonstrating excellent "
    "reproducibility at 1 cm2 scale",
    title="average_pce_exceeding_33",
    prior=0.82,
)

sq_limit_breakthrough = claim(
    "This work represents the first reported certified efficiency of a "
    "two-junction tandem solar cell exceeding the single-junction "
    "Shockley-Queisser limit of 33.7%, confirming the fundamental advantage "
    "of multi-junction architectures",
    title="sq_limit_breakthrough",
    prior=0.88,
)

dft_binding_energy = claim(
    "DFT calculations show EDA2+ has binding energies of -6.6 and -8.4 eV on "
    "FAI-rich and PbI2-rich FAPbI3 surfaces respectively, substantially "
    "larger than monoammonium PA+, and adopts a horizontal bridge-like "
    "configuration that maximizes out-of-plane charge transport",
    title="dft_binding_energy_eda",
    prior=0.80,
)

# ---------------------------------------------------------------------------
# Internal reasoning
# ---------------------------------------------------------------------------
support(
    [edai_chemical_passivation, intertwined_structure],
    bilayer_passivation,
    reason="LiF provides field passivation and contact displacement while "
    "EDAI fills the gaps with chemical passivation, together achieving both "
    "suppressed recombination and efficient electron extraction",
    prior=0.48,
)

support(
    [bilayer_passivation, asymmetric_texture_benefit, voc_progression],
    certified_33_89,
    reason="Bilayer passivation maximizes Voc and FF while asymmetric texture "
    "optimizes both perovskite coverage and silicon infrared response, "
    "enabling PCE beyond the single-junction SQ limit",
    prior=0.492,
)

support(
    [certified_33_89],
    sq_limit_breakthrough,
    reason="The 33.89% certified efficiency exceeds 33.7%, confirming the "
    "tandem architecture can surpass the fundamental single-junction limit",
    prior=0.51,
)

support(
    [bilayer_passivation],
    storage_stability,
    reason="EDAI passivation stabilizes the perovskite surface composition by "
    "eliminating metallic Pb(0) defects, improving ambient stability",
    prior=0.42,
)

# ---------------------------------------------------------------------------
# Connections to meta propositions
# ---------------------------------------------------------------------------
support(
    [certified_33_89, champion_34_1, sq_limit_breakthrough],
    p_efficiency,
    reason="33.89% certified PCE surpasses the single-junction SQ limit and "
    "represents the highest certified efficiency for any two-junction solar "
    "cell at the time, demonstrating the ultimate efficiency potential of "
    "perovskite-based photovoltaics",
    prior=0.51,
)

support(
    [certified_33_89],
    p_improvement,
    reason="Progression from sub-30% to 33.89% certified efficiency for "
    "perovskite/Si tandems in under 3 years demonstrates extremely rapid "
    "improvement in tandem technology",
    prior=0.48,
)

support(
    [storage_stability, mppt_stability_1200h],
    p_stability,
    reason="1200 hours of MPP tracking with 80% retention and 53-day air "
    "storage stability at 90% retention show improving operational lifetime",
    prior=0.39,
)

support(
    [asymmetric_texture_benefit, average_pce_33],
    p_industrialization,
    reason="The use of industrial CZ silicon wafers, solution-processed "
    "perovskite, and average PCE >33% at 1 cm2 demonstrates compatibility "
    "with commercial silicon manufacturing",
    prior=0.42,
)

__all__ = [
    "exp_context",
    "asymmetric_texture",
    "certified_33_89",
    "champion_34_1",
    "bilayer_passivation",
    "edai_chemical_passivation",
    "intertwined_structure",
    "asymmetric_texture_benefit",
    "voc_progression",
    "storage_stability",
    "mppt_stability_1200h",
    "average_pce_33",
    "sq_limit_breakthrough",
    "dft_binding_energy",
]
