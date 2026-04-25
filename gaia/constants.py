"""Gaia-blessed physical constants as unit-bearing quantities."""

from gaia.unit import ureg

# Fundamental constants
speed_of_light = c = (1 * ureg.speed_of_light).to("m/s")
planck = h = (1 * ureg.planck_constant).to("J*s")
hbar = (1 * ureg.hbar).to("J*s")
boltzmann = k_B = (1 * ureg.boltzmann_constant).to("J/K")
elementary_charge = e = (1 * ureg.elementary_charge).to("C")

# Gravitation
gravitational_constant = G = (1 * ureg.gravitational_constant).to("m^3/(kg*s^2)")
standard_gravity = g_0 = (1 * ureg.standard_gravity).to("m/s^2")

# Thermodynamics
avogadro = N_A = (1 * ureg.N_A).to("1/mol")
molar_gas_constant = R = (1 * ureg.molar_gas_constant).to("J/(mol*K)")
stefan_boltzmann = sigma_SB = (1 * ureg.stefan_boltzmann_constant).to(
    "W/(m^2*K^4)"
)

# Electromagnetism
vacuum_permittivity = eps_0 = (1 * ureg.vacuum_permittivity).to("F/m")
vacuum_permeability = mu_0 = (1 * ureg.vacuum_permeability).to("N/A^2")

# Particle masses
electron_mass = m_e = (1 * ureg.electron_mass).to("kg")
proton_mass = m_p = (1 * ureg.proton_mass).to("kg")
neutron_mass = m_n = (1 * ureg.neutron_mass).to("kg")

__all__ = [
    "G",
    "N_A",
    "R",
    "avogadro",
    "boltzmann",
    "c",
    "e",
    "electron_mass",
    "elementary_charge",
    "eps_0",
    "g_0",
    "gravitational_constant",
    "h",
    "hbar",
    "k_B",
    "m_e",
    "m_n",
    "m_p",
    "molar_gas_constant",
    "mu_0",
    "neutron_mass",
    "planck",
    "proton_mass",
    "sigma_SB",
    "speed_of_light",
    "standard_gravity",
    "stefan_boltzmann",
    "vacuum_permeability",
    "vacuum_permittivity",
]
