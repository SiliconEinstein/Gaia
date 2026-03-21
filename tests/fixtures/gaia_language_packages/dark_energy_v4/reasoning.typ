#import "gaia.typ": *

= Main Result

#claim(from: (<sn_observation>, <cmb_data>, <flat_universe>, <gr_valid>))[
  Dark energy accounts for approximately 68% of the total energy density of the universe.
][
  Based on independent observations from @sn_observation and @cmb_data,
  under the assumptions of @flat_universe and @gr_valid,
  the Friedmann equations constrain the dark energy fraction to approximately 68%.
] <dark_energy_fraction>

#claim[
  Quantum field theory predicts a vacuum energy density roughly 120 orders of magnitude
  larger than the observed dark energy density.
] <qft_vacuum_energy>

#relation(type: "contradiction", between: (<dark_energy_fraction>, <qft_vacuum_energy>))[
  The cosmological constant interpretation of dark energy differs from
  quantum field theory's vacuum energy prediction by 120 orders of magnitude.
] <vacuum_catastrophe>

#gaia-bibliography(yaml("gaia-deps.yml"))

#claim(from: (<dark_energy_fraction>, <prior_cmb_analysis>))[
  The dark energy fraction is consistent with independent CMB power spectrum analysis.
] <cross_validation>
