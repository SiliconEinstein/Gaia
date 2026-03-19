#import "../../../../libs/typst/gaia-lang/v2.typ": *

#include "motivation.typ"
#include "laws.typ"
#include "observations.typ"
#include "derivation.typ"
#include "follow_up.typ"

#package("newton_principia",
  modules: ("motivation", "axioms", "observations", "derivation", "follow_up"),
  export: (
    "freefall_acceleration_equals_g",
    "law_of_gravity",
    "mass_equivalence",
    "follow_up_question",
  ),
)

#export-graph()
