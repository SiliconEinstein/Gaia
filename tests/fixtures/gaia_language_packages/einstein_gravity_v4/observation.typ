#import "gaia.typ": *

= 观测验证

// ── 1919 日食观测 ──

#claim(kind: "observation")[
  1919 年 5 月 29 日日全食期间，巴西 Sobral 观测站测得
  恒星光线经过太阳附近时偏折：
  $ theta_"Sobral" = 1.98'' plus.minus 0.16'' $
] <observation.eddington_sobral>

#claim(kind: "observation")[
  同一次日全食期间，西非 Príncipe 岛观测站测得恒星光线偏折：
  $ theta_"Príncipe" = 1.61'' plus.minus 0.30'' $
] <observation.eddington_principe>

#claim(from: (<observation.eddington_sobral>, <observation.eddington_principe>, <general_relativity.gr_light_deflection>))[
  1919 年日食观测数据支持广义相对论的 $1.75''$ 光线偏折预测，
  排除牛顿微粒说的 $0.87''$ 预测。
][
  Sobral 站测得 $1.98'' plus.minus 0.16''$ @observation.eddington_sobral ，
  与广义相对论预测 @general_relativity.gr_light_deflection 的偏差：
  $ frac(|1.98 - 1.75|, 0.16) approx 1.4 sigma $
  与牛顿预测的偏差：
  $ frac(|1.98 - 0.87|, 0.16) approx 6.9 sigma $
  Príncipe 站测得 $1.61'' plus.minus 0.30''$ @observation.eddington_principe ：
  $ frac(|1.61 - 1.75|, 0.30) approx 0.5 sigma quad "(GR)" , quad frac(|1.61 - 0.87|, 0.30) approx 2.5 sigma quad "(Newton)" $
  两个独立观测站的结果一致支持广义相对论，大幅降低系统误差的可能性。
] <observation.eddington_confirms_gr>

// ── GR 双重独立验证 ──

#claim(from: (<observation.eddington_confirms_gr>, <general_relativity.gr_mercury_precession>))[
  光线偏折与水星进动是广义相对论的两个独立预测，
  分别被不同类型的观测所证实。
][
  爱丁顿日食观测 @observation.eddington_confirms_gr 验证了 GR 对光线偏折的预测：
  $ theta_"obs" approx 1.75'' = frac(4 G M, c^2 R) $
  水星进动 @general_relativity.gr_mercury_precession 验证了 GR 对行星轨道的预测：
  $ Delta phi_"obs" approx 43'' "/" "century" = frac(6 pi G M, c^2 a(1-e^2)) times "415 圈" $
  两个验证涉及不同的物理对象（光子 vs 行星）、
  不同的观测手段（日食摄影 vs 长期天文记录）、
  不同的 GR 效应（光线测地线 vs 行星轨道进动），
  却都精确符合同一组场方程的预测。
  这种多渠道独立验证大幅增强了广义相对论的可信度。
] <observation.gr_dual_confirmation>
