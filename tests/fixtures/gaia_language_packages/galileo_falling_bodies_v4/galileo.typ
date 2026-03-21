#import "gaia.typ": *

= 伽利略的论证

// -- Observations (no proof needed) --
#claim(kind: "observation")[
  在水、油、空气等不同介质中比较轻重物体的下落，
  会发现介质越稠密，速度差异越明显；介质越稀薄，差异越不明显。
] <galileo.medium_density_observation>

#claim(kind: "observation")[
  伽利略的斜面实验把下落过程放慢到可测量尺度后显示：
  不同重量的小球在相同斜面条件下呈现近似一致的加速趋势，
  与"重量越大速度越大"的简单比例律并不相符。
] <galileo.inclined_plane_observation>

// -- Fine-grained tied-ball decomposition --
#claim(from: (<aristotle.heavier_falls_faster>, <setting.thought_experiment_env>))[
  假设"重者下落更快"，将重球（$H$）与轻球（$L$）绑成复合体（$H L$），
  则 $H L$ 的下落速度慢于 $H$ 单独下落。
][
  在"重者更快"假设下 @aristotle.heavier_falls_faster ，
  考虑绑球思想实验 @setting.thought_experiment_env ：
  轻球 $L$ 的"天然速度"慢于重球 $H$，绑在一起后 $L$ 起拖拽作用，
  因此复合体 $H L$ 的下落速度应慢于 $H$ 单独下落。
] <galileo.composite_is_slower>

#claim(from: (<aristotle.heavier_falls_faster>, <setting.thought_experiment_env>))[
  假设"重者下落更快"，将重球（$H$）与轻球（$L$）绑成复合体（$H L$），
  则 $H L$ 的下落速度快于 $H$ 单独下落。
][
  同一假设下 @aristotle.heavier_falls_faster ，
  在绑球思想实验中 @setting.thought_experiment_env ，
  复合体 $H L$ 总质量 $= H + L > H$，
  按"重者更快"定律，$H L$ 应比 $H$ 下落更快。
] <galileo.composite_is_faster>

#relation(
  type: "contradiction",
  between: (<galileo.composite_is_slower>, <galileo.composite_is_faster>),
)[将重球（$H$）与轻球（$L$）绑成复合体（$H L$），
  "$H L$ 慢于 $H$"与"$H L$ 快于 $H$"两个预测互相矛盾。
][
  两个预测来自同一假设"重者下落更快"，
  针对同一物理对象（复合体 $H L$）：
  一方面，$L$ 的拖拽效应要求 $H L$ 比 $H$ 慢 @galileo.composite_is_slower ；
  另一方面，$H L$ 总质量更大要求它比 $H$ 快 @galileo.composite_is_faster 。
  快与慢不可能同时成立，因此原假设自相矛盾。
] <galileo.tied_balls_contradiction>

// -- Medium elimination --
#claim(from: (<galileo.medium_density_observation>,))[
  日常观察到的速度差异更应被解释为介质阻力造成的表象，
  而不是重量本身决定自由落体速度的证据。
][
  如果速度差异由介质阻力造成，那么介质越稀薄差异越小。
  实验中恰好观察到了这一规律 @galileo.medium_density_observation ，
  说明介质阻力是更好的解释。
] <galileo.air_resistance_is_confound>

// -- Final synthesis --
#claim(from: (<galileo.tied_balls_contradiction>, <galileo.air_resistance_is_confound>, <galileo.inclined_plane_observation>, <setting.vacuum_env>))[
  在真空中，不同重量的物体应以相同速率下落。
][
  + 绑球思想实验表明旧定律自相矛盾 @galileo.tied_balls_contradiction 。
  + 日常观察到的速度差异实为介质阻力的表象 @galileo.air_resistance_is_confound 。
  + 斜面实验从正面提供了等速趋势的证据 @galileo.inclined_plane_observation 。

  三条独立线索汇聚，在真空中结论成立。
] <galileo.vacuum_prediction>
