#import "gaia.typ": *

= Observational Evidence

#claim(kind: "observation")[
  Type Ia supernovae data shows the universe's expansion is accelerating.
] <sn_observation>

#claim(kind: "observation")[
  CMB anisotropy data is consistent with a flat universe model.
] <cmb_data>

#action(kind: "python", from: (<sn_observation>,))[
  MCMC fitting of Type Ia supernovae data using emcee
  to obtain the posterior distribution of the dark energy density parameter.
] <mcmc_fit>
