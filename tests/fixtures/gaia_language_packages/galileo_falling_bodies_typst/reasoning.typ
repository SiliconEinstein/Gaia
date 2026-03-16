#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("reasoning", title: "核心推理 — 伽利略的论证")

// ── references ──
#use("aristotle.heavier_falls_faster")
#use("aristotle.everyday_observation")
#use("setting.thought_experiment_env")
#use("setting.vacuum_env")

// ── independent knowledge ──
#claim("medium_density_observation")[
  在水、油、空气等不同介质中比较轻重物体的下落，
  会发现介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。
]

#claim("inclined_plane_observation")[
  伽利略的斜面实验把下落过程放慢到可测量尺度后显示：
  不同重量的小球在相同斜面条件下呈现近似一致的加速趋势，
  与"重量越大速度越大"的简单比例律并不相符。
]

// ── chain: 绑球矛盾论证 ──
#chain("tied_balls_argument")[
  #claim("tied_pair_slower",
    premise: ("heavier_falls_faster", "thought_experiment_env"),
  )[
    在思想实验环境中暂时接受亚里士多德定律：
    轻球天然比重球下落更慢。于是当轻球与重球绑在一起时，
    轻球应当拖慢重球，复合体 HL 的下落速度应慢于单独的重球 H。
  ]

  #claim("tied_pair_faster",
    premise: ("heavier_falls_faster", "thought_experiment_env"),
  )[
    按照"重量越大，下落越快"的同一条定律，
    被绑在一起后的复合体 HL 总重量大于单独的重球 H，
    因而它又应当比 H 下落更快。
  ]

  #contradiction("tied_balls_contradiction",
    premise: ("tied_pair_slower", "tied_pair_faster"),
  )[
    同一定律对同一绑球系统同时预测"更慢"和"更快"，自相矛盾。
    亚里士多德落体定律因绑球矛盾而不能成立。
  ]
]

// ── chain: 介质消除论证 ──
#chain("medium_elimination")[
  #claim("medium_difference_shrinks",
    premise: ("medium_density_observation",),
  )[
    如果从水到空气，随着介质变稀薄，轻重物体的速度差异持续缩小，
    那么这种差异更像是外部阻力效应，而不是重量本身对自由落体速度的直接支配。
  ]

  #claim("air_resistance_is_confound",
    premise: ("everyday_observation",),
  )[
    由此可知，日常观察到的速度差异更应被解释为介质阻力造成的表象，
    而不是重量本身决定自由落体速度的证据。
  ]
]

// ── chain: 最终预测 ──
#chain("synthesis")[
  #claim("inclined_plane_supports_equal_fall",
    premise: ("inclined_plane_observation",),
  )[
    斜面实验把自由落体减慢到可测量尺度后，
    显示不同重量的小球获得近似一致的加速趋势，
    支持"重量不是决定落体快慢的首要因素"。
  ]

  #claim("vacuum_prediction",
    premise: ("tied_balls_argument", "medium_elimination", "inclined_plane_supports_equal_fall"),
    ctx: ("vacuum_env",),
  )[
    综合以上三条线索：绑球矛盾推翻旧定律、介质分析排除干扰因素、
    斜面实验提供正面支持——在真空中，
    不同重量的物体应以相同速率下落。
  ]
]
