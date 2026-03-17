// Global state for collecting all knowledge graph data
#let _gaia_nodes = state("gaia-nodes", ())
#let _gaia_factors = state("gaia-factors", ())
#let _gaia_module_name = state("gaia-module", none)
#let _gaia_modules = state("gaia-modules", ())
#let _gaia_module_titles = state("gaia-module-titles", (:))
#let _gaia_refs = state("gaia-refs", ())
#let _gaia_exports = state("gaia-exports", ())

// v2 accumulators — tactics push tagged entries, export-graph reads final()
#let _gaia_proof_premises = state("gaia-proof-premises", ())  // (conclusion, name) pairs
#let _gaia_proof_steps = state("gaia-proof-steps", ())        // (conclusion, step-dict) pairs
#let _gaia_constraints = state("gaia-constraints", ())

#let module(name, title: none) = {
  _gaia_module_name.update(_ => name)
  _gaia_modules.update(m => { m.push(name); m })
  if title != none {
    _gaia_module_titles.update(m => { m.insert(name, title); m })
  }
  // Render module heading
  if title != none {
    heading(level: 1)[#name — #title]
  } else {
    heading(level: 1)[#name]
  }
}

// Registers an external knowledge reference. Place as content — do NOT capture
// with `#let`, as that discards the state update. Use string names to refer to
// imported knowledge in `premise:` and `ctx:` parameters.
//
// Example:
//   #use("galileo.galileo_experiment")  // registers the ref
//   #claim("my_step", premise: ("galileo_experiment",))[...]
#let use(target) = {
  let alias = target.split(".").last()
  _gaia_refs.update(refs => {
    refs.push((alias: alias, target: target))
    refs
  })
  // Render a small note so use() produces visible content
  text(size: 0.8em, fill: gray)[_imports #alias from #target _]
}

#let package(name, modules: (), export: ()) = {
  _gaia_exports.update(_ => export)
}

#let export-graph() = context {
  // Aggregate proof traces from flat accumulators
  let raw_premises = _gaia_proof_premises.final()
  let raw_steps = _gaia_proof_steps.final()

  // Group by conclusion
  let conclusions = raw_premises.map(p => p.at(0)).dedup()
  let traces = conclusions.map(c => {
    let premises = raw_premises.filter(p => p.at(0) == c).map(p => p.at(1))
    let steps = raw_steps.filter(s => s.at(0) == c).map(s => s.at(1))
    (conclusion: c, premises: premises, steps: steps)
  })

  // Build factors from proof traces (one noisy-AND per proven claim)
  let proof_factors = traces.filter(t => t.premises.len() > 0).map(t => (
    type: "reasoning",
    premise: t.premises,
    conclusion: t.conclusion,
  ))

  [#metadata((
    nodes: _gaia_nodes.final(),
    factors: _gaia_factors.final() + proof_factors,
    refs: _gaia_refs.final(),
    modules: _gaia_modules.final(),
    module-titles: _gaia_module_titles.final(),
    exports: _gaia_exports.final(),
    proof-traces: traces,
    constraints: _gaia_constraints.final(),
  )) <gaia-graph>]
}
