# Review Pipeline & Publish Workflow

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-11 |
| 状态 | **Draft — foundation design** |
| Supersedes | `architecture.md` sections on build context / build align |
| 关联文档 | [architecture.md](architecture.md), [../cli/command-lifecycle.md](../cli/command-lifecycle.md), [../server/architecture.md](../server/architecture.md) |

> **Note:** This document redefines the pipeline originally described in `architecture.md` as `compile → context → align → review`. That four-stage build pipeline is replaced by a simpler model: 3 CLI commands + 3 agent skills, with an academic-publishing-style peer review cycle at publish time.

---

## 1. Design Principles

1. **Review is knowledge.** Review findings, rebuttals, and editorial verdicts are expressed in Gaia language and can participate in BP. The review process forms a fiber bundle over the package — meta-knowledge attached to each knowledge unit.

2. **CLI commands do data I/O; intelligence lives in agent skills.** CLI commands (`build`, `infer`, `publish`) are deterministic or mechanical. Judgment-heavy work (self-review, graph construction, rebuttal writing) is done by agent skills.

3. **Local and remote are the same flow, different database.** `--local` targets local LanceDB + Kuzu; `--remote` targets server. The pipeline is identical.

4. **Academic publishing model.** The publish cycle mirrors paper submission: self-review → submit → peer review → revise/rebuttal → editor verdict → accept or reject.

## 2. Pipeline Overview

```
gaia build         compile (structural validation + elaboration)
                         │
                         ▼
                   agent skill: self-review (optional, recommended)
                         │
                         ▼
                   agent skill: graph construction / local parameterization
                         │
                         ▼
                   gaia infer         local BP on canonical graph + local parameterization (optional, preview)
                         │
                         ▼
gaia publish       submit package → triggers peer review cycle
                         │
                         ▼
                   ┌─────────────────────────────────┐
                   │  Peer Review → Rebuttal → Editor │ (may loop ≤5 rounds)
                   └─────────────────────────────────┘
                         │
                         ▼
                   approved → merge into LKM
                   rejected → return findings
                   under_debate → escalate to human (>5 rounds)
```

### CLI Commands (3 core)

| Command | Responsibility |
|---------|---------------|
| `gaia build` | Compile: schema validation, ref resolution, elaboration. Produces `manifest.json` + `package.md` + `raw_graph.json` |
| `gaia infer` | Read canonical graph + local parameterization, run BP, produce belief outputs |
| `gaia publish [--local \| --remote]` | Submit package to target DB. Triggers peer review cycle. Includes automatic re-compile on server side |

### Agent Skills (3 core)

| Skill | Responsibility |
|-------|---------------|
| self-review | Two-round LLM evaluation of reasoning quality |
| graph-construction | Build package-local canonical graph and, optionally, local preview parameterization |
| rebuttal | Process peer review findings: accept revisions or write rebuttals |

### Deferred

| Command | Description |
|---------|-------------|
| `gaia check` | Local mock peer review. Runs a local review engine as preview of what server will do. Not required for MVP |
| `gaia sync` | Pull latest versions of declared dependency packages. Like `cargo fetch` |

## 3. Self-Review Skill

### Purpose

Agent evaluates its own package's reasoning quality before submission. Produces weak point knowledge units and conditional priors for author-local use. Optional but recommended — a well-reviewed package is more likely to pass peer review.

### Two-Round LLM Protocol

```
Round 1 (LLM call 1):
  Input:  package.md
  Tasks:
    1. Evaluate conditional_prior_v1 for each chain
    2. Extract weak points → write as knowledge units (claim or setting)
    3. Mark unrelated refs (refs declared but not used by the reasoning)
  Output: conditional_prior_v1 + weak_point knowledge units + unrelated_refs

       ↓ Program: insert weak point knowledge units into document
                  remove unrelated refs
                  regenerate package.md_v2
                  DO NOT include conditional_prior_v1 (hidden from Round 2)

Round 2 (LLM call 2):
  Input:  package.md_v2
  Tasks:
    1. Classify each weak point knowledge unit: premise / context / unrelated
    2. Assign prior to each weak point knowledge unit
    3. Re-evaluate conditional_prior_v2 (independent of v1)
  Output: classified weak_points with priors + conditional_prior_v2
```

### Terminology

These definitions are included in every report header for self-containedness:

| Term | Definition |
|------|-----------|
| `conditional_prior` | Probability that the reasoning step is correct, ASSUMING all premise-classified knowledge units are true. Isolates reasoning quality from input reliability |
| `premise` | Knowledge that the reasoning necessarily depends on. If false, the conclusion fails |
| `context` | Background knowledge that frames the reasoning. The conclusion can stand without it |
| `unrelated` | Knowledge declared as a reference but not used by the reasoning process |

### Design Decisions

- **v1 is hidden from v2.** Prevents anchoring bias. Two independent assessments; the delta is a diagnostic signal (large delta = significant hidden dependencies).
- **Weak points are structured as knowledge units**, not free-text comments. They can be connected to the factor graph and participate in BP.
- **Unrelated ref detection in Round 1**, not Round 2. Reduces Round 2's input size and cognitive load.
- **Author-local probabilities are not submitted.** Self-review priors and conditional priors support local preview inference but are hidden from peer review engines, which must make independent judgments.

## 4. Graph Construction Skill

### Purpose

Agent builds a package-local canonical graph from all available knowledge: original package content, self-review weak points, and optionally external candidates from the server. It may also derive a local preview parameterization, but that parameterization is not submitted.

### Workflow

```
Inputs:
  - manifest.json (compiled package)
  - raw_graph.json (deterministic structural graph from `gaia build`)
  - self-review report (weak points with classifications and priors)
  - (optional) similar knowledge from server (via search API)

Steps:
  1. Collect all knowledge units (original + weak points)
  2. Cluster semantically similar propositions → local canonical nodes
  3. For each premise-classified weak point, connect to its chain's factor
  4. (If external candidates available) User/agent marks relationships:
     - equivalent    → merge nodes
     - supporting    → add positive factor
     - contradicting → add negative factor
     - unrelated     → skip
  5. Produce local_canonical_graph.json
  6. Optionally derive local_parameterization.json for `gaia infer`

Output:
  .gaia/graph/local_canonical_graph.json
  .gaia/inference/local_parameterization.json   -- local only, not submitted
```

### Key Property

This is an **agent skill, not a CLI command**. The agent can iterate: build graph → optionally parameterize locally → run `gaia infer` → inspect beliefs → adjust graph → re-run. Different agents may have different graph construction strategies. Only the structural graph is submitted.

## 5. Publish & Peer Review Cycle

### 5.1 Publish Triggers Peer Review

```
gaia publish [--local | --remote]
  │
  ├── --local:  target = local LanceDB + Kuzu
  │             review engine = local instance
  │
  └── --remote: target = server LanceDB + Kuzu
                review engine = registered, trusted server-side engines
```

Both modes follow the same pipeline. The only difference is the database target and which review engines are used.

### 5.2 Peer Review Engine Responsibilities

The review engine performs a full independent assessment:

1. **Re-compile** — do not trust client compilation
2. **Internal review** — independent reasoning quality assessment (does not see author's self-review probabilities or local parameterization)
3. **Global search** — check for duplicates, conflicts, missing refs, similar knowledge in target DB
4. **Graph validation** — verify the submitted structural graph and relationship labels
5. **Probability judgments** — if needed, record node-prior and reasoning-factor probability judgments directly in the peer review report without using author-local preview parameters
6. **Identity assignment** — after approval, record `CanonicalBinding` from each submitted LocalCanonicalNode to its target GlobalCanonicalNode

### 5.3 Review → Rebuttal → Editor Cycle

```
gaia publish
      │
      ▼
  Review Engine(s) → peer_review_report (findings)
      │
      ├── no blocking findings → Editor
      │
      └── has blocking findings → return to agent
              │
              ▼
        Agent skill: rebuttal
          - accept: revise package
          - rebuttal: write argument
          - dismiss: advisory only
          - defer: advisory, handle later
              │
              ▼
        gaia publish (with rebuttal_report attached)
              │
              ▼
          Review Engine(s) re-review + evaluate rebuttals
              │
              ├── resolved → Editor
              └── unresolved → loop (max 5 rounds)
                                  │
                                      └── >5 rounds → under_debate
                                       escalate to human
```

Once the package is approved, the registry writes `CanonicalBinding` records for the accepted local → global identity assignments and updates `GlobalInferenceState` using the approved review report plus the current global graph. These are review/registry metadata, not part of the submitted package artifacts.

### 5.4 Multi-Path Review as Gaia Knowledge Structure

The review process is itself a Gaia knowledge structure:

```
                    package.md
                   (premise)
                  /    |     \
                 /     |      \
    Review Engine 1  Engine 2  Engine 3    ← independent review chains
         |            |          |
    findings_1    findings_2  findings_3
         |            |          |
    rebuttal_1    rebuttal_2  rebuttal_3   ← author response chains
         \            |          /
          \           |         /
           ───────────┼────────
                      |
                   Editor                   ← synthesis chain
                      |
                final_verdict
              (approved / rejected)
```

- `package.md` = premise (the knowledge being reviewed)
- Each review engine = an independent reasoning chain
- Each rebuttal = a counter-chain responding to findings
- Editor = final synthesis chain consuming all reviews + rebuttals

All expressed in Gaia language. All can participate in BP. The review process forms a **fiber bundle** over the package — meta-knowledge attached to the base knowledge.

### 5.5 Per-Module Status & Visibility

Each module is tracked independently during review, but the package merges atomically:

```
Package status = min(all module statuses)

Any module not approved → entire package not merged
All modules approved    → entire package enters LKM, exports become searchable
```

**Module status transitions:**

```
pending_review → in_review → approved
                     │
                     ├── revision_required → (agent revises) → in_review
                     │                                             │
                     │                                       (round > 5)
                     │                                             │
                     │                                             ▼
                     │                                       under_debate
                     │                                       (human escalation)
                     │
                     └── rejected (editor decides package is fundamentally inadequate)
                           → author may revise and start a new gaia publish cycle
                             (new cycle, round counter resets)
```

**Terminal states:** `approved`, `rejected`, `under_debate`. A `rejected` package can always be revised and resubmitted via a new `gaia publish` — rejection applies to the current submission, not to the knowledge permanently.

**Visibility rules:**

| Status | Exports searchable? | Can be referenced? |
|--------|--------------------|--------------------|
| approved | Yes | Yes |
| All others | No | No |

Only `approved` packages' exported knowledge enters the global graph and becomes discoverable by other packages' graph construction or search.

**Note on peer review search:** Review engines perform high-recall global search and may return both exported and intermediate knowledge as candidates. Intermediate results are labeled as such in the response. This does not violate the visibility rule above — intermediate knowledge is not independently addressable or referenceable by other packages, but review engines can surface it as context for conflict/duplicate detection.

## 6. Report Formats

### 6.1 Peer Review Report

```yaml
peer_review_report:
  package: galileo_falling_bodies
  engine: "gaia-review-engine-v1"
  engine_version: "1.2.0"
  timestamp: "2026-03-11T10:00:00Z"
  round: 1
  local_graph_hash: "sha256:abc123..."

  verdict: revision_required    # approved | revision_required | rejected

  # ── Terminology ──
  # category:
  #   structural    — compile/schema issues
  #   reasoning     — reasoning quality issues
  #   duplicate     — semantically overlapping with existing knowledge
  #   missing_ref   — relevant existing knowledge not referenced
  #   contradiction — conflicts with existing knowledge
  #   graph         — factor graph structure issues
  #
  # severity:
  #   blocking  — must be resolved before merge
  #   advisory  — recommendation, can be dismissed without rebuttal

  findings:
    - id: structural_001
      category: structural
      severity: blocking
      target: "reasoning.synthesis_chain"
      description: "chain step 2 references vacuum_env as direct dependency,
                    should be indirect (settings are typically context)"
      suggestion: "Change dependency to indirect"

    - id: reasoning_001
      category: reasoning
      severity: blocking
      target: "reasoning.inclined_plane_chain"
      description: "Reasoning gap between inclined plane acceleration trend
                    and free-fall equal velocity conclusion"
      suggestion: "Add bridging reasoning step"

    - id: conflict_001
      category: duplicate
      severity: blocking
      target: "reasoning.vacuum_prediction"
      related: "newton_principia.equal_fall_derived"
      similarity: 0.94
      description: "Highly similar to existing knowledge, relationship needed"
      suggestion: "Mark as equivalent or supporting with justification"

    - id: conflict_002
      category: missing_ref
      severity: advisory
      target: "aristotle.heavier_falls_faster"
      related: "newton_principia.universal_law"
      description: "Aristotle's doctrine already refuted from another angle
                    by newton package, consider referencing"

  # Optional probability judgments used by the registry after approval.
  # Keys may be full local IDs or unambiguous local short prefixes.
  node_prior_judgments:
    "lcn_00af91": 0.82
    "lcn_17c2b4": 0.61

  factor_probability_judgments:
    "f_0192aa":
      conditional_probability: 0.78
```

### 6.2 Rebuttal Report

```yaml
rebuttal_report:
  package: galileo_falling_bodies
  author: "agent-galileo-v2"
  timestamp: "2026-03-11T12:00:00Z"
  round: 1
  in_response_to: "gaia-review-engine-v1"

  # ── Action rules ──
  # blocking findings:  accept | rebuttal (dismiss/defer not allowed)
  # advisory findings:  accept | rebuttal | dismiss | defer
  #
  # accept:   issue resolved, package revised
  # rebuttal: disagree, argument provided
  # dismiss:  advisory only, acknowledged but not acted on
  # defer:    acknowledged, will address in future version

  responses:
    - finding_id: structural_001
      action: accept
      revision: "Changed vacuum_env dependency from direct to indirect"

    - finding_id: reasoning_001
      action: accept
      revision: "Added bridging step incline_to_freefall_bridge"

    - finding_id: conflict_001
      action: rebuttal
      argument: "galileo_falling_bodies.vacuum_prediction and newton::equal_fall_derived
                 reach similar conclusions via entirely different paths:
                 Galileo uses reductio ad absurdum from thought experiment;
                 Newton uses mathematical derivation from universal gravitation.
                 These should be 'supporting' (independent paths to same
                 conclusion), not 'equivalent' (interchangeable)."
      proposed_relation:
        type: supporting
        from: "galileo_falling_bodies.vacuum_prediction"
        to: "newton_principia.equal_fall_derived"

    - finding_id: conflict_002
      action: dismiss
      reason: "This package focuses on Galileo's independent argument.
               Cross-system integration deferred to a future package."
```

## 7. Relationship to Git

### Package Development (git-native)

Package development uses standard git workflow. Teams choose their own branching/PR strategy. This is independent of Gaia's publish/review system.

### Knowledge Integration (Gaia publish)

`gaia publish` is a separate action from `git push`:

- `git push` → pushes source files to package repo remote
- `gaia publish` → submits package to knowledge database (local or server)

These can be coupled via automation (e.g., merge-to-main webhook triggers `gaia publish`), but are conceptually independent.

### Identity Conflict Resolution

During peer review's global search phase:

| Case | Situation | Action |
|------|-----------|--------|
| ID exists, content matches | Package references external knowledge correctly | Pass |
| ID exists, content differs | Package has stale/modified version of external knowledge | Blocking finding: must sync to authoritative version |
| ID not found | New knowledge | Global search returns similar candidates (exported + intermediate) for relationship marking |

**Exported vs Intermediate knowledge:**
- Exported: explicitly declared in `package.yaml` `export` list, have independent BP, are primary search targets
- Intermediate: internal chain knowledge, not in `export` list, no independent BP

**Intermediate promotion:** Export is always an explicit package-level declaration. When the server detects an intermediate node referenced by many external packages, it upgrades the source package: increment version, add the node to `export`, and trigger BP recomputation. This preserves the invariant that export is a deliberate author/system action, not an implicit side effect.

## 8. Superseded Decisions

The following decisions from `architecture.md` v4.0 are replaced:

| architecture.md (old) | This document (new) | Rationale |
|----------------------|---------------------|-----------|
| `gaia build` = compile + context + align | `gaia build` = compile only | Context and align are not build steps; context is a search operation, align is part of peer review |
| `gaia build context` constructs package environment | Removed as CLI command | Search for external knowledge happens during graph construction (agent skill) or peer review (server-side) |
| `gaia build align` performs open-world relation discovery | Removed as CLI command | Relation discovery is done by peer review engines, not by the author's CLI |
| `gaia review` is the final assessment boundary after build | Self-review is an agent skill; peer review happens at publish time | Review is decoupled from build; two layers of review (self + peer) replace one |
| Build, review, and inference are three sequential phases | Build and infer are CLI commands; review is split into self-review (skill) and peer review (publish-time) | Intelligence in skills, mechanics in CLI |

## 9. Open Questions

1. **Review engine registration** — how are review engines registered and trusted? Domain-specific engines (physics, biology)?
2. **Editor implementation** — single LLM call or multi-step? How does it weigh conflicting review engines?
3. **Fiber bundle storage** — how are review/rebuttal chains stored relative to the base package in LanceDB + Kuzu?
4. **Rebuttal BP integration** — how exactly do review findings and rebuttals connect to the factor graph? Factor weights?
5. **`gaia sync`** — detailed design for dependency fetching and version resolution
