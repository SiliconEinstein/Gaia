#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("follow_up", title: "后续问题 — 未来研究")

#use("reasoning.vacuum_prediction")

#chain("next_steps")[
  #question("follow_up_question",
    premise: ("vacuum_prediction",),
  )[
    能否在足够接近真空的条件下直接比较重球与轻球的下落时间？
    如果日常差异确实来自空气阻力，那么真正决定性的实验应当在
    几乎无介质的环境中完成。
  ]
]
