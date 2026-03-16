#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("aristotle", title: "亚里士多德学说 — 即将被挑战的先验知识")

#claim("heavier_falls_faster")[
  重的物体比轻的物体下落得更快。
  下落速度与重量成正比。
]

#claim("everyday_observation")[
  在日常空气环境中，从同一高度落下时，石头通常比羽毛更早落地；
  重物看起来往往比轻物下落得更快。
]

#chain("inductive_support")[
  #claim("inductive_step",
    premise: ("everyday_observation",),
  )[
    日常经验反复呈现"重物先落地、轻物后落地"的现象，
    如果不区分空气阻力等外在因素，人们很自然会把这种表象
    归纳成一条普遍规律：重量越大，下落越快。
  ]
]
