#import "../../../../libs/typst/gaia-lang/v2.typ": *

#module("derivation", title: "推导")

#use("axioms.second_law")
#use("axioms.third_law")
#use("observations.kepler_third_law")
#use("observations.pendulum_experiment")
#use("observations.near_earth_surface")

// ── 第一步：从开普勒定律推出反平方关系 ──

#claim("inverse_square_force")[
  对于绕中心天体做圆周运动的物体，
  所受引力与到天体中心距离 r 的平方成反比：F ∝ 1/r²。
][
  #premise("kepler_third_law")
  #premise("second_law")

  由牛顿第二定律 @second-law ，
  做匀速圆周运动的物体需要向心力 F = m_i × v²/r。
  轨道速度 v = 2πr/T，代入得 F = m_i × 4π²r / T²。
  由开普勒第三定律 @kepler-third-law T² = k × r³（k 为常数），
  代入得 F = (4π²/k) × m_i / r²。
  因此引力与距离的平方成反比。
]

// ── 第二步：推出完整的万有引力公式 ──

#claim("law_of_gravity")[
  万有引力定律：质量为 M 和 m_g 的两个物体之间的引力为
  F = G × M × m_g / r²，
  其中 r 是两者之间的距离，G 是万有引力常数。
][
  #premise("inverse_square_force")
  #premise("third_law")

  由反平方关系 @inverse-square-force ，
  天体 A（质量 M）对物体 B（质量 m）的引力为 F_AB = C(M) × m / r²，
  其中 C(M) 是仅依赖 A 的质量的系数。
  由牛顿第三定律 @third-law ，B 对 A 的引力 F_BA = F_AB。
  从 A 的视角，F_BA = C(m) × M / r²。
  两式描述同一个力：C(M) × m = C(m) × M，
  因此 C(M)/M = C(m)/m = G（普适常数）。
  得 F = G × M × m_g / r²。
]

// ── 第三步：从摆锤实验推出质量等价 ──

#claim("mass_equivalence")[
  物体的惯性质量 m_i（决定对力的加速响应）
  与引力质量 m_g（决定所受引力大小）相等：m_i = m_g。
][
  #premise("pendulum_experiment")
  #premise("second_law")
  #premise("law_of_gravity")

  单摆的回复力由引力提供（∝ m_g），而加速阻力由惯性决定（∝ m_i）。
  摆锤周期 T = 2π × √(L × m_i / (m_g × g))。
  如果 m_i/m_g 因材料而异，不同材料的等长摆锤周期就会不同。
  牛顿的摆锤实验 @pendulum-experiment 表明
  所有材料的周期在 10⁻³ 精度内一致，
  因此 m_i/m_g 是与材料无关的普适常数。
  选择适当单位，m_i = m_g。
]

// ── 第四步：推出自由落体加速度与质量无关 ──

#claim("freefall_acceleration_equals_g")[
  在地球表面附近，任何物体的自由落体加速度都等于
  g ≈ 9.8 m/s²，与物体质量无关。
][
  #premise("second_law")
  #premise("law_of_gravity")
  #premise("mass_equivalence")
  #premise("near_earth_surface")

  对自由落体，唯一的力是引力。
  由牛顿第二定律 @second-law 得 F = m_i × a；
  由万有引力定律 @law-of-gravity 得 F = G × M × m_g / r²。
  两式描述同一个力：m_i × a = G × M × m_g / r²。
  由质量等价 @mass-equivalence m_i = m_g，
  两边约去质量得 a = G × M / r²。
  在地球表面 @near-earth-surface r ≈ R，
  故 a = G × M / R² = g。
  加速度表达式中不含物体质量，因此与质量无关。
]
