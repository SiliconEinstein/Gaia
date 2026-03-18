#import "../../../../libs/typst/gaia-lang/v2.typ": *

#module("galileo", title: "伽利略的论证")

// ── Cross-module imports ──
#use("aristotle.heavier_falls_faster")
#use("setting.thought_experiment_env")

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

// ── Fine-grained tied-ball decomposition ──
#claim("composite_is_slower")[
  假设"重者下落更快"，将重球（H）与轻球（L）绑成复合体（HL），
  则 HL 的下落速度慢于 H 单独下落。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")

  在"重者更快"假设下 @heavier-falls-faster ，
  考虑绑球思想实验 @thought-experiment-env ：
  轻球 L 的"天然速度"慢于重球 H，绑在一起后 L 起拖拽作用，
  因此复合体 HL 的下落速度应慢于 H 单独下落。
]

#claim("composite_is_faster")[
  假设"重者下落更快"，将重球（H）与轻球（L）绑成复合体（HL），
  则 HL 的下落速度快于 H 单独下落。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")

  同一假设下 @heavier-falls-faster ，
  在绑球思想实验中 @thought-experiment-env ，
  复合体 HL 总质量 = H + L > H，
  按"重者更快"定律，HL 应比 H 下落更快。
]

#claim_relation("tied_balls_contradiction",
  type: "contradiction",
  between: ("composite_is_slower", "composite_is_faster")
)[将重球（H）与轻球（L）绑成复合体（HL），"HL 慢于 H"与"HL 快于 H"两个预测互相矛盾。]

// ── Medium elimination ──
#claim("air_resistance_is_confound")[
  日常观察到的速度差异更应被解释为介质阻力造成的表象，
  而不是重量本身决定自由落体速度的证据。
][
  #premise("medium_density_observation")

  如果速度差异由介质阻力造成，那么介质越稀薄差异越小。
  实验中恰好观察到了这一规律 @medium-density-observation ，
  说明介质阻力是更好的解释。
]

// ── Final synthesis ──
#claim("vacuum_prediction")[
  在真空中，不同重量的物体应以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("air_resistance_is_confound")
  #premise("inclined_plane_observation")

  + 绑球思想实验表明旧定律自相矛盾 @tied-balls-contradiction 。
  + 日常观察到的速度差异实为介质阻力的表象 @air-resistance-is-confound 。
  + 斜面实验从正面提供了等速趋势的证据 @inclined-plane-observation 。

  三条独立线索汇聚，在真空中结论成立。
]
