#import "../../../../libs/typst/gaia-lang/lib.typ": *
#include "motivation.typ"
#include "setting.typ"
#include "aristotle.typ"
#include "reasoning.typ"
#include "follow_up.typ"

#package("galileo_falling_bodies",
  modules: ("motivation", "setting", "aristotle", "reasoning", "follow_up"),
  export: (
    "vacuum_prediction",
    "tied_balls_contradiction",
    "follow_up_question",
  ),
)

#export-graph()
