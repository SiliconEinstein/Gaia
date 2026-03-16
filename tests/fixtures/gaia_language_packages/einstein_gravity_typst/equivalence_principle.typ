#import "../../../../libs/typst/gaia-lang/lib.typ": *

#module("equivalence_principle", title: "等价原理 — 爱因斯坦 1907 电梯思想实验")

#use("prior_knowledge.eotvos_experiment")
#use("prior_knowledge.maxwell_electromagnetism")

#setting("elevator_env")[
  想象一个密闭电梯，其中的观察者无法看到外界。
  如果电梯静止在引力场中（如地表），
  观察者感受到的"重力"与电梯在无引力的太空中以 g 加速上升时
  观察者感受到的"惯性力"完全不可区分。
]

#chain("ep_derivation_chain")[
  #claim("equivalence_principle",
    premise: ("eotvos_experiment", "elevator_env"),
  )[
    爱因斯坦等价原理：在足够小的时空区域内，
    引力效应与相应的加速参考系效应不可区分。
    这不只是 m_i = m_g 的重复陈述，
    而是将其提升为一条基本物理原理。
  ]
]

#chain("light_bending_chain")[
  #claim("light_must_bend_in_gravity",
    premise: ("equivalence_principle", "maxwell_electromagnetism"),
  )[
    等价原理的直接推论：在加速电梯中，水平射入的光束因电梯上升
    而呈现向下弯曲的路径。如果引力与加速度等价，那么在引力场中
    光也必须弯曲。光作为电磁波也不能免于引力的影响。
  ]
]
