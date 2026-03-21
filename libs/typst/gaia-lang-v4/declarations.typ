// Gaia v4 — Knowledge declaration functions
// Each returns a single figure(kind: "gaia-node") with hidden metadata.

#let setting(body) = {
  figure(kind: "gaia-node", supplement: "Setting", numbering: none, {
    hide(metadata(("gaia-type": "setting", "from": (), "kind": none)))
    body
  })
}

#let question(body) = {
  figure(kind: "gaia-node", supplement: "Question", numbering: none, {
    hide(metadata(("gaia-type": "question", "from": (), "kind": none)))
    body
  })
}

#let claim(from: (), kind: none, body, ..args) = {
  assert(args.named().len() == 0,
    message: "unexpected named arguments: " + repr(args.named().keys()))
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  figure(kind: "gaia-node", supplement: "Claim", numbering: none, {
    hide(metadata(("gaia-type": "claim", "from": from, "kind": kind)))
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

#let action(from: (), kind: none, body, ..args) = {
  assert(args.named().len() == 0,
    message: "unexpected named arguments: " + repr(args.named().keys()))
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  figure(kind: "gaia-node", supplement: "Action", numbering: none, {
    hide(metadata(("gaia-type": "action", "from": from, "kind": kind)))
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

#let relation(type: "contradiction", between: (), body, ..args) = {
  assert(type == "contradiction" or type == "equivalence",
    message: "relation type must be 'contradiction' or 'equivalence', got: " + type)
  assert(args.named().len() == 0,
    message: "unexpected named arguments: " + repr(args.named().keys()))
  let proof-body = if args.pos().len() > 0 { args.pos().at(0) } else { none }
  let supplement = if type == "contradiction" { "Contradiction" } else { "Equivalence" }
  figure(kind: "gaia-node", supplement: supplement, numbering: none, {
    hide(metadata(("gaia-type": "relation", "rel-type": type, "between": between)))
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
