#import "gaia.typ": *

= 等价原理

#setting[
  密闭电梯思想实验：电梯中的观察者无法看到外界，
  需要判断自己是静止在引力场中还是在无引力空间中匀加速上升。
] <equivalence_principle.elevator_env>

#claim(from: (<prior_knowledge.eotvos_experiment>, <equivalence_principle.elevator_env>))[
  爱因斯坦等价原理：在足够小的时空区域内，
  均匀引力场的效应与匀加速参考系的效应不可区分。
][
  引力对物体的加速度为：
  $ a_"gravity" = frac(F, m_i) = frac(m_g, m_i) dot frac(G M, r^2) $
  Eötvös 实验 @prior_knowledge.eotvos_experiment 以 $10^(-9)$ 精度表明 $m_i = m_g$，
  因此 $m_g \/ m_i = 1$，引力加速度与物体的组成和质量完全无关：
  $ a_"gravity" = frac(G M, r^2) $

  在密闭电梯 @equivalence_principle.elevator_env 中，
  静止于引力场所感受的"重力"加速度为 $g = G M \/ r^2$；
  在无引力空间中以 $a = g$ 匀加速上升的电梯内，
  惯性力产生完全等效的加速度。
  由于 $m_i = m_g$ 对一切物质成立，
  没有任何局部实验能区分这两种情况——
  因此引力与加速度在物理上等价。
] <equivalence_principle.equivalence_principle>

#claim(from: (<equivalence_principle.equivalence_principle>, <prior_knowledge.maxwell_electromagnetism>))[
  光线在引力场中会发生弯曲。
][
  由等价原理 @equivalence_principle.equivalence_principle ，引力场等价于匀加速参考系。
  在向上以 $g$ 匀加速的电梯中，水平射入的光束在时间 $t$ 内
  相对电梯地板下移：
  $ Delta y = frac(1, 2) g t^2 $
  即光束轨迹相对电梯呈抛物线弯曲。
  由麦克斯韦理论 @prior_knowledge.maxwell_electromagnetism ，光是电磁波，
  作为物理实体同样适用等价原理。
  因此在等价的引力场中，光线同样必须弯曲。
] <equivalence_principle.light_bends_in_gravity>
