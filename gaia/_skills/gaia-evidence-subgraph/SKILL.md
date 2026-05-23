---
name: gaia-evidence-subgraph
description: |
  Use to build, audit, and render a methodological-decomposition evidence
  graph rooted on a chain-backed quantitative claim of the form "<system or
  setting> has <quantity> = <value>" or "<computation / measurement> yields
  <observable>". The graph is the anatomy of how that single result is closed
  inside one paper's reasoning — observational / experimental constraints,
  theoretical or computational inputs, intermediate computed quantities,
  derivation / inversion / fitting steps, parameter and approximation choices,
  and external-paper / setting context. Multiple labelled joint-support factor
  diamonds, three-class edge taxonomy (chain support / background /
  verification support — render in the user's locale, e.g. 链式支撑 / 背景 /
  核验支撑 in Chinese), auto-layout (Graphviz neato/sfdp or Mermaid flowchart
  with linkStyle for per-edge classes — Mermaid mindmap is NOT acceptable),
  CJK-safe fonts and labels. Domain-agnostic: physics, chemistry, materials,
  biology, ML, climate, astrophysics, etc. Input is an LKM chain payload,
  fetched via `gaia search lkm knowledge "<root>"` to surface the root and
  `gaia search lkm reasoning --claim-id <id> --format raw-json` for the
  chains + the `data.papers` metadata block (use `--format raw-json` — the
  verbatim envelope is the audit substrate under `raw/`). The graph is
  strictly chain-bounded — only LKM-returned premises and their explicit
  content are admitted as nodes; no synthetic bridging from external sources.
  Reach for this skill when the user explicitly asks for a closure-chain /
  evidence graph (not Gaia formalization — that is the `gaia-lkm-explore` client); it
  pairs with `gaia-scholarly-synthesis`, which consumes the audited graph it
  produces.
---

# Evidence Subgraph

## Principle

The graph shows the **anatomy of one quantitative result**, not a literature genealogy. The root is a specific result — typically `<system> has <quantity> = <value>` or `<computation / measurement> yields <observable>`. The graph traces the reasoning pipeline that produces that result inside the root paper:

`(observational / experimental anchors) + (theoretical / computational inputs) + (parameter / approximation choices) → (intermediate quantities) → (derivation / inversion / fitting) → (root result)`.

External papers do **not** become "tier-1 upstream conclusions" — they appear as named **context** nodes (named by the formula, dataset, method, or theorem they contributed *as named in the LKM premise content*; *not* by paper id) attached to whichever reasoning step uses them. The backbone is the root paper's own reasoning chain returned by LKM `evidence`. The graph is strictly chain-bounded: every node and edge must trace to content that LKM returned. Do not mint synthetic intermediate nodes to bridge gaps in the chain payload — gaps are recorded as audit-table observations, not papered over.

The same paradigm applies across domains:

- **Computational science** — `(electronic structure / force field / simulation inputs) → (intermediate observables) → (derivation) → (parameter value or predicted observable)`.
- **Experimental science** — `(measurement protocol + calibration + sample preparation) → (raw signal) → (analysis / inversion) → (extracted parameter)`.
- **ML / AI** — `(architecture + dataset + hyperparameters) → (training curves / intermediate metrics) → (eval protocol) → (benchmark score / scaling exponent)`.
- **Modeling-driven fields** (climate, astrophysics, epidemiology) — `(forcings / initial conditions + model resolution + parameterizations) → (simulated observables) → (comparison / inversion) → (sensitivity parameter)`.

The skill text below is domain-agnostic. Every domain-specific term in the produced graph comes from the LKM chain payload (premise / factor / step content and `data.papers` metadata), not from the skill.

## Input

The skill is invoked with a single root claim id and the corresponding LKM chain payload — the `gaia search lkm reasoning --claim-id <id> --format raw-json` output (and, if available, the `gaia search lkm knowledge "<root>" --format raw-json` output that surfaced the root). The root's conclusion text names a system / setting and a quantitative result. The skill does not perform discovery; it does not select among candidates. Callers (or the user directly) supply the chosen root id.

If invoked with a chain-less claim id (`total_chains == 0`), stop and report the gate failure. Do not invent premises.

## Output

Every successful invocation leaves on disk:

- a structured graph artifact (`evidence_graph.json`) capturing nodes, edges, and per-element source pointers into the LKM payload (RFC 6901 JSON Pointer convention against the verbatim raw payload);
- the canonical re-renderable graph source (`evidence_graph.dot`, or `evidence_graph.mmd` when Mermaid is the chosen renderer);
- a human-readable raster (`evidence_graph.png`, plus optionally SVG/PDF);
- the verbatim LKM raw payloads under `raw/` (at minimum `evidence_<root-gcn-id>.json` — the `gaia search lkm reasoning --claim-id … --format raw-json` envelope; if a `gaia search lkm knowledge … --format raw-json` recall was consulted to surface the root, also `match_NN.json`); raw payloads are never modified, pretty-printed, or stripped — they are the audit substrate the source pointers resolve against;
- an audit table (rows per non-trivial edge — see §6) co-located with the graph artifacts.

The audit table and every node/edge in `evidence_graph.json` carry a chain-payload anchor (premise `gcn_*`, factor `gfac_*`, `factors[i].steps[j].reasoning`, or claim content) so a reader can trace any element back to the LKM JSON. Anchor discipline is canonical in `references/source-ground-truth.md` — read it before producing output.

## Workflow

### 0. Gate: chain-backed root

The evidence payload for the root must have `total_chains > 0`. Synthetic premises only with explicit user waiver. If the root id does not satisfy the gate, stop and report — do not proceed.

The chain payload itself is the **single source of truth** for every node and audit anchor in this skill: claim `content`, factor `subtype`, premise `id` and `content`, optional `steps[].reasoning`, and the `data.papers` metadata block. No external paper text is admitted as a node.

### 1. Factor diamonds (one per `gfac_*`)

Each `gfac_*` factor in the root's evidence chains becomes a labelled diamond (`shape=diamond` in DOT, or analogous in Mermaid). The label is two short lines:

- top line: the factor operator name in the user's locale (`共同支撑` for Chinese / `joint support` for English / etc.). If the LKM payload exposes a `subtype` (e.g. `noisy_and`, `noisy_or`), include it parenthetically: `共同支撑 (noisy_and)` / `joint support (noisy_and)`.
- bottom line: a concrete tag derived from the factor's premises — e.g. *"inversion step"*, *"first-principles input"*, *"dataset + protocol"*, *"thermodynamic coverage"*. The exact wording comes from reading the premise contents and naming the cluster they form.

If the chain has **multiple** `gfac_*` nodes, render multiple factor diamonds — **do not collapse them into one**. Multiple factors carve the reasoning into distinguishable clusters (e.g. one for the input computation, another for the inversion step, another for cross-observable coverage).

If the chain has **exactly one** `gfac_*` node, render exactly one diamond. Use the bottom-line tag to summarise the cumulative semantic of all premises (e.g. *"inversion-step closure"*, *"computation + fitting"*) — do not leave the bottom line empty or generic.

### 2. Native premises → typed reasoning nodes

The primary text source for each premise is `factors[].premises[].content` in the parent chain payload. Some chain payloads also expose `steps[].reasoning` — that field is **optional**. Do not require `steps`; do not fail when it is absent.

For each native premise (chain-internal id; `total_chains == 0` standalone but full content recoverable from the parent chain), classify the premise content into one of four reasoning-node types:

- **method-setting** — *what* method / protocol / model is used and *how* it is configured. Examples: "simulation method + convergence parameters", "fit model + assumed prior", "measurement protocol + calibration".
- **intermediate result** — a computed, simulated, or measured quantity that becomes input to the next step. Examples: "computed coupling = 1.33", "fitted gap ratio = 5.0", "training loss at step N", "measured rate constant = …".
- **parameter choice** — an explicitly chosen scalar / categorical setting, with its value. Examples: "isotropy assumption true", "cutoff ω_c = 3 Ω_max", "mini-batch size = 64", "fixed prior σ = 0.1".
- **derivation step** — an equation, inversion, or fitting procedure that determines a downstream quantity. Examples: "Δ_{m=1}(μ*, T_c) = 0 ⇒ μ* fixed", "argmax over θ", "linear regression on log-log axes".

Render each as a labelled box (filled, locale-safe font). Label is two short lines: first line = tag (the role this node plays in the chain), second line = numerical / equation / symbol anchor lifted verbatim from the premise `content` (or, when present, `steps[].reasoning`).

**Empty-content premises (temporary).** Some premises currently come back from the LKM with only an `id` populated and an empty `content` — this is a temporary corpus state and the LKM is being progressively populated. Render as gray dashed nodes with the placeholder label "未展开前提 / unexpanded premise" only when the user explicitly asks for full premise coverage; the default is to omit. The audit table must mark them `content unavailable (temporary)` so a future run (when content is populated) can revisit them.

**No synthetic bridging.** The graph is strictly chain-bounded. If an intermediate quantity is implied but not present in any premise / step / claim content returned by LKM, do **not** mint a node for it — record the gap in the audit table as `gap: <description>` and move on. Inventing nodes silently switches the graph from chain-backed to synthetic.

**No duplicate nodes for equivalent premises.** When two premises (or a premise and a verification-support claim) assert the **same proposition** — same equation, same numerical value, same formal statement, just from different parts of the chain or different source packages — render them as a **single node**. List the two source packages in parentheses on a second label line, or as a side note in the audit table; do not draw two near-identical boxes. The merge decision is a judgement call on the premise text; when in doubt, keep the two as distinct verification-support nodes — the independent confirmation is informative for the closure-chain reader and erasing it loses information. Obvious same-paper / same-version restatements (e.g. arXiv preprint and journal version of one paper saying the same thing) should still be merged.

### 3. Background / context nodes

Add a panel-style node (visually distinct from reasoning nodes — different fill colour, `shape=note` in DOT) for each of:

- **external paper / formula / dataset / theorem named inside an LKM premise's `content`** — name it by the formula, dataset, theorem, or method it contributed (e.g. *"AD formula"*, *"Morel–Anderson renormalization"*, *"ImageNet-1k"*, *"GPCR-Bench"*, *"Anderson's theorem"*) — **never** by paper id, and **never** drawn from outside the chain payload. The actual paper bibliography lives in the `data.papers` block of the chain payload and travels with the run-folder for downstream consumers; this skill does not emit a references list.
- **parameter-setting / approximation / regularization choice** — e.g. *"real-axis solution, weak damping"*, *"hybrid functional"*, *"early stopping"*.
- **scope-bounding empirical fact** — a fact that bounds where the analysis applies (e.g. *"linear-T resistivity"*, *"validation set held out"*, *"Migdal small parameter ω_ph/E_F ≪ 1"*).

Connect to the reasoning node(s) they justify, scope, or limit using **background** edges. Background nodes never participate in the conjunction structure; they annotate it. Background nodes have **no incoming chain edges**.

### 4. Edge taxonomy (exactly three classes)

| class | render style | when to use |
|-------|--------------|-------------|
| **chain support** (`链式支撑` / `chain support`) | solid line, thick (penwidth 1.8–2.2), neutral colour (e.g. black) | chain conjunction edges: premises → factor diamond, factor diamond → root, and any internal step-to-step backbone explicitly carried by the LKM chain |
| **background** (`背景` / `background`) | dashed line, thin, distinctive colour (e.g. purple) | context: parameter setting, external-paper input, regularization choice, scope-bounding fact |
| **verification support** (`核验支撑` / `verification support`) | dashed line, thin, distinctive colour (e.g. green) | independent calculation, source-of-record number, or cross-method check that confirms (or partially disconfirms) a specific numerical anchor inside a reasoning node — for partial-disconfirm polarity append a parenthetical to the edge label, e.g. `核验支撑（部分不符）` / `verification support (partial disconfirm)` |

The label rendered on the edge is in the user's locale. The taxonomy itself is fixed.

**Do not introduce other classes.** No "literature support", no "tier-2 support", no `upstream_conclusion_support`. External-paper inputs are background; cross-method comparisons (confirming or partially disconfirming) are verification support — note polarity in the audit table's bridge sentence rather than inventing a fourth class.

### 5. Layout, fonts, and labels (CJK-safe)

- **Auto-layout renderer**: Graphviz `neato` / `sfdp` for DOT (preferred for archival), or Mermaid `flowchart` with `linkStyle` for per-edge classes (preferred when no Graphviz install). Do **not** use Mermaid `mindmap` — it has no per-edge styling and cannot encode the three-class taxonomy.
- **Title format**: `<root system / topic> <quantity or theme>: closure-chain map (auto-layout)`. Localize to the user's prompt language (e.g. `<topic>：闭合链图（自动布局）` for Chinese). The "(auto-layout)" tag tells the reader spatial arrangement is non-semantic. The phrasing "closure chain" / "闭合链" is intentional — it names what the graph actually is (the closed reasoning that produces the root result) without overloading more general terms.
- **Locale**: labels in the user's prompt language.
- **CJK fonts (avoid Graphviz tofu pit).** Default Graphviz fonts (Helvetica, Times) **omit Chinese / Japanese / Korean glyphs**, producing tofu (`□`) blocks in the rendered PNG/SVG. Set fonts explicitly on `graph`, `node`, and `edge` for any non-Latin script:

  ```dot
  graph [fontname="Noto Sans CJK SC", labelloc="t", label=<...>];
  node  [fontname="Noto Sans CJK SC", style="rounded,filled"];
  edge  [fontname="Noto Sans CJK SC"];
  ```

  - **Linux / CI**: `Noto Sans CJK SC` (Simplified Chinese), `Noto Sans CJK TC` (Traditional Chinese), `Noto Sans CJK JP` (Japanese), `Noto Sans CJK KR` (Korean). For Latin scripts: `Noto Sans` or system default.
  - **macOS local**: `PingFang SC` is acceptable.
  - **Windows local**: `Microsoft YaHei` is acceptable.
  - **Always re-open the rendered PNG/SVG and visually check** — if you see `□` boxes, the font fallback failed silently. Switch to a font you know is installed.
  - For Mermaid `flowchart`, set `themeVariables.fontFamily` and verify in the output that CJK characters are intact.
- **Math and symbols**: inline Unicode (μ*, λ, ∫, ⊗) when the renderer supports it; LaTeX-style `\mu^*` only where the renderer supports it. When using DOT HTML-like labels (`<...>`), prefer Unicode for cross-renderer safety.
- **Brevity**: every node label ≤ 2 lines. First line = tag (role of node). Second line = numerical / equation / symbol anchor.

### 6. Audit table

One row per non-trivial edge. **Background and verification-support edges must always be documented in full** (downstream / upstream / class / bridge sentence / chain-payload anchor). For chain-support edges through a `gfac_*` factor (premises → diamond → root), full rows are *recommended but optional*: at minimum, document them once with the factor label as the bridge sentence; preferably, log each premise with its own anchor so the reader can verify the premise text is faithful to the chain payload.

| downstream | upstream | edge class | bridge sentence | chain-payload anchor |
|------------|----------|------------|-----------------|----------------------|

The chain-payload anchor points back into the LKM JSON: a premise id (`gcn_…`), factor id (`gfac_…`), `factors[i].steps[j].reasoning`, or claim content quoted verbatim. For verification-support edges that **partially disconfirm** the downstream node, state the polarity explicitly ("confirms within 5%", "partially disconfirms: independent value differs by 30%"). Without a chain-payload anchor, the row is just paraphrase.

### 7. Cycle check

Run `node scripts/check_dot_cycles.mjs <path-to-graph.dot>` (the script bundled with this skill) for DOT graphs. The decomposition is a DAG; cycles usually indicate a misclassified background edge — for example, a verification-style fact mis-rendered as background creates a cycle through the inversion step.

### 8. Best-effort numerical-anchor check

Before declaring the run complete, walk every numerical anchor in every reasoning node and try to locate it inside the chain payload — premise `content`, claim content, or `factors[i].steps[j].reasoning`. The check is **soft**: chain payloads are sometimes incomplete, and an anchor may legitimately not be locatable inside the JSON. When you can confirm an anchor, log the chain-payload location in the audit row. When you cannot, mark the row `anchor not locatable in chain payload` and leave the node in place — do not delete the node, do not invent a substitute, and do not fail the run on this alone. A node whose value is contradicted by some other piece of the chain payload, however, is a real error and must be fixed. This "contradicted anchor" case is source-consistency checking, not the contradiction-admission rule used by LKM-to-Gaia packages.

## Return value

On success, return the run-folder path. The folder contains the structured graph (`evidence_graph.json`), the canonical re-renderable source (`evidence_graph.dot` and/or `evidence_graph.mmd`), the rendered raster (`evidence_graph.png`, plus optional SVG/PDF), the audit table, and the verbatim raw payloads under `raw/`. The relevant `data.papers` block from the chain payload is preserved verbatim under `raw/` so any downstream consumer (or the user directly) can map background-node mentions back to bibliographic records.

On failure (chain-less root, contradicted anchors that cannot be reconciled, cycle detected after re-classification, CJK glyphs rendering as tofu and no installed font usable), report the failure reason and the run-folder state — do not declare partial success.

## What this skill is NOT

- Not a literature-genealogy graph. External papers are background nodes, not tier-1 upstream conclusions.
- Not a thematic survey. Single root, single result, single paper's reasoning anatomy.
- Not a renderer-of-record for purely qualitative conclusions. Qualitative claims (e.g. "X exhibits property Y") without a numeric or formula-level anchor do not have a closure step to decompose; this skill does not apply.
