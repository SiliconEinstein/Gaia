#import "module.typ": _gaia_nodes, _gaia_factors, _gaia_module_name, _gaia_proof_premises, _gaia_proof_steps, _gaia_constraints

// ── Internal: proof block context ──
// NOTE on Typst state timing: state.update() in tactics produces content
// that is resolved in document flow order. Reading state.get() in the same
// context block may not see updates from content placed earlier.
// SOLUTION: tactics record their conclusion association in global accumulators.
// The claim function sets _proof_conclusion before the proof body.
// export-graph reads final state — no in-claim state reads needed.
#let _proof_active = state("proof-active", false)
#let _proof_conclusion = state("proof-conclusion", none)

// _register_node uses context internally so callers don't need to wrap in context
#let _register_node(name, node_type, content_text) = context {
  let mod = _gaia_module_name.get()
  _gaia_nodes.update(nodes => {
    nodes.push((
      name: name,
      type: node_type,
      content: content_text,
      module: mod,
    ))
    nodes
  })
}

// ── observation: empirical fact, no proof needed ──
// Label is placed outside context so it remains referenceable.
// Accepts ..args for forward-compatibility (extra named args are ignored).
#let observation(name, ..args, body) = {
  _register_node(name, "observation", body)

  block(above: 0.6em)[
    *#name.replace("_", " ")* (observation): #body #label(name.replace("_", "-"))
  ]
}

// ── setting: definitional assumption, no proof needed ──
// Accepts ..args for v1 backward-compatibility (premise:/ctx: are accepted but ignored).
#let setting(name, ..args, body) = {
  _register_node(name, "setting", body)

  block(above: 0.6em)[
    *#name.replace("_", " ")* (setting): #body #label(name.replace("_", "-"))
  ]
}

// ── question: open question, no proof needed ──
// Accepts ..args for v1 backward-compatibility (premise:/ctx: are accepted but ignored).
#let question(name, ..args, body) = {
  _register_node(name, "question", body)

  block(above: 0.6em)[
    *#name.replace("_", " ")* (question): #body #label(name.replace("_", "-"))
  ]
}

// ── claim: assertion, optional proof block ──
// Usage:
//   #claim("name")[statement]              — no proof (hole if used as premise)
//   #claim("name")[statement][proof block]  — with proof
#let claim(name, ..args) = {
  let positional = args.pos()
  let statement = positional.at(0)
  let has_proof = positional.len() > 1
  let proof_body = if has_proof { positional.at(1) } else { none }

  _register_node(name, "claim", statement)

  if has_proof {
    // Activate proof context — tactics will push to global accumulators
    // tagged with this conclusion name. No in-claim state reads needed.
    _proof_active.update(_ => true)
    _proof_conclusion.update(_ => name)

    // Render claim heading + statement + proof body
    // Label is on the block, outside any context expression.
    block(above: 1em)[
      === #name.replace("_", " ") #label(name.replace("_", "-"))
      *Claim:* #statement

      *Proof:*
      #proof_body
    ]

    // Deactivate proof context
    // Factor emission happens in export-graph via accumulator aggregation
    _proof_active.update(_ => false)
    _proof_conclusion.update(_ => none)
  } else {
    // No proof — just render the declaration
    block(above: 0.6em)[
      *#name.replace("_", " ")* (claim): #statement #label(name.replace("_", "-"))
    ]
  }
}

// ── claim_relation: relation between declarations ──
#let claim_relation(name, type: "contradiction", between: (), ..args) = {
  let positional = args.pos()
  let statement = positional.at(0)
  let has_proof = positional.len() > 1
  let proof_body = if has_proof { positional.at(1) } else { none }

  _register_node(name, type, statement)

  // Emit constraint
  _gaia_constraints.update(constraints => {
    constraints.push((
      name: name,
      type: type,
      between: between,
    ))
    constraints
  })

  if has_proof {
    _proof_active.update(_ => true)
    _proof_conclusion.update(_ => name)

    block(above: 1em)[
      === #name.replace("_", " ") #label(name.replace("_", "-"))
      *Relation (#type):* #statement \
      _Between: #between.join(", ")_

      *Proof:*
      #proof_body
    ]

    _proof_active.update(_ => false)
    _proof_conclusion.update(_ => none)
  } else {
    block(above: 0.6em)[
      *#name.replace("_", " ")* (#type): #statement #label(name.replace("_", "-")) \
      _Between: #between.join(", ")_
    ]
  }
}
