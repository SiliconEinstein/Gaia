#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("observation", title: "观测验证 — Eddington 1919 日食与 Apollo 15 月面实验")

#use("general_relativity.gr_light_deflection")
#use("prior_knowledge.soldner_deflection")
#use("general_relativity.deflection_contradiction")
#use("prior_knowledge.galileo_vacuum_prediction")
#use("prior_knowledge.newton_a_equals_g")

#claim("eddington_sobral")[
  1919 年 5 月 29 日日全食，Sobral (巴西) 观测站测得
  恒星光线偏折 1.98 ± 0.16 角秒。
  与 GR 预测 (1.75) 一致，与牛顿预测 (0.87) 偏离 7σ。
]

#claim("eddington_principe")[
  同一日食，Príncipe (西非) 观测站测得偏折 1.61 ± 0.30 角秒。
  与 GR 预测一致，与牛顿预测偏离约 2.5σ。
]

#claim("apollo15_feather_drop")[
  1971 年 Apollo 15 宇航员 David Scott 在月球表面
  同时释放一把锤子 (1.32 kg) 和一根羽毛 (0.03 g)，
  质量比 44:1。两者在月球真空中同时落地。
]

#chain("eddington_chain")[
  #claim("eddington_confirms_gr",
    premise: ("eddington_sobral", "eddington_principe", "gr_light_deflection"),
  )[
    爱丁顿日食观测支持广义相对论的 1.75 角秒预测，
    排除了牛顿框架的 0.87 角秒预测。
    两个独立观测站的一致性大幅降低了系统误差的可能性。
  ]
]

#chain("soldner_rejection_chain")[
  #claim("soldner_prediction_disfavored",
    premise: ("eddington_confirms_gr", "deflection_contradiction"),
  )[
    在爱丁顿 1919 年观测之后，
    Soldner/牛顿的 0.87 角秒预测不再是与数据相容的最佳解释，
    至少在太阳边缘光偏折问题上应被显著削弱。
  ]
]

#chain("apollo_chain")[
  #claim("apollo15_confirms_equal_fall",
    premise: ("apollo15_feather_drop",),
  )[
    月球表面没有大气，提供了真正的真空条件。
    在 44:1 的极端质量比下，两个物体仍然同时落地，
    直接验证了"自由落体加速度与质量无关"的预测，
    并为"真空中不同重量物体等速下落"提供了近乎理想条件下的经验支持。
  ]
]

#chain("convergence_chain")[
  #claim("three_path_convergence",
    premise: ("galileo_vacuum_prediction", "newton_a_equals_g", "apollo15_confirms_equal_fall"),
  )[
    "所有物体在引力场中等速下落"这一结论
    被三条方法上彼此不同、相对独立的认识路径所支持：
    （1）逻辑路径：伽利略 1638 绑球归谬法
    （2）理论路径：牛顿 1687 F=ma+F=mg 推导
    （3）观测路径：Apollo 15 月面直接实验
    三条路径从不同方向到达同一结论，大幅提升可信度。
  ]
]
