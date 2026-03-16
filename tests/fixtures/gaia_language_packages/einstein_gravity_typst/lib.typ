#import "../../../../libs/typst/gaia-lang/lib.typ": *
#include "prior_knowledge.typ"
#include "equivalence_principle.typ"
#include "general_relativity.typ"
#include "observation.typ"

#package("einstein_gravity",
  modules: ("prior_knowledge", "equivalence_principle", "general_relativity", "observation"),
  export: (
    "gr_light_deflection",
    "newton_subsumed_by_gr",
    "three_path_convergence",
  ),
)

#export-graph()
