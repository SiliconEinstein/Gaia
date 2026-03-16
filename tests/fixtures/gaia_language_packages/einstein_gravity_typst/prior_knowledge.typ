#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("prior_knowledge", title: "先验知识 — 从其他 package 和历史背景引入的前提")

#use("newton_principia.law_of_gravity")
#use("newton_principia.acceleration_independent_of_mass")
#use("galileo_falling_bodies.vacuum_prediction")

#claim("eotvos_experiment")[
  Eötvös 1889 年的扭摆实验以 10^-9 的精度验证了
  惯性质量与引力质量的等价性。
  这是迄今为止对 m_i = m_g 最精确的实验检验。
]

#claim("maxwell_electromagnetism")[
  麦克斯韦电磁理论：光是电磁波，在真空中以恒定速度 c 传播。
  光不是粒子（至少在经典电磁理论框架下）。
]

#claim("soldner_deflection")[
  Soldner 1801 年基于牛顿力学的微粒说计算：
  光线掠过太阳表面时偏折角度为 0.87 角秒。
  这是纯牛顿框架下的预测。
]
