#import "module.typ": _gaia_nodes, _gaia_factors, _gaia_module_name, _gaia_proof_premises, _gaia_constraints

// ── Internal: proof block context ──
#let _proof_active = state("proof-active", false)
#let _proof_conclusion = state("proof-conclusion", none)

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

// ── Color scheme ──
#let _c_obs = rgb("#1d4ed8")   // blue
#let _c_set = rgb("#4b5563")   // gray
#let _c_qst = rgb("#b45309")   // amber
#let _c_clm = rgb("#0f766e")   // teal
#let _c_ctr = rgb("#b91c1c")   // red

// ── Shared card renderer ──
#let _card(name_str, tag, color, body) = {
  block(
    width: 100%,
    above: 0.8em,
    below: 0.8em,
    inset: (left: 12pt, top: 8pt, bottom: 8pt, right: 10pt),
    stroke: (left: 3pt + color, rest: 0.5pt + color.lighten(60%)),
    radius: 2pt,
  )[
    #text(size: 8pt, fill: color, weight: "bold", tracking: 0.5pt)[#upper(tag)]
    #h(8pt)
    #text(weight: "bold", size: 10.5pt)[#name_str.replace("_", " ")]
    #v(4pt)
    #body
  ]
}

// ── observation: empirical fact, no proof needed ──
#let observation(name, ..args, body) = {
  _register_node(name, "observation", body)

  [#figure(kind: "gaia", supplement: none, outlined: false)[
    #_card(name, "observation", _c_obs, body)
  ] #label(name.replace("_", "-"))]
}

// ── setting: definitional assumption, no proof needed ──
#let setting(name, ..args, body) = {
  _register_node(name, "setting", body)

  [#figure(kind: "gaia", supplement: none, outlined: false)[
    #_card(name, "setting", _c_set, body)
  ] #label(name.replace("_", "-"))]
}

// ── question: open question, no proof needed ──
#let question(name, ..args, body) = {
  _register_node(name, "question", body)

  [#figure(kind: "gaia", supplement: none, outlined: false)[
    #_card(name, "question", _c_qst, body)
  ] #label(name.replace("_", "-"))]
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
    _proof_active.update(_ => true)
    _proof_conclusion.update(_ => name)

    [#figure(kind: "gaia", supplement: none, outlined: false)[
      #block(
        width: 100%,
        above: 0.8em,
        below: 0.8em,
        inset: (left: 12pt, top: 8pt, bottom: 10pt, right: 10pt),
        stroke: (left: 3pt + _c_clm, rest: 0.5pt + _c_clm.lighten(60%)),
        radius: 2pt,
      )[
        #text(size: 8pt, fill: _c_clm, weight: "bold", tracking: 0.5pt)[CLAIM]
        #h(8pt)
        #text(weight: "bold", size: 10.5pt)[#name.replace("_", " ")]
        #v(4pt)
        #statement
        #v(8pt)
        #block(
          width: 100%,
          inset: (x: 10pt, y: 8pt),
          fill: luma(248),
          radius: 2pt,
          stroke: 0.5pt + luma(220),
        )[
          #text(size: 8pt, fill: luma(100), weight: "bold", tracking: 0.5pt)[PROOF]
          #v(4pt)
          #proof_body
        ]
      ]
    ] #label(name.replace("_", "-"))]

    _proof_active.update(_ => false)
    _proof_conclusion.update(_ => none)
  } else {
    [#figure(kind: "gaia", supplement: none, outlined: false)[
      #_card(name, "claim", _c_clm, statement)
    ] #label(name.replace("_", "-"))]
  }
}

// ── claim_relation: relation between declarations ──
// Usage (same two-block pattern as #claim):
//   #claim_relation("name", between: (...))[statement]              — no proof
//   #claim_relation("name", between: (...))[statement][proof block]  — with proof
#let claim_relation(name, type: "contradiction", between: (), ..args) = {
  let positional = args.pos()
  let statement = if positional.len() > 0 { positional.at(0) } else { none }
  let has_proof = positional.len() > 1
  let proof_body = if has_proof { positional.at(1) } else { none }

  let color = if type == "contradiction" { _c_ctr } else { _c_clm }

  _register_node(name, type, statement)

  _gaia_constraints.update(constraints => {
    constraints.push((
      name: name,
      type: type,
      between: between,
    ))
    constraints
  })

  // Auto-push between members as premises for this constraint
  for member in between {
    _gaia_proof_premises.update(p => { p.push((name, member)); p })
  }

  if has_proof {
    _proof_active.update(_ => true)
    _proof_conclusion.update(_ => name)

    [#figure(kind: "gaia", supplement: none, outlined: false)[
      #block(
        width: 100%,
        above: 0.8em,
        below: 0.8em,
        inset: (left: 12pt, top: 8pt, bottom: 10pt, right: 10pt),
        stroke: (left: 3pt + color, rest: 0.5pt + color.lighten(60%)),
        radius: 2pt,
      )[
        #text(size: 8pt, fill: color, weight: "bold", tracking: 0.5pt)[#upper(type)]
        #h(8pt)
        #text(weight: "bold", size: 10.5pt)[#name.replace("_", " ")]
        #v(4pt)
        #if statement != none { statement; v(4pt) }
        #text(size: 9pt, fill: luma(100))[_#between.map(b => b.replace("_", " ")).join(" ↔ ")_]
        #v(8pt)
        #block(
          width: 100%,
          inset: (x: 10pt, y: 8pt),
          fill: luma(248),
          radius: 2pt,
          stroke: 0.5pt + luma(220),
        )[
          #text(size: 8pt, fill: luma(100), weight: "bold", tracking: 0.5pt)[PROOF]
          #v(4pt)
          #proof_body
        ]
      ]
    ] #label(name.replace("_", "-"))]

    _proof_active.update(_ => false)
    _proof_conclusion.update(_ => none)
  } else {
    [#figure(kind: "gaia", supplement: none, outlined: false)[
      #block(
        width: 100%,
        above: 0.8em,
        below: 0.8em,
        inset: (left: 12pt, top: 8pt, bottom: 8pt, right: 10pt),
        stroke: (left: 3pt + color, rest: 0.5pt + color.lighten(60%)),
        radius: 2pt,
      )[
        #text(size: 8pt, fill: color, weight: "bold", tracking: 0.5pt)[#upper(type)]
        #h(8pt)
        #text(weight: "bold", size: 10.5pt)[#name.replace("_", " ")]
        #v(4pt)
        #if statement != none {
          statement
          v(3pt)
        }
        #text(size: 9pt, fill: luma(100))[_#between.map(b => b.replace("_", " ")).join(" ↔ ")_]
      ]
    ] #label(name.replace("_", "-"))]
  }
}
