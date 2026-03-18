#import "../../../../libs/typst/gaia-lang/v2.typ": *

#include "motivation.typ"
#include "setting.typ"
#include "aristotle.typ"
#include "galileo.typ"
#include "follow_up.typ"

#package("galileo_falling_bodies",
  modules: ("motivation", "setting", "aristotle", "galileo", "follow_up"),
  export: (
    "vacuum_prediction",
    "tied_balls_contradiction",
    "follow_up_question",
  ),
)

#export-graph()
