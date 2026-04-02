#import "gaia.typ": *

= 推理

// === 亚里士多德分支 ===

// 日常观测 → 亚里士多德命题
#claim(from: (<obs.daily>,))[
  物体下落速度与重量成正比：重物比轻物下落更快。
] <hyp.A>

// A → 日常预测 B_daily（A 的可观测推论）
#claim(from: (<hyp.A>,))[
  亚里士多德定律预测：日常中重物应比轻物下落更快。
] <pred.B_daily>

// B_daily ↔ O_daily：预测与观测的一致性
#relation(
  type: "equivalence",
  between: (<pred.B_daily>, <obs.daily>),
)[
  亚里士多德的日常预测与日常观测一致。
] <rel.Bdaily_eq_Odaily>

// A → T1: 拖拽论证
#claim(from: (<hyp.A>,))[
  假设重物下落更快，将重球 H 与轻球 L 绑在一起，
  L 拖拽 H，复合体 HL 速度应慢于 H 单独下落。
] <hyp.T1>

// A → T2: 总重论证
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

// A + vacuum → A_vac: 亚里士多德在真空中的推论
#claim(from: (<hyp.A>, <setting.vacuum>))[
  按亚里士多德定律，在真空中也应重者下落更快。
] <hyp.A_vac>

// === 伽利略分支 ===

// 介质观测 → 空气阻力假说 G
#claim(from: (<obs.media>, <obs.air>))[
  日常观察到的速度差异由空气阻力造成，
  而非重量本身决定。
] <hyp.G>

// G → 介质预测 B_media
#claim(from: (<hyp.G>,))[
  空气阻力假说预测：在不同密度介质中，
  密度越低则轻重物体速度差越小。
] <pred.B_media>

// B_media ↔ O_media
#relation(
  type: "equivalence",
  between: (<pred.B_media>, <obs.media>),
)[
  介质预测与介质观测一致。
] <rel.Bmedia_eq_Omedia>

// G → 空气预测 B_air
#claim(from: (<hyp.G>,))[
  空气阻力假说预测：在空气中做精细实验，
  应观测到轻重物体几乎同速。
] <pred.B_air>

// B_air ↔ O_air
#relation(
  type: "equivalence",
  between: (<pred.B_air>, <obs.air>),
)[
  空气预测与空气实验一致。
] <rel.Bair_eq_Oair>

// G + vacuum → V: 真空等速
#claim(from: (<hyp.G>, <setting.vacuum>))[
  如果速度差异纯由空气阻力造成，
  则在真空中不同重量物体应等速下落。
] <hyp.V>

// === 斜面证据链 ===

// theta1 + plane → V_t1
#claim(from: (<obs.theta1>, <setting.plane>))[
  第一组斜面实验支持真空等速下落。
] <hyp.V_t1>

// V_t1 → B_theta1
#claim(from: (<hyp.V_t1>,))[
  等速假说预测第一组斜面实验应呈等加速。
] <pred.B_theta1>

// B_theta1 ↔ O_theta1
#relation(
  type: "equivalence",
  between: (<pred.B_theta1>, <obs.theta1>),
)[
  第一组斜面预测与观测一致。
] <rel.Bt1_eq_Ot1>

// theta2 + plane → V_t2
#claim(from: (<obs.theta2>, <setting.plane>))[
  第二组斜面实验支持真空等速下落。
] <hyp.V_t2>

// V_t2 → B_theta2
#claim(from: (<hyp.V_t2>,))[
  等速假说预测第二组斜面实验应呈等加速。
] <pred.B_theta2>

// B_theta2 ↔ O_theta2
#relation(
  type: "equivalence",
  between: (<pred.B_theta2>, <obs.theta2>),
)[
  第二组斜面预测与观测一致。
] <rel.Bt2_eq_Ot2>

// === 最终矛盾 ===

// A_vac ⊗ V: 亚里士多德与伽利略在真空中的预测矛盾
#relation(
  type: "contradiction",
  between: (<hyp.A_vac>, <hyp.V>),
)[
  真空中不能同时"重者更快"又"等速下落"。
] <rel.Avac_contra_V>
