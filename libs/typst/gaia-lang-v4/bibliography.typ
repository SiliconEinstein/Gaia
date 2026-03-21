// Gaia v4 — Cross-package knowledge references (analogous to #bibliography())
// Registers external knowledge nodes as labeled figures.
// Usage: #gaia-bibliography(yaml("gaia-deps.yml"))

#let gaia-bibliography(data) = {
  if data == none or type(data) != dictionary { return }
  for (key, entry) in data {
    if type(entry) != dictionary { continue }
    // Create a hidden figure for each external node.
    // This makes the <key> label available for from: and @ref.
    [#figure(kind: "gaia-ext", supplement: "External", {
      hide(metadata((
        "gaia-type": "external",
        "ext-package": entry.at("package", default: ""),
        "ext-version": entry.at("version", default: ""),
        "ext-node": entry.at("node", default: key),
        "ext-content-type": entry.at("type", default: "claim"),
        "ext-content": entry.at("content", default: key),
      )))
      hide(text(entry.at("content", default: key)))
    }) #label(key)]
  }
}
