#import "declarations.typ": _proof_active, _proof_conclusion
#import "module.typ": _gaia_proof_premises, _gaia_proof_steps

// ── premise: declare an independent premise (noisy-AND input edge) ──
// The ONLY tactic that affects the factor graph.
// Must be inside a proof block. Pushes (conclusion, name) to global accumulator.
#let premise(name) = {
  context {
    let active = _proof_active.get()
    if not active {
      text(fill: red)[premise used outside proof block]
    } else {
      let concl = _proof_conclusion.get()
      _gaia_proof_premises.update(p => { p.push((concl, name)); p })
      _gaia_proof_steps.update(s => {
        s.push((concl, (tactic: "premise", name: name)))
        s
      })
    }
  }
  block(inset: (left: 1em))[
    — *Premise:* #name.replace("_", " ")
  ]
}

// ── Internal: generic reasoning strategy tactic ──
// All strategy tactics share this pattern: record step + render block.
// name is optional (none = anonymous). body is content.
// tactic_name is the string recorded in proof traces (e.g. "deduce", "abduction").
// display_name is the human label shown in rendering.
#let _strategy(tactic_name, display_name, name, body) = {
  context {
    let active = _proof_active.get()
    if not active {
      text(fill: red)[#tactic_name used outside proof block]
    } else {
      let concl = _proof_conclusion.get()
      let step = (tactic: tactic_name, content: body)
      if name != none { step.insert("name", name) }
      _gaia_proof_steps.update(s => { s.push((concl, step)); s })
    }
  }
  if name != none {
    [#figure(kind: "gaia", supplement: none, outlined: false, block(
      above: 0.4em, inset: (left: 1em),
    )[
      *#display_name#if name != none [ (#name.replace("_", " "))]:* #body
    ]) #label(name.replace("_", "-"))]
  } else {
    block(above: 0.4em, inset: (left: 1em))[
      *#display_name:* #body
    ]
  }
}

// ── Reasoning strategy tactics ──
// Each tells the reviewer which reasoning strategy the author is using.
// None affect the factor graph — only #premise does.

// deduce: deductive reasoning (strong syllogism)
#let deduce(name: none, body) = _strategy("deduce", "Deduce", name, body)

// abduction: inference to best explanation (weak syllogism)
#let abduction(name: none, body) = _strategy("abduction", "Abduction", name, body)

// by_contradiction: reductio ad absurdum
#let by_contradiction(name: none, body) = _strategy("by_contradiction", "By contradiction", name, body)

// by_cases: case analysis
#let by_cases(name: none, body) = _strategy("by_cases", "By cases", name, body)

// by_induction: inductive generalization
#let by_induction(name: none, body) = _strategy("by_induction", "By induction", name, body)

// by_analogy: analogical reasoning
#let by_analogy(name: none, body) = _strategy("by_analogy", "By analogy", name, body)

// by_elimination: process of elimination
#let by_elimination(name: none, body) = _strategy("by_elimination", "By elimination", name, body)

// by_extrapolation: trend extrapolation / limit argument
#let by_extrapolation(name: none, body) = _strategy("by_extrapolation", "By extrapolation", name, body)

// synthesize: convergence of multiple independent evidence lines
#let synthesize(name: none, body) = _strategy("synthesize", "Synthesis", name, body)
