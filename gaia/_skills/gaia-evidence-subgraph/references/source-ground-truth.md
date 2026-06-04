# Chain-Payload Audit Discipline

LKM chain payloads (`gaia search lkm knowledge` recall + `gaia search lkm reasoning --claim-id <id> --format raw-json` chains) are this skill's **single source of truth**. Current claim-reasoning payloads are graph-shaped by default (`reasoning_chains[].graph.nodes[]` / `graph.edges[]`), while older payloads may carry `factors[]`. Every node in the graph and every audit row must trace back into that JSON — no external paper text, no agent paraphrase, no synthetic bridging.

## Why the discipline matters

The graph claims to be *chain-backed*. That claim is meaningful only if a reader or auditor can take any node or edge and follow the audit table back to a specific piece of LKM-returned content. Two failure modes silently break the contract:

1. **Synthetic bridging** — minting an intermediate-result node because "the closure chain obviously needs one here", even though no graph node, graph edge, premise / step / claim content in the payload mentions it. This makes the graph indistinguishable from agent paraphrase.
2. **Floating numerical anchors** — quoting a value on a node that does not appear inside any premise content, claim content, or `steps[].reasoning` in the chain. The number then has no provenance the user can verify.

The discipline below is what prevents both.

## Anchor sources (in priority order)

For each node and edge, pick the most specific anchor available:

| Anchor | What it points to |
| --- | --- |
| `graph.nodes[id=<gcn_* or paper:* or lfac_*>]` | A claim, question, or factor node inside a graph-shaped chain. Quote `content` verbatim when present. |
| `graph.edges[source=<id>,target=<id>,type=<relation>]` | A graph-shaped chain edge. Preserve the LKM relation name (`concludes`, `motivates`, `previous_conclusion_of`, `weakpoint_of`, `highlight_of`, etc.) as an audit fact. |
| `gcn_<premise_id>` | A native premise claim, either a graph claim node that points to a factor or a legacy `factors[].premises[]` entry. Quote `content` verbatim. |
| `gfac_<factor_id>` / `lfac_<factor_id>` | A factor diamond. Quote `subtype` and the cluster semantics implied by its premises. |
| `factor.steps[j].reasoning` / `factors[i].steps[j].reasoning` | An optional step note inside a factor — not always populated. When present, treat as second-class evidence after premise content. |
| Root `data.claim.content` | The root claim text itself. Use only on the root node. |
| `data.papers[paper:<id>]` | Bibliographic metadata for a `source_package`. Use for `gaia-scholarly-synthesis` references; **never** as the source of a graph node's text. |

If none of these contain what you want to assert, the assertion does not belong in the graph.

## Chain-payload anchor in the audit row

Every audit-table row carries a `chain-payload anchor` column (last column). Examples:

| What you are anchoring | Anchor value |
| --- | --- |
| A graph edge saying a claim is a premise of a factor | `graph.edges[source=gcn_...,target=lfac_...,type=weakpoint_of]` |
| A premise rendered as an intermediate-result node | `gcn_a1b2c3…` |
| A factor diamond label | `gfac_d4e5f6… (subtype=noisy_and)` |
| A step-level numerical claim | `gfac_d4e5f6…/steps[0].reasoning` |
| The root result | `data.claim.content` |
| A polarity remark on a verification edge | `gcn_…/content: "…differs by 30%…"` |

Where a quotation is short and load-bearing, include it inline (`gcn_…/content: "Δ/Q ≈ 0.066"`) rather than just the id.

## Best-effort numerical-anchor check

Walk every numerical anchor on every reasoning node and try to find it inside the chain payload. The check is **soft**:

- **Located** → record the anchor cell and move on.
- **Not located, but consistent with related premises** → mark `anchor not locatable in chain payload`. Leave the node and value in place; do not delete, do not substitute. Chain payloads are sometimes incomplete and this row simply records that fact.
- **Located, but contradicted** by another premise / step / claim in the same payload → real error. Fix the node (re-read the contradicting premise) before publishing. This is payload-internal source consistency checking, not the Gaia contradiction-admission rule defined for LKM-to-Gaia packages.

The goal is no fabrication — not exhaustive coverage. A graph with a few `anchor not locatable` rows is still chain-bounded; a graph with one undeclared synthetic node is not.

## What is forbidden

- Reading the original paper (PDF, HTML rendering, scanned image, or otherwise) and pulling text from it into a node, label, or audit row.
- Paraphrasing a premise into a "tighter" form. Quote `content` verbatim or summarise it inside the audit row's bridge sentence — never both, never altered.
- Naming background nodes by paper id (`paper:…`). Background nodes are named by the formula / dataset / theorem / method as it appears in the LKM premise content; bibliographic metadata stays in `data.papers`.
- Adding a node whose label asserts a fact that no premise / step / claim content in the payload supports, even when the fact is "obviously true" in the field.

## Multi-sub-model papers

When a single paper analyses multiple sub-models / variants and LKM has split it into several claims, each chain-backed claim id is a candidate root. Pick **one** as the root for this graph and limit nodes to that claim's `reasoning_chains[].graph` (or legacy `evidence_chains` / `factors[]`). If the user wants the other sub-models, that is a separate run with a different root id.

If the chain you receive is missing a sub-model the user expected to see, run targeted `gaia search lkm knowledge` queries (`--retrieval-mode lexical --keywords <sub-model's distinctive terms> --scopes claim`) for that sub-model — do **not** import sub-model content from outside the chain payload.

## Caching

- Persist the raw `gaia search lkm reasoning --claim-id … --format raw-json` JSON (and the `gaia search lkm knowledge … --format raw-json` JSON that surfaced the candidate) under the run's working folder. The audit anchors are line-item references into that JSON; without the JSON the anchors lose meaning.
- Re-issue `evidence` if more than a few minutes pass between discovery and graph build — the corpus may have moved, and an anchor that used to resolve may not after a re-fetch. When this happens, prefer re-pinning the anchor over editing the graph.
