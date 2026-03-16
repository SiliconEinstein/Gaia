#import "module.typ": _gaia_nodes, _gaia_factors

// Internal: detect if we're inside a chain
#let _chain_active = state("chain-active", false)
#let _chain_pipeline = state("chain-pipeline", none)
#let _chain_name = state("chain-name", none)
#let _chain_step_index = state("chain-step-index", 0)

#let _register_node(name, node_type, content_text, premise, ctx) = {
  _gaia_nodes.update(nodes => {
    nodes.push((
      name: name,
      type: node_type,
      content: content_text,
      premise: premise,
      ctx: ctx,
    ))
    nodes
  })
}

#let _knowledge(name, node_type, body, premise: (), ctx: ()) = context {
  let is_chain = _chain_active.get()

  // In chain: auto-inject previous step as first premise if no explicit premise
  let effective_premise = premise
  if is_chain and premise == () {
    let prev = _chain_pipeline.get()
    if prev != none {
      effective_premise = (prev,)
    }
  }

  // Register node
  _register_node(name, node_type, body, effective_premise, ctx)

  // If in chain, register factor and update pipeline
  if is_chain {
    let chain_name = _chain_name.get()
    let step_idx = _chain_step_index.get()
    _gaia_factors.update(factors => {
      factors.push((
        chain: chain_name,
        step: step_idx,
        type: if node_type == "contradiction" { "mutex_constraint" }
              else if node_type == "equivalence" { "equiv_constraint" }
              else { "reasoning" },
        premise: effective_premise,
        ctx: ctx,
        conclusion: name,
      ))
      factors
    })
    _chain_pipeline.update(_ => name)
    _chain_step_index.update(n => n + 1)
  }

  // Render — always show premise/ctx when present
  block(above: 0.6em)[
    === #name \[#node_type\]
    #if effective_premise != () [
      #block(above: 0.3em, inset: (left: 1em))[
        _Premise: #effective_premise.join(", ")_
      ]
    ]
    #if ctx != () [
      #block(inset: (left: 1em))[
        _Context: #ctx.join(", ")_
      ]
    ]
    #body
  ]
  // Note: does NOT return a value. In Typst, `#let x = func()` discards
  // content (including state.update calls), so knowledge functions must
  // always be placed as content, never captured with #let.
  // Reference knowledge by its string name, e.g. premise: ("my_claim",)
}

#let claim(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "claim", body, premise: premise, ctx: ctx)
}

#let setting(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "setting", body, premise: premise, ctx: ctx)
}

#let question(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "question", body, premise: premise, ctx: ctx)
}

#let contradiction(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "contradiction", body, premise: premise, ctx: ctx)
}

#let equivalence(name, ..args, premise: (), ctx: (), body) = {
  _knowledge(name, "equivalence", body, premise: premise, ctx: ctx)
}
