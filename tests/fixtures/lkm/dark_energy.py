"""Dark Energy — complete LKM fixture.

Source: tests/fixtures/gaia_language_packages/dark_energy_v4/

Observational evidence → dark energy fraction, plus the vacuum catastrophe
contradiction with QFT. Cross-package dep on cmb-analysis.
"""

from gaia.lkm.models import Step

from tests.fixtures.lkm._helpers import operator, strategy, var

PACKAGE_ID = "dark_energy"
VERSION = "1.0.0"

_P = PACKAGE_ID


def _qid(label: str) -> str:
    return f"reg:{_P}::{label}"


# ══════════════════════════════════════════════════════════════════════
#  CLAIMS
# ══════════════════════════════════════════════════════════════════════

sn_observation = var(
    "sn_observation",
    "Type Ia supernovae data shows the universe's expansion is accelerating.",
    _P,
)

cmb_data = var(
    "cmb_data",
    "CMB anisotropy data is consistent with a flat universe model.",
    _P,
)

dark_energy_fraction = var(
    "dark_energy_fraction",
    "Dark energy accounts for approximately 68% of the total energy density of the universe.",
    _P,
)

qft_vacuum_energy = var(
    "qft_vacuum_energy",
    "Quantum field theory predicts a vacuum energy density roughly "
    "120 orders of magnitude larger than the observed dark energy density.",
    _P,
)

cross_validation = var(
    "cross_validation",
    "The dark energy fraction is consistent with independent CMB power spectrum analysis.",
    _P,
)

# ══════════════════════════════════════════════════════════════════════
#  SETTINGS
# ══════════════════════════════════════════════════════════════════════

flat_universe = var(
    "flat_universe",
    "The universe is spatially flat on large scales.",
    _P,
    type_="setting",
)

gr_valid = var(
    "gr_valid",
    "General relativity is valid at cosmological scales.",
    _P,
    type_="setting",
)

# ══════════════════════════════════════════════════════════════════════
#  QUESTIONS
# ══════════════════════════════════════════════════════════════════════

main_question = var(
    "main_question",
    "What is the physical nature of dark energy?",
    _P,
    type_="question",
)

# ══════════════════════════════════════════════════════════════════════
#  CROSS-PACKAGE REFERENCE
#  References cmb-analysis::cmb_power_spectrum (external package)
# ══════════════════════════════════════════════════════════════════════

prior_cmb_analysis = var(
    "ext.prior_cmb_analysis",
    "CMB power spectrum analysis from Planck satellite data",
    _P,
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Strategies
# ══════════════════════════════════════════════════════════════════════

f_dark_energy_fraction = strategy(
    "dark_energy_fraction",
    premises=[_qid("sn_observation"), _qid("cmb_data")],
    conclusion=_qid("dark_energy_fraction"),
    background=[_qid("flat_universe"), _qid("gr_valid")],
    package=_P,
    steps=[
        Step(reasoning="SN Ia → accelerating expansion; CMB → flat geometry."),
        Step(reasoning="Flat + accelerating → ~68% dark energy component."),
    ],
)

f_cross_validation = strategy(
    "cross_validation",
    premises=[_qid("dark_energy_fraction"), _qid("ext.prior_cmb_analysis")],
    conclusion=_qid("cross_validation"),
    package=_P,
    steps=[Step(reasoning="Independent CMB analysis confirms the 68% fraction.")],
)

# ══════════════════════════════════════════════════════════════════════
#  FACTORS — Operators
# ══════════════════════════════════════════════════════════════════════

# Vacuum catastrophe: QFT prediction contradicts observed dark energy
f_vacuum_catastrophe = operator(
    "vacuum_catastrophe",
    variables=[_qid("dark_energy_fraction"), _qid("qft_vacuum_energy")],
    conclusion=_qid("qft_vacuum_energy"),
    package=_P,
    subtype="contradiction",
)

# ══════════════════════════════════════════════════════════════════════
#  EXPORTS
# ══════════════════════════════════════════════════════════════════════

LOCAL_VARIABLES = [
    # claims
    sn_observation,
    cmb_data,
    dark_energy_fraction,
    qft_vacuum_energy,
    cross_validation,
    # cross-package ref
    prior_cmb_analysis,
    # settings
    flat_universe,
    gr_valid,
    # questions
    main_question,
]

LOCAL_FACTORS = [
    f_dark_energy_fraction,
    f_cross_validation,
    f_vacuum_catastrophe,
]
