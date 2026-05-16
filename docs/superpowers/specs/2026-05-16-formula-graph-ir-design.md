# Formula Graph IR Foundation

Date: 2026-05-16
Status: Draft for review
Scope: Gaia v0.5, minimal canonical formula graph spine

## Goal

Add the smallest durable foundation for formula-level structure in Gaia:

1. A canonical identity for formula atoms and formula sub-expressions.
2. A claim-scoped `FormulaGraph` IR artifact anchored to source claims.
3. Validation rules that treat formulas as hard logic without rejecting normal
   scientific disagreement between separate claims.
4. A future-safe path for logic diagnostics, user inspection, and knowledge
   graph projection.

This is a semantic spine, not a new authoring hierarchy. Authors still write
`claim(formula=...)` in Gaia Lang. The compiler canonicalizes that formula into
IR. Later tools consume the IR-backed graph instead of reinterpreting runtime
Python objects.

## First Principles

Gaia needs two separations:

- `GaiaGraph` records are authored graph records such as reasoning and
  scaffold. Formula nodes are not authored reasoning steps and should not
  inherit from `GaiaGraph`.
- `Claim.formula` is authoring syntax. Stable package semantics require a
  JSON-serializable, content-addressed IR representation.

The minimal complete contract is therefore:

```text
Gaia Lang Formula AST
  -> compiler canonical descriptors
  -> claim-scoped FormulaGraph IR
  -> existing Knowledge / Operator / Strategy lowering
  -> logic diagnostics, BP, inspect APIs, and future KG projection
```

Formula graph is not a replacement for the existing ground IR. The current
`Knowledge`, `Operator`, and `Strategy` records remain the structures consumed
by BP and existing propositional logic tools. `FormulaGraph` makes the
fine-grained formula structure explicit and stable.

## Non-Goals

- No full first-order theorem prover.
- No ontology system or entity resolution.
- No knowledge graph projection in the first implementation PR.
- No user-facing browser or visualization UI in the first implementation PR.
- No migration of `GaiaGraph`, `Reasoning`, or `Scaffold` into the formula
  model.
- No change to the existing finite-domain quantifier grounding semantics.
- No compile failure for ordinary cross-claim scientific disagreement.

## Current Code Facts

The current v0.5 code already has most authoring pieces:

- `Claim` carries `formula` and `kind` in
  `gaia/engine/lang/runtime/knowledge.py`.
- Formula AST classes live under `gaia/engine/lang/formula`.
- `lower_formula.py` already lowers atom, connective, and finite-domain
  quantifier formulas into generated `Knowledge`, `Operator`, `Strategy`,
  metadata, and parameter updates.
- `LocalCanonicalGraph` currently stores `knowledges`, `operators`,
  `strategies`, and `composes`, but no first-class formula graph.
- Current formula lowering can generate duplicate helper claims for repeated
  equivalent formula atoms because helper identity is not yet derived from a
  canonical formula descriptor.

The design should reuse the existing formula descriptor and term descriptor
logic where possible instead of inventing a parallel parser.

## IR Model

Add a small IR module for formula graphs, for example
`gaia.engine.ir.formula`:

```python
class FormulaGraph(BaseModel):
    source_claim: str
    root: str
    nodes: list[FormulaNode]
    edges: list[FormulaEdge] = []


class FormulaNode(BaseModel):
    id: str
    kind: Literal["atom", "op", "term", "variable", "constant", "binding", "quantifier"]
    descriptor: dict[str, Any]
    source_claim: str | None = None


class FormulaEdge(BaseModel):
    source: str
    target: str
    role: str
```

Extend `LocalCanonicalGraph` with:

```python
formula_graphs: list[FormulaGraph] = []
```

Include `formula_graphs` in canonical JSON and hash computation once the field
is introduced. The graph is package content, not ephemeral metadata.

### Node Identity

Formula node identity should be content-addressed from canonical descriptors:

```text
fg:<short-hash(canonical descriptor)>
```

For atom nodes, the `source_claim` should not be part of the semantic node id.
This lets the same `P(x)` receive the same formula atom id when it appears in
multiple formulas. The `FormulaGraph` record remains anchored to the source
claim that used the atom.

For connective and quantifier nodes, the descriptor includes the operator kind
and child ids or normalized child descriptors. This makes repeated sub-formulas
deduplicate inside the same graph and gives future diagnostics stable handles.

## Compiler Boundary

Extend the formula lowering pipeline conceptually as:

```text
Formula AST
  -> canonical formula descriptors
  -> FormulaGraph
  -> existing IR lowering records
```

Add an internal builder:

```python
build_formula_graph(
    formula,
    *,
    source_claim_id: str,
    knowledge_map: dict[int, str],
    namespace: str,
    package_name: str,
) -> FormulaGraph
```

Extend `FormulaLoweringResult`:

```python
@dataclass(frozen=True)
class FormulaLoweringResult:
    knowledges: list[IrKnowledge] = field(default_factory=list)
    operators: list[IrOperator] = field(default_factory=list)
    strategies: list[IrStrategy] = field(default_factory=list)
    formula_graphs: list[FormulaGraph] = field(default_factory=list)
    metadata_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    parameter_updates: dict[str, list[IrParameter]] = field(default_factory=dict)
```

The compiler should promote the existing private descriptor helpers into a
shared internal contract:

```python
canonical_formula_descriptor(formula, bindings, knowledge_map) -> dict[str, Any]
canonical_term_descriptor(term, bindings, knowledge_map) -> dict[str, Any]
formula_node_id(descriptor) -> str
```

Lowering keeps the current `Knowledge`, `Operator`, `Strategy`, metadata, and
parameter behavior. The first PR should avoid broad BP behavior changes.

### Formula Shapes

Initial graph support should cover the current formula lowering surface:

- `ClaimAtom(existing_claim)` becomes an atom descriptor with the referenced
  claim QID.
- `UserPredicate(symbol, args)` becomes a predicate atom descriptor.
- `Equals`, `NotEquals`, and inequalities become atomic formula descriptors
  over canonical term descriptors.
- `Land`, `Lor`, `Lnot`, `Implies`, and `Iff` become op nodes with operand
  edges.
- `Forall` and `Exists` become quantifier nodes with variable and body edges,
  while preserving the current finite-domain grounding behavior.

Unsupported primitive-domain quantifier grounding should keep raising the
existing error. The formula graph may still be buildable for inspection later,
but this first slice does not need partial compile artifacts after a lowering
failure.

### Helper Claim Identity

Generated formula helper claims should derive their ids from canonical
descriptors where possible.

Example:

```python
claim("P and P", formula=land(UserPredicate(P, (x,)), UserPredicate(P, (x,))))
```

Expected first-slice behavior:

- one canonical predicate atom node for `P(x)`;
- the conjunction has two operand edges to that same atom node;
- generated helper claims do not treat the two identical atoms as independent
  semantic atoms.

This fixes the current duplicate-atom problem without changing the public
authoring surface.

## Validation Semantics

Formula logic is hard logic, but Gaia packages may contain uncertain,
competing, or contradictory claims. Validation must distinguish three levels.

### 1. Structural Validation

These are hard failures in every profile:

- `FormulaGraph.source_claim` must reference an existing claim.
- `FormulaGraph.root` must reference an existing formula node.
- Every edge endpoint must reference an existing formula node.
- A node id must match the hash of its canonical descriptor.
- The same node id must not appear with different descriptors.
- Formula descriptors that reference claim QIDs must reference existing
  knowledges.

### 2. Formula Semantic Validation

These are about one formula graph as a hard logical expression:

- `P and not P` is unsatisfiable.
- `P or not P` is a tautology.
- `P and P` is redundant.

Unsatisfiable formulas should be treated as errors in strict or publish
profiles. In development profiles they may be reported as clear diagnostics so
the author can inspect the graph, but they must not silently pass.

Tautologies and redundancies are not contradictions, but they are usually poor
modeling signals for claims with priors. They should start as diagnostics, with
strict-profile behavior decided after real packages exercise the feature.

### 3. Theory-Level Consistency Diagnostics

These are about multiple claims, operators, and formula graphs together:

- separate claims assert `P` and `not P`;
- `P -> Q`, `P`, and `not Q` all appear in the package;
- deterministic operators make part of the package jointly unsatisfiable.

These should start as diagnostics rather than universal compile failures. A
scientific package may intentionally contain competing hypotheses or explicit
contradiction relations. The role of theory diagnostics is to reveal the
conflict and identify the responsible claims, not to forbid scientific
disagreement.

## Logic and Future User APIs

The first implementation should leave stable hooks for later work:

```python
gaia.engine.ir.logic.diagnostics.inspect_formula_graphs(graph)
```

Future diagnostics can use the canonical formula graph instead of reparsing
metadata:

- redundant formula atoms;
- formula unsatisfiability;
- formula tautologies;
- formula-to-lowered-operator mismatch;
- theory-level entailment and contradiction reports.

User-facing consumption should also be IR-backed:

```bash
gaia inspect formula-graph <claim-label-or-qid>
```

or:

```python
inspect_formula_graph(claim_or_qid)
```

These APIs are not required in the first PR, but the IR design should not block
them.

## Knowledge Graph Projection

Formula graph can later drive a provenance-aware knowledge graph projection:

```text
FormulaGraph atom: UserPredicate(P, (x, y))
KG projection:     relation P(x, y), source_claim=<claim qid>
```

The projection must preserve provenance and truth status. A formula appearing
inside a claim is not automatically an accepted fact. A future KG edge should
carry at least:

- source claim;
- package and module provenance;
- polarity and formula context;
- confidence or prior when appropriate;
- review or inference status.

KG projection is explicitly a later layer. FormulaGraph remains the semantic
source; KG is a query and navigation projection.

## Testing

The first implementation should add focused tests without rewriting the
existing formula lowering suite.

Required test coverage:

1. `land(P(x), P(x))` creates one canonical predicate atom node and two operand
   edges to it.
2. `land(ClaimAtom(a), ClaimAtom(a))` reuses one claim atom node.
3. `implies(land(ClaimAtom(a), ClaimAtom(b)), ClaimAtom(c))` produces the
   expected op graph shape.
4. `forall(x in finite Domain, P(x))` produces a quantifier node, a variable
   descriptor, and body edge while existing finite-domain grounding tests still
   pass.
5. Structural validation rejects dangling formula edges, missing roots, missing
   source claims, and descriptor/id mismatches.
6. Formula semantic validation reports unsatisfiable single-formula graphs such
   as `P and not P`.
7. Existing BP and formula lowering tests continue to pass.

## Suggested PR Sequence

### PR 1: Canonical FormulaGraph IR

- Add `FormulaGraph`, `FormulaNode`, and `FormulaEdge` IR models.
- Add `LocalCanonicalGraph.formula_graphs`.
- Build formula graphs during formula lowering.
- Use canonical descriptors for atom identity.
- Add structural validation and focused tests.

### PR 2: Formula Logic Diagnostics

- Move or expose reusable proposition-building logic under
  `gaia.engine.ir.logic`.
- Add single-formula unsatisfiable/tautology/redundancy diagnostics.
- Add strict/publish profile behavior for unsatisfiable formulas.

### PR 3: User Inspection

- Add CLI and Python APIs for inspecting formula graphs by claim label or QID.
- Keep output textual/JSON first; visualization can come later.

### PR 4: Knowledge Graph Projection

- Add provenance-aware KG projection from canonical formula graphs.
- Keep ontology and entity-resolution policy explicit and separable.

## Implementation Defaults

Use these defaults unless implementation reveals a direct compatibility problem:

- Formula node ids use `fg:` plus the first 16 hex characters of the SHA-256
  digest of canonical descriptor JSON.
- Each claim-scoped `FormulaGraph` stores its own node list. Identical semantic
  nodes may appear in multiple graphs with the same node id and descriptor.
  This keeps local inspection simple while preserving cross-claim identity.
- Default development compile emits unsatisfiable-formula diagnostics but does
  not fail solely for formula unsatisfiability. Strict and publish profiles
  fail on unsatisfiable single-formula graphs.
- Structural formula graph validation fails in every profile.
