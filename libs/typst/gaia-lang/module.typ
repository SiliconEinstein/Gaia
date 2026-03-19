// Global state for collecting all knowledge graph data
#let _gaia_nodes = state("gaia-nodes", ())
#let _gaia_factors = state("gaia-factors", ())
#let _gaia_module_name = state("gaia-module", none)
#let _gaia_modules = state("gaia-modules", ())
#let _gaia_module_titles = state("gaia-module-titles", (:))
#let _gaia_refs = state("gaia-refs", ())
#let _gaia_exports = state("gaia-exports", ())
#let _gaia_package_name = state("gaia-package-name", none)
#let _gaia_package_version = state("gaia-package-version", none)

// v2+ accumulators — premise tactic pushes entries, export-graph reads final()
#let _gaia_proof_premises = state("gaia-proof-premises", ())  // (conclusion, name) pairs
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
  // No visible output — use() is purely structural.
  // The state update above is content and will be placed in document flow.
}

#let package(
  name,
  title: none,
  author: none,
  version: none,
  date: none,
  abstract: none,
  modules: (),
  export: (),
) = {
  _gaia_package_name.update(_ => name)
  if version != none {
    _gaia_package_version.update(_ => str(version))
  }
  _gaia_exports.update(_ => export)

  // Render title block
  {
    let display_title = if title != none { title } else { name.replace("_", " ") }

    align(center)[
      #v(1.5em)
      #text(size: 8.5pt, fill: luma(140), weight: "bold", tracking: 1pt)[GAIA KNOWLEDGE PACKAGE]
      #v(0.6em)
      #text(size: 20pt, weight: "bold")[#display_title]
      #if version != none {
        v(0.3em)
        text(size: 10pt, fill: luma(120))[v#version]
      }
      #v(0.8em)
      #if author != none {
        text(size: 11pt)[#author]
      }
      #if date != none {
        v(0.2em)
        text(size: 10pt, fill: luma(120))[#date]
      }
      #v(1em)
    ]
    line(length: 100%, stroke: 0.5pt + luma(200))
    if abstract != none {
      v(0.8em)
      block(inset: (x: 1.5em))[
        #text(size: 9pt, fill: luma(100), weight: "bold", tracking: 0.3pt)[ABSTRACT]
        #v(3pt)
        #text(size: 10pt)[#abstract]
      ]
      v(0.5em)
      line(length: 100%, stroke: 0.5pt + luma(200))
    }
    v(0.5em)
  }
}

#let export-graph() = context {
  // Build factors directly from premises grouped by conclusion
  let raw_premises = _gaia_proof_premises.final()
  let raw_constraints = _gaia_constraints.final()

  // Get constraint names to exclude from reasoning factors —
  // claim_relation pushes to _gaia_proof_premises for edge connectivity,
  // but those edges belong to the constraint factor, not a reasoning factor.
  let constraint_names = raw_constraints.map(c => c.name)

  let pkg_name = _gaia_package_name.final()
  let pkg_version = _gaia_package_version.final()

  let conclusions = raw_premises.map(p => p.at(0)).dedup()
  let proof_factors = conclusions.map(c => {
    let premises = raw_premises.filter(p => p.at(0) == c).map(p => p.at(1))
    (type: "reasoning", premise: premises, conclusion: c)
  }).filter(f => f.premise.len() > 0 and f.conclusion not in constraint_names)

  [#metadata((
    package: pkg_name,
    version: pkg_version,
    nodes: _gaia_nodes.final(),
    factors: _gaia_factors.final() + proof_factors,
    refs: _gaia_refs.final(),
    modules: _gaia_modules.final(),
    module-titles: _gaia_module_titles.final(),
    exports: _gaia_exports.final(),
    constraints: raw_constraints,
  )) <gaia-graph>]
}
