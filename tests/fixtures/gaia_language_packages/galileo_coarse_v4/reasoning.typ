#import "gaia.typ": *

= 推理

// W1: 日常观测 → 亚里士多德命题 A
#claim(from: (<obs.daily>,))[
  物体下落速度与重量成正比：重物比轻物下落更快。
] <hyp.A>

// A → T1: 绑球拖拽论证
#claim(from: (<hyp.A>,))[
  假设重物下落更快，将重球 H 与轻球 L 绑在一起，
  L 拖拽 H，复合体 HL 速度应慢于 H 单独下落。
] <hyp.T1>

// A → T2: 绑球总重论证
#claim(from: (<hyp.A>,))[
  假设重物下落更快，复合体 HL 总重量大于 H，
  因此 HL 速度应快于 H 单独下落。
] <hyp.T2>

// T1 ⊗ T2: 矛盾
#relation(
  type: "contradiction",
  between: (<hyp.T1>, <hyp.T2>),
)[
  T1 与 T2 互相矛盾：复合体 HL 不能同时慢于 H 又快于 H。
] <rel.T1_contra_T2>

// A + S_vac → A_vac: 亚里士多德在真空中的推论
#claim(from: (<hyp.A>, <setting.vacuum>))[
  按亚里士多德定律，在真空中也应重者下落更快。
] <hyp.A_vac>

// W2: 介质证据 + 空气证据 → V
#claim(from: (<obs.media>, <obs.air>))[
  综合介质和空气实验的证据，
  在真空中不同重量物体应以相同速率下落。
] <hyp.V>

// W3: 斜面实验 → V（独立证据链支持同一结论）
#claim(from: (<obs.inclined_plane>,))[
  斜面实验提供了正面证据：在真空中物体等速下落。
] <hyp.V_inclined>

// V ↔ V_inclined: 两条独立证据链得到等价结论
#relation(
  type: "equivalence",
  between: (<hyp.V>, <hyp.V_inclined>),
)[
  两条独立证据链得出等价的真空等速结论。
] <rel.V_equiv>

// A_vac ⊗ V: 亚里士多德真空预测与伽利略真空预测矛盾
#relation(
  type: "contradiction",
  between: (<hyp.A_vac>, <hyp.V>),
)[
  真空中不能同时"重者更快"又"等速下落"。
] <rel.Avac_contra_V>
