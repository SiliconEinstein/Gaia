#import "gaia.typ": *

= 推导

// ── 第一步：从开普勒定律推出反平方关系 ──

#claim(from: (<observations.kepler_third_law>, <laws.second_law>))[
  对于绕中心天体做圆周运动的物体，
  所受引力与到天体中心距离 $r$ 的平方成反比。
  $ F prop frac(1, r^2) $
][
  由牛顿第二定律 @laws.second_law ，做匀速圆周运动的物体需要向心力：
  $ F = frac(m_i v^2, r) $
  轨道速度 $v = 2 pi r \/ T$，代入：
  $ F = frac(m_i dot 4 pi^2 r^2, r dot T^2) = frac(4 pi^2 m_i r, T^2) $
  由开普勒第三定律 @observations.kepler_third_law $T^2 = k r^3$，代入消去 $T$：
  $ F = frac(4 pi^2 m_i r, k r^3) = frac(4 pi^2, k) dot frac(m_i, r^2) $
  系数 $4 pi^2 \/ k$ 为常数，因此引力与距离的平方成反比。
] <derivation.inverse_square_force>

// ── 第二步：推出完整的万有引力公式 ──

#claim(from: (<derivation.inverse_square_force>, <laws.third_law>))[
  万有引力定律：质量为 $M$ 和 $m_g$ 的两个物体之间的引力与两者质量之积成正比，
  与距离的平方成反比。
  $ F = frac(G M m_g, r^2) $
][
  由反平方关系 @derivation.inverse_square_force ，天体 A（质量 $M$）对物体 B（质量 $m$）的引力：
  $ F_(A B) = C(M) dot frac(m, r^2) $
  其中 $C(M)$ 是仅依赖 A 质量的系数。
  由牛顿第三定律 @laws.third_law $F_(A B) = F_(B A)$，从 B 对 A 的视角：
  $ F_(B A) = C(m) dot frac(M, r^2) $
  两式描述同一个力，因此：
  $ C(M) dot m = C(m) dot M quad ==> quad frac(C(M), M) = frac(C(m), m) = G $
  $G$ 为与具体物体无关的普适常数。代回得：
  $ F = frac(G M m_g, r^2) $
] <derivation.law_of_gravity>

// ── 第三步：从摆锤实验推出质量等价 ──

#claim(from: (<observations.pendulum_experiment>, <laws.second_law>, <derivation.law_of_gravity>))[
  物体的惯性质量 $m_i$（决定对力的加速响应）
  与引力质量 $m_g$（决定所受引力大小）相等。
  $ m_i = m_g $
][
  单摆的回复力由引力提供（$prop m_g$），加速阻力由惯性决定（$prop m_i$）。
  摆锤周期：
  $ T = 2 pi sqrt(frac(L dot m_i, m_g dot g)) $
  如果 $m_i \/ m_g$ 因材料而异，不同材料的等长摆锤周期就会不同。
  牛顿的摆锤实验 @observations.pendulum_experiment 表明
  所有材料的周期在 $10^(-3)$ 精度内一致：
  $ frac(m_i, m_g) = "const"  quad ==> quad m_i = m_g $
  （选择适当单位使比值等于 1。）
] <derivation.mass_equivalence>

// ── 第四步：推出自由落体加速度与质量无关 ──

#claim(from: (<laws.second_law>, <derivation.law_of_gravity>, <derivation.mass_equivalence>, <observations.near_earth_surface>))[
  在地球表面附近，任何物体的自由落体加速度都等于
  $g approx 9.8$ m/s²，与物体质量无关。
][
  对自由落体，唯一的力是引力。
  联立牛顿第二定律 @laws.second_law 与万有引力定律 @derivation.law_of_gravity ：
  $ m_i a = frac(G M m_g, r^2) $
  由质量等价 @derivation.mass_equivalence $m_i = m_g$，两边约去质量：
  $ a = frac(G M, r^2) $
  在地球表面 @observations.near_earth_surface $r approx R$：
  $ a = frac(G M, R^2) = g $
  加速度表达式中不含物体质量，因此自由落体加速度与物体质量无关。
] <derivation.freefall_acceleration_equals_g>

// ── 汇聚：两条独立路径殊途同归 ──

#gaia-bibliography(yaml("gaia-deps.yml"))

#claim(from: (<derivation.freefall_acceleration_equals_g>, <vacuum_prediction>))[
  牛顿从力学定律出发的数学推导，与伽利略从思想实验出发的逻辑论证，
  独立得出同一结论：自由落体加速度与物体质量无关。
][
  伽利略的论证路径 @vacuum_prediction ：
  从"重者下落更快"假设出发，通过绑球思想实验揭示逻辑矛盾，
  结合斜面实验与介质消除，推出真空中一切物体等速下落。

  牛顿的论证路径 @derivation.freefall_acceleration_equals_g ：
  从运动定律与开普勒观测出发，推导 $F = G M m_g \/ r^2$，
  再由摆锤实验确立 $m_i = m_g$，最终得出 $a = G M \/ R^2 = g$，
  加速度不含物体质量。

  两条路径的前提完全独立——伽利略不依赖力学定律，
  牛顿不依赖绑球思想实验——殊途同归显著增强了结论的可信度。
] <derivation.galileo_newton_convergence>

// ── Apollo 15：跨越三个世纪的直接验证 ──

#claim(kind: "observation")[
  1971 年 Apollo 15 任务中，宇航员 David Scott 在月球表面（真空环境）
  同时释放一把锤子（$1.32$ kg）和一根羽毛（$0.03$ g），
  质量比约 $44000 : 1$，两者同时落地。
] <derivation.apollo15_feather_drop>

#claim(from: (<derivation.apollo15_feather_drop>,))[
  在月球真空条件下，质量相差约四万倍的物体仍然同时落地，
  直接验证自由落体加速度与质量无关。
][
  Apollo 15 月面实验 @derivation.apollo15_feather_drop 在真正的真空环境中进行。
  若自由落体加速度依赖质量，预期到达时间差：
  $ Delta t prop frac(Delta m, m) dot frac(h, g_"moon") $
  锤子与羽毛的质量比约 $44000 : 1$，
  若存在质量依赖性，时间差应极为显著。
  实际观测：两者同时落地，$Delta t approx 0$。
] <derivation.apollo15_confirms_equal_fall>

#claim(from: (<derivation.apollo15_confirms_equal_fall>, <vacuum_prediction>))[
  伽利略 1638 年的思想实验预测与 Apollo 15 1971 年的月面实验结果一致：
  在真空中一切物体以相同速率下落。
][
  伽利略通过绑球思想实验与介质消除论证 @vacuum_prediction ，
  在 1638 年从纯逻辑推理出发预测真空中一切物体等速下落——
  但当时无法制造真空来直接验证。

  333 年后，Apollo 15 月面实验 @derivation.apollo15_confirms_equal_fall
  在月球的天然真空中直接验证了这一预测：
  质量比 $44000 : 1$ 的锤子与羽毛同时落地。

  思想实验的逻辑推理与真空中的直接观测完全独立，
  跨越三个世纪的殊途同归为等速下落提供了极强的认识论支撑。
] <derivation.apollo_galileo_convergence>
