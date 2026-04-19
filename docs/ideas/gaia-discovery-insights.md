# Insights from gaia-discovery for Gaia Lang v6

> **Date:** 2026-04-19  
> **Context:** Analysis of SiliconEinstein/gaia-discovery — an MCTS-based scientific discovery engine that compiles to Gaia IR

---

## Executive Summary

gaia-discovery (DZ) is an exploration-first system that uses MCTS + LLMs to automatically discover mathematical conjectures and scientific hypotheses, then compiles them to Gaia IR for probabilistic inference. It represents the opposite workflow from Gaia's formalization-first approach: **belief search drives structure growth** rather than structure being authored first.

The two systems are complementary ends of the same pipeline:

```
DZ (exploration) → candidate propositions → human review → Gaia (formalization) → publication
```

This document extracts design patterns from DZ that could inform Gaia Lang v6.

---

## Architecture Overview

### DZ's Four-Package Stack

```
dz-mcp          (MCP server — 6 tools for AI agents)
    ↓
dz-engine       (MCTS orchestration, HTPS selection, UCB/RMaxTS search)
    ↓
dz-verify       (claim extraction → multi-path verification → write-back)
    ↓
dz-hypergraph   (core data model, Gaia IR bridge, BP inference)
    ↓
gaia-lang       (external: compiler, IR, validator, lowering, InferenceEngine)
```

### Core Data Model

**Node** — a proposition with dual state:
- Discrete: `unverified` / `proven` / `refuted` (locked when proven/refuted)
- Continuous: `belief` ∈ [0,1], `prior` ∈ [0,1] (updated by BP)

**Hyperedge** — a reasoning step: `premise_ids → conclusion_id`, with:
- `module`: `PLAUSIBLE` / `EXPERIMENT` / `LEAN` / `ANALOGY` / `DECOMPOSE` / `SPECIALIZE` / `RETRIEVE`
- `edge_type`: `heuristic` / `formal` / `decomposition`
- `confidence`: factor confidence for BP

**HyperGraph** — flat graph of nodes + edges with O(1) adjacency indices. No package/module/version layering — the graph grows dynamically as MCTS explores.

### The Gaia IR Bridge

`bridge_to_gaia()` in `dz-hypergraph/bridge.py`:

1. Creates a `CollectedPackage` via `gaia.lang.runtime`
2. Maps every DZ `Node` → `DslKnowledge(type="claim")`
3. Maps every `Hyperedge` → `DslStrategy` (`formal` edges → `deduction`, others → `infer`)
4. Detects contradictions/equivalences → `DslOperator`
5. Compiles to `LocalCanonicalGraph` via `gaia.lang.compiler.compile_package_artifact()`
6. Builds `PriorRecord` and `StrategyParamRecord` for parameterization
7. Constructs CPT tables: for `infer` strategies, builds 2^n CPT where entry[0] = 1-p2 (no premises true), entry[2^n-1] = p1 (all premises true)

**Key insight:** Gaia IR can be **programmatically constructed** at runtime, not just compiled from static DSL files. This "runtime compilation" pattern is not currently exposed in Gaia Lang but could be formalized in v6.

---

## Key Differences: Formalization-First vs Exploration-First

| Dimension | Gaia (formalization-first) | DZ (exploration-first) |
|-----------|---------------------------|----------------------|
| **Graph origin** | Human-authored DSL | MCTS + LLM auto-generated |
| **Graph mutability** | Static after compilation | Dynamic, grows each iteration |
| **BP timing** | One-shot after compilation | Incremental after each verification |
| **Node state** | Only prior/posterior | Dual: discrete (proven/refuted) + continuous (belief) |
| **Reasoning module selection** | Human chooses Warrant pattern / relation / compute | Engine chooses (7 modules, UCB scheduling) |
| **Verification** | Human reviewer | Automated (Python sandbox / Lean / LLM judge) |
| **Identity** | Versioned `(knowledge_id, version)` | Flat node IDs, text-based deduplication |
| **Organization** | Package/module hierarchy | Flat hypergraph |
| **Provenance** | Package metadata + citation refs | Module tag on each edge |

---

## Design Patterns DZ Validates

### 1. Incremental BP

DZ runs BP incrementally: after each MCTS iteration adds new edges, it extracts the affected subgraph (nodes/edges reachable from changed edges), compiles and runs BP on the subgraph, then writes beliefs back.

**Why this matters for Gaia:** When a package updates a claim's prior, we don't need to re-run BP on the entire knowledge graph. Incremental BP could be upstreamed to `gaia.bp.engine` as a first-class feature.

**v6 implication:** The compiler should track dependency graphs at the IR level to enable efficient incremental inference.

### 2. Runtime Compilation API

DZ constructs Gaia IR programmatically via `CollectedPackage` + `compile_package_artifact()`. This proves that Gaia IR can be a **compilation target** for non-DSL sources.

**v6 implication:** Formalize the "runtime compilation" pattern. Let `@compute` functions not only return values but also emit new Claims and reasoning structures. This enables:
- AI-assisted hypothesis generation that compiles to valid Gaia packages
- Dynamic knowledge graph construction from external sources
- Programmatic package synthesis for testing/benchmarking

### 3. Dual Node State: Discrete + Continuous

DZ nodes have both discrete status (`proven`/`refuted`/`unverified`) and continuous belief. Proven/refuted nodes are locked — BP cannot change them.

**Why this matters for Gaia:** Some discovery outputs are qualitatively different from heuristic guesses: a Lean proof should be treated differently from an LLM plausibility judgment. But this should be handled by review/inference policy, not by changing the Claim type.

**v6 implication:** Do not add a general `locked` Claim state to v6 core. If a verifier establishes a theorem or exact refutation, the review layer can assign the appropriate prior/parameterization policy while the persisted graph remains ordinary Claim + support/relation structure.

### 4. Module Provenance on Edges

Every DZ hyperedge records which module (`PLAUSIBLE`/`EXPERIMENT`/`LEAN`) produced it. This enables confidence differentiation: formal proofs get higher confidence than heuristic reasoning.

**Why this matters for Gaia:** Gaia's user-facing `supported_by(..., pattern=...)`, `compute`, and relation wrappers encode this intent at authoring time. Inquiry/review tools should be able to reconstruct enough traceability from Warrant labels, generated review Questions, source locations, and provenance.

**v6 implication:** Do not introduce Action IR. Preserve source traceability and provenance for generated Warrant/Strategy/Operator objects so tools can support:
- InquiryState filtering by evidence type ("show only experimentally verified claims")
- Confidence calibration by reasoning type
- Audit trails for warrant review

### 5. Custom CPT Construction for Soft Entailment

DZ builds full 2^n CPT tables for `infer` strategies where:
- Entry[0] (no premises true) = 1 - p2 (base rate)
- Entry[2^n-1] (all premises true) = p1 (full support)
- Intermediate entries interpolated

This is more nuanced than Gaia's current degraded noisy-AND default.

**v6 implication:** Expose CPT construction as a first-class parameterization option. Let reviewers specify not just `prior` but also `base_rate` and `full_support` for soft entailment strategies.

---

## Design Patterns from DZ That v6 Should Adopt

### 1. Bridge Plans — Structured Proof Strategies

DZ's `BridgePlan` model grades propositions into four tiers:
- **A-grade:** Formal proof required (Lean verification)
- **B-grade:** Partial verification (computational check)
- **C-grade:** Experimental support (empirical evidence)
- **D-grade:** Heuristic plausibility (LLM reasoning)

Each tier has explicit dependencies and verification methods.

**Why this is better than Gaia's InquiryState:** It's not just "what's missing" but "what to verify next and how."

**v6 proposal:** Extend InquiryState to include a **verification plan**:

```python
$ gaia check --inquiry

Goal: quantum_hyp [posterior=0.85]
  
  Verification plan:
    A: planck_spectrum (compute, verified ✓)
    B: uv_catastrophe (pattern=observation, reviewed ✓)
    C: planck_resolves (pattern=explanation, needs review ⚠)
    D: classical_fails (pattern=elimination, low confidence, optional)
  
  Suggested next action: Review warrant for planck_resolves
  Expected posterior gain: 0.85 → 0.92 if approved
```

This makes InquiryState **actionable** — it tells the user what to do next, not just what's incomplete.

**Implementation:** Keep bridge tiers in the inquiry/tooling layer, not Gaia Lang core. InquiryState can compute marginal belief gains from the existing Claim + Strategy/Operator graph and display a verification plan without adding new Claim fields.

### 2. Claim Type Classification → Verification Strategy

DZ classifies claims into three types, each with a default verification method:

| Claim Type | Verification Method | Example |
|-----------|-------------------|---------|
| `quantitative` | Python experiment (sandbox execution) | "The sum of first n primes is O(n² log n)" |
| `structural` | Lean formal proof | "Every finite group has a Sylow p-subgroup" |
| `heuristic` | LLM judge evaluation | "This analogy between thermodynamics and information theory is plausible" |

**v6 implication:** Treat this as verification routing, not Claim ontology. A claim should not become a `QuantitativeClaim` or `StructuralClaim` subclass merely because one tool can verify it a certain way. The same stable Claim may later be supported by computation, citation, experiment, and formal proof.

For v6.0, this should remain outside Gaia Lang core:
- discovery tools may classify generated candidates before choosing a verifier;
- review tools may display the Warrant pattern used by a support edge;
- the persisted Gaia graph remains ordinary Claim + support/relation structure.

### 3. Critical Gap Analysis — Structural Bottleneck Detection

DZ's `BeliefGapAnalyser.find_critical_gaps()` identifies upstream nodes where proving them would produce the largest marginal belief gain on the target. This is a **graph-structural heuristic** — it finds bottlenecks on reasoning paths.

**Why this matters for Gaia:** Not all holes in an argument are equally important. Some claims, if established, would unlock large belief gains downstream. Others are peripheral.

**v6 proposal:** Add `--critical-gaps` flag to InquiryState:

```python
$ gaia check --inquiry --critical-gaps

Goal: safe_to_operate [posterior=0.65, target=0.95]

  Critical gaps (ranked by marginal gain):
  1. corrosion_rate_model [0.70 → 0.88 if proven] ⚠ HIGH IMPACT
     - Single evidence path, no redundancy
     - Blocks 3 downstream claims
  
  2. inspection_reliability [0.80 → 0.85 if proven]
     - Multiple support paths exist
     - Lower priority
```

**Implementation:** Run counterfactual BP: for each unverified claim, set its posterior to 1.0 and measure the belief change on the target. Rank by delta.

### 4. Stall Detection and Strategy Switching

DZ tracks multiple stall indicators:
- `belief_stall_count`: target belief unchanged for N iterations
- `plausible_stall_cycles`: PLAUSIBLE module repeatedly fails
- `consecutive_same_module`: same module used M times in a row
- `target_isolation_streak`: target node has no new incoming edges

When stuck, it cycles through PLAUSIBLE → DECOMPOSE → ANALOGY.

**Why this matters for Gaia:** Human authors can also get stuck — repeatedly trying the same reasoning pattern without progress.

**v6 proposal:** Add **workflow hints** to InquiryState when it detects stalls:

```python
$ gaia check --inquiry

Goal: quantum_hyp [posterior=0.75, unchanged for 3 commits]

  ⚠ Stall detected: No belief gain in recent updates.
  
  Suggestions:
  - Try a different Warrant pattern (current: induction, consider: abduction)
  - Decompose the claim into sub-claims
  - Look for analogies in related domains
  - Add experimental evidence (only theoretical support so far)
```

**Implementation:** Track belief history in package metadata. Detect stalls and suggest alternative Warrant patterns based on what's been tried.

---

## What v6 Can Offer Back to DZ

### 1. Versioned Identity

DZ uses flat node IDs and deduplicates by text matching. As graphs grow across sessions, this becomes fragile.

**Gaia's solution:** `(knowledge_id, version)` provides stable identity with evolution tracking. DZ could adopt this for cross-session knowledge reuse.

### 2. Package/Module Structure

DZ's flat hypergraph lacks organizational structure. Large discovery graphs (1000+ nodes) would benefit from Gaia's hierarchical package/module model for:
- Archival and sharing
- Scoped reasoning (run BP on a subgraph corresponding to one research question)
- Provenance tracking (which discovery session produced which claims)

### 3. Human Review Pipeline

DZ does automated verification (Python/Lean/LLM) but lacks Gaia's human reviewer model. For AI-discovered claims to enter the curated knowledge graph, they need human review.

**Integration point:** DZ's `save_gaia_artifacts()` already produces `.gaia/` directories. These could be ingested by Gaia's review pipeline:

```
DZ discovers → saves as Gaia package → human reviewer audits → approved package published
```

v6 should formalize this workflow: a "provisional" package state for AI-generated content awaiting review.

### 4. Graph Store Integration

DZ persists to flat JSON files. Gaia's LanceDB + Neo4j backend would enable:
- Multi-graph queries (find all claims about "superconductivity" across discovery sessions)
- Cross-session knowledge reuse (avoid re-discovering known results)
- Vector similarity search over established propositions

### 5. Canonical IR as Interchange Format

DZ already compiles to Gaia IR. v6 should strengthen this as the **standard interchange format** for scientific knowledge:
- DZ (exploration) → Gaia IR → Gaia (formalization)
- Argument mining tools → Gaia IR → Gaia packages
- Nanopublications → Gaia IR → Gaia packages

This positions Gaia IR as the "LLVM IR of scientific reasoning."

---

## Concrete v6 Design Recommendations

### High Priority (Should Be in v6.0)

1. **Keep Claim identity stable** — no `Hypothesis`/`Observation`/`QuantitativeClaim` subtype split for roles or verification routes
2. **Represent Warrant as a Claim subtype with `pattern`, generated review Questions, `reason`, and stable labels** — enough for review/inquiry tools to reference and audit each argument step
3. **Formalize runtime compilation API** — document `CollectedPackage` + `compile_package_artifact()` as a public API for programmatic package construction
4. **Keep source-first exploration sugar deferred** — discovery tools can still emit plain Claim + Warrant + Strategy graphs in v6.0

### Medium Priority (v6.1 or Later)

5. **Extend InquiryState with verification plans** — structured proof strategies with graded propositions
6. **Add critical gap analysis** — rank unverified claims by marginal belief gain
7. **Add stall detection and workflow hints** — suggest alternative reasoning approaches when stuck
8. **Support incremental BP** — upstream DZ's subgraph extraction pattern into `gaia.bp.engine`

### Low Priority (Future Research)

9. **Custom CPT parameterization** — expose `base_rate` and `full_support` for soft entailment
10. **Provisional package state** — for AI-generated content awaiting human review
11. **Cross-system knowledge reuse** — shared graph store for DZ and Gaia

---

## Conclusion

gaia-discovery validates that Gaia IR is a robust compilation target for non-DSL sources and that BP scales to dynamically growing graphs. The two systems are complementary:

- **DZ excels at exploration** — rapidly generating candidate hypotheses and reasoning paths
- **Gaia excels at formalization** — curating, reviewing, and publishing established knowledge

v6 should design the interface between these workflows: making it easy for AI-discovered propositions to flow into the human-curated knowledge graph after review. The bridge already exists (`bridge_to_gaia()`); v6 should formalize and strengthen it.

The most valuable patterns from DZ for v6 are:
1. **Bridge plans** — actionable verification strategies
2. **Claim type classification** — verification method selection
3. **Critical gap analysis** — structural bottleneck detection
4. **Runtime compilation** — programmatic IR construction

These would make Gaia Lang not just a formalization tool but also a **discovery-aware** system that can guide users toward the most impactful next steps in their reasoning.
