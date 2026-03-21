// Gaia Typst DSL — Path C Label-based prototype
// 验证：label 引用、from 参数、query 收集、metadata 输出

// ============================================================
// 1. 声明函数 — 每个返回单个 figure（这样 <label> 能正确附着）
// ============================================================

#let gaia-setting(body) = {
  figure(kind: "gaia-node", supplement: "Setting", body)
}

#let gaia-question(body) = {
  figure(kind: "gaia-node", supplement: "Question", body)
}

#let gaia-claim(from: (), kind: none, body, ..args) = {
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  figure(kind: "gaia-node", supplement: "Claim", {
    // 隐藏的 metadata，存储 from 和 kind
    hide(metadata(("node-type": "claim", "from": from, "kind": kind)))
    body
    if proof-body != none {
      v(0.3em)
      block(
        inset: (left: 1em, top: 0.5em, bottom: 0.5em),
        stroke: (left: 2pt + gray),
        proof-body,
      )
    }
  })
}

#let gaia-action(from: (), kind: none, body, ..args) = {
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  figure(kind: "gaia-node", supplement: "Action", {
    hide(metadata(("node-type": "action", "from": from, "kind": kind)))
    body
    if proof-body != none {
      v(0.3em)
      block(
        inset: (left: 1em, top: 0.5em, bottom: 0.5em),
        stroke: (left: 2pt + gray),
        proof-body,
      )
    }
  })
}

#let gaia-relation(type: "contradiction", between: (), body) = {
  figure(kind: "gaia-node", supplement: "Relation", {
    hide(metadata(("node-type": "relation", "rel-type": type, "between": between)))
    body
  })
}

// ============================================================
// 2. export-graph：收集所有节点和边
// ============================================================

#let export-graph() = context {
  let all-nodes = query(figure.where(kind: "gaia-node"))

  let graph-nodes = ()
  let graph-edges = ()

  for node in all-nodes {
    // 获取 supplement 作为类型
    let node-type = if node.supplement != none { repr(node.supplement) } else { "unknown" }

    // 尝试获取 label
    let node-label = repr(node.label)

    // 尝试从 figure body 内的 metadata 提取 from/between
    let inner = node.body
    // query 当前 figure 内部的 metadata（通过位置范围）

    graph-nodes.push((
      label: node-label,
      type: node-type,
    ))
  }

  // 单独 query 所有 metadata 获取 from/between 信息
  let all-meta = query(metadata)
  for m in all-meta {
    let val = m.value
    if type(val) == dictionary {
      if "from" in val and type(val.from) == array and val.from.len() > 0 {
        for src-label in val.from {
          graph-edges.push((
            type: "premise",
            from: repr(src-label),
            info: repr(val),
          ))
        }
      }
      if "between" in val and type(val.between) == array and val.between.len() > 0 {
        for b in val.between {
          graph-edges.push((
            type: val.at("rel-type", default: "unknown"),
            node: repr(b),
          ))
        }
      }
    }
  }

  // 输出人类可读的结果
  [
    = Graph Export Result

    == Nodes (#graph-nodes.len())
    #for n in graph-nodes {
      [- #n.type : #raw(n.label) \ ]
    }

    == Edges (#graph-edges.len())
    #for e in graph-edges {
      if "from" in e {
        [- premise: #raw(e.from) \ ]
      } else {
        [- #e.type : #raw(e.node) \ ]
      }
    }
  ]

  // 机器可读输出
  [#metadata((graph: (nodes: graph-nodes, edges: graph-edges))) <gaia-graph>]
}

// ============================================================
// 3. Show rule — 让 gaia-node figure 好看一点
// ============================================================

#show figure.where(kind: "gaia-node"): it => {
  block(
    width: 100%,
    inset: 1em,
    stroke: (left: 3pt + blue),
    {
      text(8pt, weight: "bold", fill: gray)[#it.supplement]
      h(0.5em)
      it.body
    },
  )
}

// ============================================================
// 4. 测试用例
// ============================================================

= Test Knowledge Package

#gaia-setting[假设宇宙在大尺度上是平坦的。] <flat_universe>

#gaia-setting[假设广义相对论在宇宙学尺度上成立。] <gr_valid>

#gaia-question[暗能量的物理本质是什么？] <main_question>

#gaia-claim(kind: "observation")[
  Ia 型超新星观测数据显示宇宙正在加速膨胀。
] <sn_observation>

#gaia-claim(kind: "observation")[
  CMB 各向异性数据与平坦宇宙模型一致。
] <cmb_data>

#gaia-claim(from: (<sn_observation>, <cmb_data>, <flat_universe>, <gr_valid>))[
  暗能量占宇宙总能量密度的约 68%。
][
  根据 @sn_observation 和 @cmb_data 的独立观测证据，
  在 @flat_universe 和 @gr_valid 的假设下，
  通过 Friedmann 方程约束，可以推导出暗能量占比约为 68%。
] <dark_energy_fraction>

#gaia-relation(type: "contradiction", between: (<dark_energy_fraction>,))[
  暗能量的宇宙学常数解释与量子场论的真空能预测存在 120 个数量级的差异。
] <vacuum_catastrophe>

#gaia-action(kind: "python", from: (<sn_observation>,))[
  使用 emcee 对 Ia 型超新星数据进行 MCMC 拟合。
] <mcmc_fit>

// 测试 @ref 交叉引用
== Cross References Test

根据 @sn_observation 和 @cmb_data 的观测数据，我们得出了 @dark_energy_fraction 的结论。
这与 @vacuum_catastrophe 构成了现代物理学的一个核心矛盾。
@mcmc_fit 提供了数值验证。

// 导出图
#export-graph()
