#import "gaia.typ": *

= 推理

// W1: 日常观察 → 亚里士多德命题 A（soft implication, p=0.70）
#claim(from: (<obs.daily>,))[
  物体下落速度与其重量成正比：重物比轻物下落更快。
] <hyp.A>

// A → T1, A → T2（绑球思想实验的两个确定性推论）
#claim(from: (<hyp.A>,))[
  假设重物下落更快，将重球H与轻球L绑在一起，L拖拽H，复合体HL速度应慢于H单独下落。
] <hyp.T1>

#claim(from: (<hyp.A>,))[
  假设重物下落更快，复合体HL总重量大于H，因此HL速度应快于H单独下落。
] <hyp.T2>

// T1 ⊗ T2（矛盾）
#relation(
  type: "contradiction",
  between: (<hyp.T1>, <hyp.T2>),
)[
  T1与T2互相矛盾：复合体HL不能同时慢于H又快于H。
] <rel.T1_contra_T2>

// A ∧ S_vac → A_vac（确定性推导）
#claim(from: (<hyp.A>, <setting.vacuum>))[
  在真空中也应重者更快（A的推论应用于真空条件）。
] <hyp.A_vac>

// W2: 介质证据链 → V_w2（soft implication, p=0.80）
#claim(from: (<obs.media>, <obs.air>, <setting.vacuum>))[
  介质实验与空气实验的证据表明，在真空中不同重量的物体以相同速率下落。
] <hyp.V_w2>

// W3: 斜面证据链 → V_w3（soft implication, p=0.78）
#claim(from: (<obs.theta>, <setting.plane>))[
  斜面实验的证据表明，在真空中不同重量的物体以相同速率下落。
] <hyp.V_w3>

// V_w2 ↔ V_w3（两条独立证据链达到相同结论）
#relation(
  type: "equivalence",
  between: (<hyp.V_w2>, <hyp.V_w3>),
)[
  V_w2与V_w3是等价命题：两条独立证据链得出相同的真空等速结论。
] <rel.V_equiv>

// A_vac ⊗ V_w2（矛盾：真空中重者更快 vs 真空中等速）
#relation(
  type: "contradiction",
  between: (<hyp.A_vac>, <hyp.V_w2>),
)[
  A_vac与V之间存在矛盾：真空中不能同时重者更快又等速下落。
] <rel.Avac_contra_V>
