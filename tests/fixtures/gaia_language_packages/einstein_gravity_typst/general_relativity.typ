#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("general_relativity", title: "广义相对论 — 1915 场方程、光线偏折预测、与牛顿的关系")

#use("equivalence_principle.light_must_bend_in_gravity")
#use("prior_knowledge.soldner_deflection")
#use("prior_knowledge.newton_gravity")
#use("prior_knowledge.newton_a_equals_g")

#claim("einstein_field_equations")[
  爱因斯坦场方程 (1915)：G_μν + Λg_μν = (8πG/c⁴)T_μν。
  引力不是力，而是时空弯曲的几何效应。
  物质告诉时空如何弯曲，时空告诉物质如何运动。
]

#claim("mercury_perihelion")[
  广义相对论精确预测了水星近日点每世纪 43 角秒的异常进动，
  这是牛顿引力无法解释的天文观测。
]

#chain("light_deflection_chain")[
  #claim("gr_light_deflection",
    premise: ("light_must_bend_in_gravity", "einstein_field_equations"),
  )[
    广义相对论预测：光线掠过太阳表面时偏折 1.75 角秒。
    这是 Soldner/牛顿预测 (0.87 角秒) 的恰好两倍，
    因为 GR 同时包含时间弯曲和空间弯曲的贡献，
    而牛顿框架只捕获了时间弯曲部分。
  ]
]

#contradiction("deflection_contradiction",
  premise: ("gr_light_deflection", "soldner_deflection"),
)[
  GR 预测光线偏折 1.75 角秒，牛顿微粒说预测 0.87 角秒。
  两个预测不能同时正确——它们之间恰好差两倍，
  差异来源是 GR 的空间弯曲贡献。
  这是一个可以通过观测判决的定量矛盾。
]

#chain("subsumption_chain")[
  #claim("gr_subsumes_newton_weak_field",
    premise: ("einstein_field_equations", "newton_gravity", "newton_a_equals_g"),
  )[
    在弱引力场和低速条件下，广义相对论退化为牛顿引力。
    牛顿的 F=GMm/r² 和 a=g 都是 GR 的弱场近似。
    GR 不否定牛顿，而是将其包含为特殊情况。
  ]
]

// newton_subsumed_by_gr: theory subsumption (using claim since subsumption type not yet in Typst)
#chain("weak_field_summary_chain")[
  #claim("newton_subsumed_by_gr",
    premise: ("gr_subsumes_newton_weak_field",),
  )[
    牛顿引力定律 F=GMm/r² 是广义相对论在弱场低速极限下的近似。
    GR 是更一般的理论，牛顿是其特殊情况。
    这是理论继承而非理论否定。
  ]
]
