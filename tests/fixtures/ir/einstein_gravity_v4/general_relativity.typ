#import "gaia.typ": *

= 广义相对论

#claim[
  爱因斯坦场方程：引力不是超距力，而是质能分布导致的时空弯曲。
  $ G_(mu nu) + Lambda g_(mu nu) = frac(8 pi G, c^4) T_(mu nu) $
  左端 $G_(mu nu)$（Einstein 张量）描述时空曲率，
  右端 $T_(mu nu)$（能动张量）描述物质能量分布，
  $Lambda$ 为宇宙学常数。
] <general_relativity.einstein_field_equations>

// ── 光线偏折预测 ──

#claim(from: (<equivalence_principle.light_bends_in_gravity>, <general_relativity.einstein_field_equations>))[
  广义相对论预测：光线掠过太阳表面时偏折 $1.75''$。
][
  等价原理已定性预测光线在引力场中弯曲 @equivalence_principle.light_bends_in_gravity 。
  在 Schwarzschild 度规下 @general_relativity.einstein_field_equations ，
  光线经过质量 $M$ 的天体时偏折角为：
  $ theta = frac(4 G M, c^2 R) $
  其中 $R$ 为光线与天体中心的最近距离。
  这一结果包含两部分贡献：
  $ underbrace(frac(2 G M, c^2 R), "时间弯曲") + underbrace(frac(2 G M, c^2 R), "空间弯曲") = frac(4 G M, c^2 R) $
  Soldner 的牛顿微粒说 @prior_knowledge.soldner_deflection 仅考虑时间弯曲，
  得到 $theta_"Newton" = 2 G M \/ (c^2 R) = 0.87''$。
  广义相对论的空间弯曲贡献恰好再翻一倍：
  $ theta_"GR" = 2 theta_"Newton" = 1.75'' $
] <general_relativity.gr_light_deflection>

#relation(type: "contradiction", between: (<general_relativity.gr_light_deflection>, <prior_knowledge.soldner_deflection>))[
  广义相对论预测光线偏折 $1.75''$，牛顿微粒说预测 $0.87''$，
  两者针对同一物理量给出不同数值，不可能同时正确。
][
  广义相对论 @general_relativity.gr_light_deflection 的完整计算给出：
  $ theta_"GR" = frac(4 G M, c^2 R) = 1.75'' $
  Soldner 的牛顿微粒说 @prior_knowledge.soldner_deflection 仅含时间弯曲项：
  $ theta_"Newton" = frac(2 G M, c^2 R) = 0.87'' $
  两者比值恰好为 2，但针对同一物理量（太阳边缘的光线偏折角），
  不可能同时正确——任何精度足够高的观测都能判决。
] <general_relativity.deflection_contradiction>

// ── 水星近日点进动 ──

#claim(kind: "observation")[
  天文观测显示水星近日点每世纪有约 $43''$ 的异常进动，
  牛顿引力理论在扣除其他行星摄动后无法解释这一剩余量。
] <general_relativity.mercury_perihelion>

#claim(from: (<general_relativity.einstein_field_equations>, <general_relativity.mercury_perihelion>))[
  广义相对论精确解释了水星近日点每世纪 $43''$ 的异常进动，
  无需引入任何新参数。
][
  在 Schwarzschild 度规下 @general_relativity.einstein_field_equations 求解行星轨道，
  广义相对论给出每圈额外进动：
  $ Delta phi = frac(6 pi G M, c^2 a (1 - e^2)) $
  其中 $M$ 为太阳质量，$a$ 为轨道半长轴，$e$ 为离心率。
  代入水星轨道参数
  $a = 5.79 times 10^(10)$ m、$e = 0.2056$：
  $ Delta phi approx 0.1035'' "（每圈）" $
  水星公转周期约 $87.97$ 天，每世纪约 $415$ 圈，
  累积进动 $approx 43''$\/世纪，
  与观测值 @general_relativity.mercury_perihelion 精确吻合。
  所有参数（$G$, $M$, $c$, $a$, $e$）均由独立测量确定，
  无需引入任何自由参数。
] <general_relativity.gr_mercury_precession>
