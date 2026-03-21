// Gaia v4 — Document styling and show rules

#let _c_set = rgb("#4b5563")
#let _c_qst = rgb("#b45309")
#let _c_clm = rgb("#0f766e")
#let _c_act = rgb("#6d28d9")
#let _c_ctr = rgb("#b91c1c")
#let _c_eqv = rgb("#2563eb")

#let _color_for(supplement) = {
  if supplement == [Setting] { _c_set }
  else if supplement == [Question] { _c_qst }
  else if supplement == [Claim] { _c_clm }
  else if supplement == [Action] { _c_act }
  else if supplement == [Contradiction] { _c_ctr }
  else if supplement == [Equivalence] { _c_eqv }
  else { gray }
}

#let gaia-style(body) = {
  set page(margin: (x: 2.5cm, y: 2cm))
  set text(11pt, lang: "en")
  set par(justify: true)

  show heading.where(level: 1): it => {
    text(14pt, weight: "bold", it)
    v(0.3em)
    line(length: 100%, stroke: 0.5pt + gray)
  }

  show figure.where(kind: "gaia-node"): it => {
    let color = _color_for(it.supplement)
    block(
      width: 100%,
      inset: 1em,
      stroke: (left: 3pt + color, rest: 0.5pt + luma(220)),
      {
        text(8pt, weight: "bold", fill: color, upper(it.supplement))
        h(0.5em)
        it.body
      },
    )
  }

  // Render @ref to gaia-node figures using the label name instead of "Claim 1"
  show ref: it => {
    let targets = query(it.target)
    if targets.len() > 0 {
      let target = targets.first()
      if target.has("kind") and target.kind == "gaia-node" {
        let label-str = str(it.target)
        let color = _color_for(target.supplement)
        text(fill: color, weight: "medium", label-str)
      } else {
        it
      }
    } else {
      it
    }
  }

  // Hide external reference figures from rendering
  show figure.where(kind: "gaia-ext"): it => {
    hide(it)
  }

  body
}
