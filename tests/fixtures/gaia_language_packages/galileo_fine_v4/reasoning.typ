#import "gaia.typ": *

= 推理

// --- 假说 A: 重者更快 ---
#claim[
  物体下落速度与其重量成正比：重物比轻物下落更快。
] <hyp.A>

// W1展开: A → B_daily, B_daily ↔ O_daily
#claim(from: (<hyp.A>,))[
  A的预测：日常应观察到重者更快。
] <pred.B_daily>

#relation(
  type: "equivalence",
  between: (<pred.B_daily>, <obs.daily>),
)[
  B_daily与O_daily是等价命题：A的预测即日常观察。
] <rel.Bdaily_eq_Odaily>

// --- 绑球思想实验 ---
#claim(from: (<hyp.A>,))[
  假设重物下落更快，将重球H与轻球L绑在一起，L拖拽H，复合体HL速度应慢于H。
] <hyp.T1>

#claim(from: (<hyp.A>,))[
  假设重物下落更快，复合体HL总重量大于H，因此HL速度应快于H。
] <hyp.T2>

#relation(
  type: "contradiction",
  between: (<hyp.T1>, <hyp.T2>),
)[
  T1与T2互相矛盾：复合体HL不能同时慢于H又快于H。
] <rel.T1_contra_T2>

// --- A + S_vac → A_vac ---
#claim(from: (<hyp.A>, <setting.vacuum>))[
  A与真空条件的合取成立。
] <hyp.AV_M>

#claim(from: (<hyp.AV_M>,))[
  在真空中也应重者更快（A的推论应用于真空的推论）。
] <hyp.A_vac>

// --- 假说 G: 空气阻力是原因 ---
#claim[
  空气阻力是造成下落速度差异的主要原因。
] <hyp.G>

// W2展开: G → B_media, B_media ↔ O_media; G → B_air, B_air ↔ O_air
#claim(from: (<hyp.G>,))[
  G的预测：介质密度影响下落速度差异。
] <pred.B_media>

#relation(
  type: "equivalence",
  between: (<pred.B_media>, <obs.media>),
)[
  B_media与O_media是等价命题。
] <rel.Bmedia_eq_Omedia>

#claim(from: (<hyp.G>,))[
  G的预测：空气中重材料球落差极小。
] <pred.B_air>

#relation(
  type: "equivalence",
  between: (<pred.B_air>, <obs.air>),
)[
  B_air与O_air是等价命题。
] <rel.Bair_eq_Oair>

// G + S_vac → GV_M → V
#claim(from: (<hyp.G>, <setting.vacuum>))[
  G与真空条件的合取成立。
] <hyp.GV_M>

#claim(from: (<hyp.GV_M>,))[
  在真空中，不同重量的物体以相同速率下落。
] <hyp.V>

// --- W3展开: V → predictions → observations ---
#claim(from: (<hyp.V>, <setting.plane>))[
  V与斜面条件的合取成立（实验1）。
] <hyp.Vt1_M>

#claim(from: (<hyp.Vt1_M>,))[
  V的预测1：斜面实验中不同重量球加速一致。
] <pred.B_theta1>

#relation(
  type: "equivalence",
  between: (<pred.B_theta1>, <obs.theta1>),
)[
  B_theta1与E_theta1是等价命题。
] <rel.Bt1_eq_Et1>

#claim(from: (<hyp.V>, <setting.plane>))[
  V与斜面条件的合取成立（实验2）。
] <hyp.Vt2_M>

#claim(from: (<hyp.Vt2_M>,))[
  V的预测2：重复实验结果高度一致。
] <pred.B_theta2>

#relation(
  type: "equivalence",
  between: (<pred.B_theta2>, <obs.theta2>),
)[
  B_theta2与E_theta2是等价命题。
] <rel.Bt2_eq_Et2>

// --- A_vac ⊗ V ---
#relation(
  type: "contradiction",
  between: (<hyp.A_vac>, <hyp.V>),
)[
  A_vac与V之间存在矛盾。
] <rel.Avac_contra_V>
