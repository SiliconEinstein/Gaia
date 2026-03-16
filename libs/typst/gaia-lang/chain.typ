#import "knowledge.typ": _chain_active, _chain_pipeline, _chain_name, _chain_step_index

// A reasoning chain groups a sequence of knowledge steps.
// Place as content — do NOT capture with `#let`, as that discards the
// state updates (including all knowledge nodes registered inside the body).
#let chain(name, body) = {
  // Activate chain context
  _chain_active.update(_ => true)
  _chain_pipeline.update(_ => none)
  _chain_name.update(_ => name)
  _chain_step_index.update(_ => 0)

  // Render chain heading
  block(above: 1em)[
    == Chain: #name
    #body
  ]

  // Deactivate chain context
  _chain_active.update(_ => false)
  _chain_pipeline.update(_ => none)
  _chain_name.update(_ => none)
  // Note: does NOT return a value — see knowledge.typ for rationale.
}
