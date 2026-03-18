#import "../../../../libs/typst/gaia-lang/v2.typ": *

#module("aristotle", title: "亚里士多德学说 — 即将被挑战的先验知识")

#observation("everyday_observation")[
  在日常空气环境中，从同一高度落下时，
  石头通常比羽毛更早落地；重物看起来往往比轻物下落得更快。
]

#claim("heavier_falls_faster")[
  重的物体比轻的物体下落得更快。下落速度与重量成正比。
][
  #premise("everyday_observation")

  #by_induction[
    从日常观察中，重物总是比轻物先落地。
    亚里士多德将这一有限的、存在空气阻力干扰的经验现象，
    直接推广为普适的物理定律。
  ]
]
