#import "../../../../libs/typst/gaia-lang/v2.typ": *

#module("galileo", title: "伽利略的论证")

// ── Cross-module imports ──
#use("aristotle.heavier_falls_faster")
#use("aristotle.everyday_observation")
#use("setting.thought_experiment_env")
#use("setting.vacuum_env")

// ── Observations (no proof needed) ──
#observation("medium_density_observation")[
  在水、油、空气等不同介质中比较轻重物体的下落，
  会发现介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。
]

#observation("inclined_plane_observation")[
  伽利略的斜面实验把下落过程放慢到可测量尺度后显示：
  不同重量的小球在相同斜面条件下呈现近似一致的加速趋势，
  与"重量越大速度越大"的简单比例律并不相符。
]

// ── Tied balls contradiction ──
#claim("tied_balls_contradiction")[
  在假设"重者下落更快"的前提下，
  绑球系统同时被预测为更快和更慢，产生矛盾。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")

  #derive("tied_pair_slower")[
    由"重者下落更快"的假设，轻球天然比重球慢。
    在思想实验环境中，轻球应拖慢重球，
    复合体 HL 的下落速度应慢于单独的重球 H。
  ]
  #derive("tied_pair_faster")[
    但按"重者下落更快"的同一定律，
    复合体 HL 总重量大于 H，应比 H 更快。
  ]
  #contradict("tied_pair_slower", "tied_pair_faster")
]

// ── Medium elimination ──
#claim("air_resistance_is_confound")[
  日常观察到的速度差异更应被解释为介质阻力造成的表象，
  而不是重量本身决定自由落体速度的证据。
][
  #premise("medium_density_observation")

  #derive("medium_difference_shrinks")[
    从水到空气，随着介质变稀薄，轻重物体的速度差异持续缩小，
    说明 @everyday-observation 中的现象更像是外部阻力效应，
    而非重量本身的作用。
  ]
]

// ── Final synthesis ──
#claim("vacuum_prediction")[
  在真空中，不同重量的物体应以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("air_resistance_is_confound")
  #premise("inclined_plane_observation")

  #derive("inclined_plane_supports")[
    斜面实验显示不同重量的小球获得近似一致的加速趋势，
    支持"重量不是决定落体快慢的首要因素"。
  ]

  综合三条线索：绑球矛盾推翻旧定律、
  介质分析排除干扰因素、斜面实验提供正面支持。
  在真空环境下，结论成立。
]
