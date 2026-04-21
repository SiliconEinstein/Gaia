# Gaia IR v6 Proposal: Strategy/Warrant-Aligned Minimal Redesign

> Status: design proposal  
> Date: 2026-04-20  
> Scope: canonical Gaia IR, review layer, and lowering contract  
> Design goal: align as much as possible with the current Gaia IR implementation while removing probabilistic warrant semantics.

---

## 0. Executive summary

Gaia IR v6 should **keep the current core shape**:

```text
Knowledge
Operator
Strategy
```

and add a package-level review layer:

```text
ReviewManifest / Warrant
```

The redesign is therefore not a rewrite. The main change is semantic:

```text
Old Strategy:
  probabilistic reasoning edge / strategy prior / warrant prior

New Strategy:
  reviewed information-use step that may assert generated helper claims,
  apply a likelihood score, or run/validate a computation.
```

The key v6 rules are:

1. **Only `Claim` carries epistemic probability.**
2. **`Strategy` carries no probability.**
3. **`Operator` remains deterministic and continues to have `conclusion` helper claims.**
4. **Generated helper claims are neutral unless asserted by an accepted Strategy.**
5. **The old implication “warrant helper” becomes `Strategy.assertions`.**
6. **`Warrant` moves to `ReviewManifest`; it is a review block, not a Claim and not a prior.**
7. **Statistical evidence is represented as `Strategy(type="likelihood")`, not as probabilistic support.**
8. **Raw unformalized text is represented by `Knowledge(type="context")`.**

This keeps the useful parts of the existing `Strategy / FormalStrategy / FormalExpr / Operator` framework, while removing the part that caused conceptual confusion: edge-level probability.

---

## 1. Why this redesign is needed

The current Gaia IR already has several good ingredients:

- `Claim` is the natural bearer of prior/posterior belief.
- `Operator` is deterministic and has an explicit `conclusion` helper node.
- `FormalStrategy` can embed a deterministic `FormalExpr` made of `Operator`s.
- The formalization pipeline already generates helper claims such as conjunction results, equivalence results, and implication results.

The problem is that current Strategy semantics mix several concerns:

```text
argument taxonomy      support / deduction / abduction / analogy / induction / compare
formalization shape    Strategy / CompositeStrategy / FormalStrategy
probability            strategy prior / warrant prior / conditional probability
review                 whether a step is acceptable, incomplete, or rejected
```

This becomes especially problematic for v6 because v6 wants two distinct kinds of reasoning:

```text
solid conditional reasoning:
  if the listed premises are true, the conclusion/helper assertion follows

statistical evidence:
  if the listed premises are true, apply a likelihood score to a target Claim
```

These should not both be represented as a single probabilistic `support` edge.

---

## 2. Non-goals

This proposal intentionally does **not** introduce a BP/backend object such as `Factor`, `PotentialFactor`, or `StatisticalOperator` into Gaia IR.

Gaia IR remains semantic. BP factors are a lowering target, not the IR vocabulary.

This proposal also does **not** design the final high-level relation surface API. Relation surfaces such as `equivalent(...)`, `contradicts(...)`, or `implies(...)` can be added later as Lang-level macros. The IR representation they lower into is described here, but the final user API is deferred.

---

## 3. Core object model

## 3.1 Package-level structure

```python
class GaiaPackage:
    graph: LocalCanonicalGraph
    review: ReviewManifest | None = None
```

```python
class LocalCanonicalGraph:
    knowledge: list[Knowledge]
    operators: list[Operator]
    strategies: list[Strategy]
```

The review manifest is deliberately separated from the canonical semantic graph:

```python
class ReviewManifest:
    warrants: list[Warrant]
```

This separation matters because review status can change without changing the semantic content of the graph.

---

# 4. Knowledge

## 4.1 Knowledge types

v6 should extend the existing knowledge type set to:

```python
Knowledge.type ∈ {
    "claim",
    "setting",
    "question",
    "context",
}
```

### `claim`

A proposition with truth value. This is the only Knowledge type that receives a prior/posterior and becomes a random variable during BP lowering.

### `setting`

Formalized background context, convention, or scope statement. It does not carry belief and does not become a BP variable.

### `question`

Inquiry lens or research target. It organizes exploration but is not itself a belief variable.

### `context`

Raw, not-yet-formalized text or artifact excerpt. Examples:

- paper paragraph
- experiment dashboard excerpt
- lab note
- reviewer comment source text
- LLM extraction input

A `context` item does not participate in BP. It provides traceability and raw material for later formalization.

## 4.2 Parameter values

Current Gaia parameters only distinguish name and type. v6 needs bound values so that ground parameterized claims are stable and hashable.

```python
class Parameter:
    name: str
    type: str
    value: JsonValue | None = None
```

The `value` must participate in the content hash or canonical ID of a ground parameterized Claim.

This is important for generated helper claims and statistical score claims such as:

```text
Equivalent[A, B]
Implies[G, C]
LikelihoodScoreRecord[target=H, module_ref=gaia.std.likelihood.two_binomial_ab_test@v1, score_type=log_lr, value=1.73]
```

### Knowledge references in parameters

When a parameterized Claim has a Knowledge-typed parameter (e.g., `experiment: Setting`), the parameter value stores the referenced Knowledge node's QID (qualified ID).

Example at Lang level:

```python
class ABCounts(Claim):
    """[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions."""
    experiment: Setting  # Knowledge-typed parameter
    ctrl_n: int
    ctrl_k: int
    treat_n: int
    treat_k: int

exp = Setting("AB test exp_123: 50/50 randomization, March 1-14.")
counts = ABCounts(experiment=exp, ctrl_n=10000, ctrl_k=500, treat_n=10000, treat_k=550)
```

At IR level:

```python
Knowledge(
    knowledge_id="github:my_package::counts",
    type="claim",
    content_template="[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions.",
    rendered_content="[@github:my_package::exp] recorded 500/10000 control conversions.",  # derived/display only
    parameters=[
        Parameter(name="experiment", type="Setting", value="github:my_package::exp"),  # QID reference
        Parameter(name="ctrl_n", type="int", value=10000),
        Parameter(name="ctrl_k", type="int", value=500),
        Parameter(name="treat_n", type="int", value=10000),
        Parameter(name="treat_k", type="int", value=550),
    ],
)
```

The `[@...]` syntax in `content_template` is resolved at compile time for rendering, not for canonical identity. Canonical hashing should use:

```text
Knowledge.type
content_template
sorted Parameter(name, type, value)
```

`rendered_content` is derived presentation data and must not participate in the canonical hash. This keeps display labels, package names, and link rendering from changing Claim identity. It also avoids storing the same reference twice as both an embedded rendered QID and a `Parameter.value`.

This allows:

1. **Stable hashing**: Parameter values (including QID references) participate in content hash
2. **Cross-package matching**: Two packages can reference the same Setting and match on it
3. **Rendering**: `[@label]` can be rendered as Markdown links in documentation
4. **Type safety**: Lang layer enforces that Knowledge-typed parameters receive Knowledge objects

## 4.3 Grounding metadata

A root Claim may include grounding metadata explaining why its prior exists.

```python
class Grounding:
    kind: Literal[
        "assumption",
        "source_fact",
        "definition",
        "imported",
        "judgment",
        "open",
    ]
    reason: str | None = None
    source_refs: list[str] = []
    prior_rationale: str | None = None
```

Grounding is metadata; it does not affect BP directly.

Recommended lint rule:

```text
Every root Claim with a non-default prior should have grounding metadata,
or be supported by a Strategy.
```

---

# 5. Operator

## 5.1 Keep the current Operator shape

v6 should keep the existing Operator idea:

```python
class Operator:
    operator_id: str | None = None
    scope: Literal["local"] | None = None
    operator: OperatorType
    variables: list[ClaimID]
    conclusion: ClaimID
    metadata: dict | None = None
```

The important existing invariant should remain:

```text
Operator.conclusion is separate from Operator.variables.
```

That is a good design. It reifies expression results as helper Claims.

## 5.2 Operator semantics

An Operator is deterministic:

```text
Operator defines conclusion = f(variables).
```

Examples:

```text
G = Conjunction(A, B, C)
R = Equivalence(A, B)
K = Contradiction(A, B)
S = Implication(G, C)
```

The crucial v6 change:

```text
Operator.conclusion is not automatically asserted true.
```

It is simply an expression-result helper Claim.

## 5.3 Helper claim default

All generated Operator helper Claims should default to neutral unless explicitly asserted:

```text
default prior/helper treatment = neutral
```

They must not be automatically pinned to `true` merely because they are relation helper claims.

This is the main change needed to prevent accidental unconditional relation assertions such as:

```text
Equivalent(A, B) automatically binds A and B.
```

In v6, `Equivalent(A, B)` creates the helper:

```text
R = same_truth(A, B)
```

but `R` matters only when some accepted Strategy asserts a helper that entails or uses `R`.

## 5.4 Helper metadata

Generated helpers should be tagged for traceability:

```python
metadata={
    "generated": True,
    "generated_kind": "helper_claim",
    "helper_kind": "implication_result" | "conjunction_result" | "equivalence_result" | ...,
    "visibility": "formal_internal" | "public",
    "owning_strategy_id": "...",
}
```

The exact existing helper naming mechanism can be preserved.

---

# 6. Strategy

## 6.1 Revised Strategy contract

v6 keeps the name `Strategy`, but changes its contract.

Old contract:

```text
Strategy is an uncertain reasoning declaration.
Premises support conclusion with some probability.
```

New contract:

```text
Strategy is a reviewed information-use step.
It has inputs, a conclusion/target, a method, generated helper assertions,
and a first-class reason.

Strategy carries no probability parameter.
```

A Strategy answers:

```text
What information is being used?
By what method?
For what target?
What helper claims are asserted when review permits?
Why is this step valid?
```

## 6.2 Strategy schema

The current Strategy class can be extended rather than replaced.

```python
class Strategy:
    strategy_id: str | None = None
    scope: Literal["local"]

    type: StrategyType

    premises: list[ClaimID]
    conclusion: ClaimID | None = None
    background: list[KnowledgeID] | None = None

    method: StrategyMethod | None = None  # v6: machine-readable lowering payload

    reason: str                         # v6: first-class, not metadata
    assertions: list[ClaimID] = []        # v6: generated helper claims to assert

    steps: list[Step] | None = None
    metadata: dict[str, Any] | None = None
```

`reason` is required for reviewable v6 Strategies.

`assertions` is explicit. It replaces the implicit old assumption that a generated “warrant helper” and its prior determine support strength.

`method` is a first-class, machine-readable payload. It must not be hidden in `metadata`, because review, hashing, validation, and BP lowering must all see the same object.

```python
StrategyMethod = (
    DeductionMethod
    | ModuleUseMethod
    | ComputeMethod
    | OpaqueConditionalMethod
)

class ModuleUseMethod:
    module_ref: str
    input_bindings: dict[str, KnowledgeID]
    output_bindings: dict[str, ValueRef]
    premise_bindings: dict[str, ClaimID] = {}

ValueRef = KnowledgeID | ArtifactRef | ScoreID  # ScoreID references a LikelihoodScoreRecord
```

`method` must participate in both the Strategy structure hash and the Warrant `subject_hash`.

## 6.3 FormalStrategy remains useful

`FormalStrategy` should remain the canonical way to attach deterministic Operator expansion to a Strategy.

```python
class FormalStrategy(Strategy):
    formal_expr: FormalExpr
```

`FormalExpr` remains:

```python
class FormalExpr:
    operators: list[Operator]
```

v6 interpretation:

```text
FormalExpr creates helper Claims via deterministic Operators.
Strategy.assertions lists which of those helper Claims are asserted when review permits.
```

## 6.4 Strategy types

The v6 core should collapse Strategy types into a small set of lowering methods:

```python
class StrategyType(StrEnum):
    DEDUCTION = "deduction"
    LIKELIHOOD = "likelihood"
    COMPUTE = "compute"
    OPAQUE_CONDITIONAL = "opaque_conditional"  # legacy / escape hatch
```

Legacy or authoring-only taxonomy should move to metadata:

```text
support
prediction
observation
citation
explanation
abduction
induction
analogy
compare
```

Recommended metadata:

```python
metadata={
    "surface_construct": "supported_by",
    "pattern": "citation" | "derivation" | "prediction" | "observation" | ...,
}
```

## 6.5 Why `deduction` is the canonical name

In v6, ordinary “support” is only valid after all defeasibility has been turned into explicit premises.

Thus canonical IR support is:

```text
AllTrue(premises) => conclusion
```

This is deduction in the Gaia IR sense:

```text
If the listed premises are true, the conclusion/helper assertion is licensed.
```

This does **not** mean the premises are certain. The premises may be probabilistic Claims. It only means the Strategy itself is solid under those premises.

---

# 7. Strategy.assertions and the old warrant helper

## 7.1 Mapping to the current warrant helper

Current Gaia formalization already generates implication helper Claims for support/deduction-like strategies, for example:

```text
G = AllTrue(A, B)
S = Implies(G, C)
```

The old design often called `S` a warrant helper and attached a prior to it.

v6 keeps `S`, but changes its meaning:

```text
S is an assertion helper.
It is generated by Operator.
It is listed in Strategy.assertions.
It carries no warrant prior.
```

So:

```python
Strategy.assertions = [S]
```

means:

```text
When this Strategy is accepted by review policy, assert S.
```

## 7.2 Why keep explicit assertions?

Explicit `assertions` are useful because they answer:

```text
Which generated helper Claims does this Strategy license?
```

They also make lowering and review deterministic.

Without `assertions`, lowering would need to guess which helper in `FormalExpr` is the intended assertion. That is fragile for relation, compare, compute, and future multi-step strategies.

---

# 8. Deduction Strategy

## 8.1 Basic deduction

For a user-level support step:

```text
A, B, rule_applies support C
```

canonical formalization creates:

```text
G = AllTrue(A, B, rule_applies)
S = Implies(G, C)
```

IR sketch:

```python
FormalStrategy(
    type="deduction",
    premises=[A, B, rule_applies],
    conclusion=C,
    reason="Given A, B, and the applicable rule, C follows.",
    assertions=[S],
    formal_expr=FormalExpr(operators=[
        Operator("conjunction", [A, B, rule_applies], conclusion=G),
        Operator("implication", [G, C], conclusion=S),
    ]),
)
```

Review policy decides whether `S` is asserted.

## 8.2 Gated relation via deduction

A gated relation such as:

```text
Given mapping_valid and units_consistent, A and B are equivalent.
```

should canonicalize to:

```text
G = AllTrue(mapping_valid, units_consistent)
R = Equivalent(A, B)
S = Implies(G, R)
```

The Strategy asserts `S`, not `R`.

This preserves gated relation semantics:

```text
If the gate premises are likely true, the relation has force.
If the gate premises are unlikely, the relation contributes little.
```

No sampling or thresholding is required. BP marginalizes over the gate Claim(s).

## 8.3 Empty premises

A deduction Strategy with empty premises is an unconditional assertion.

This should be allowed only for:

- definitions
- axioms
- compiler-generated internals
- reviewed package-level declarations

Recommended lint:

```text
Strict mode: error on author-facing deduction with empty premises unless marked as definition/axiom/internal/reviewed_declaration.
Draft mode: warn on author-facing deduction with empty premises unless marked as definition/axiom/internal/reviewed_declaration.
```

---

# 9. Likelihood Strategy

## 9.1 Purpose

`Strategy(type="likelihood")` represents Jaynes/Bayes-style evidence update:

```text
Given premises, apply a likelihood score to target Claim(s).
```

It is not deduction.

AB tests, Mendel ratios, measurement models, Bayes factors, and model comparisons belong here.

## 9.2 Standard library and auto-generated assumptions

At the Lang level, Gaia v6 provides a standard library of parameterized Claim classes for common statistical assumptions:

```python
RandomAssignment(experiment: Setting)
ConsistentLogging(experiment: Setting)
NoEarlyStopping(experiment: Setting)
FormulaCorrect(formula_name: str)
ImplementationCorrect(formula_name: str)
```

Standard helpers like `ab_test(counts, target)` auto-generate these assumption Claims with default priors, so users don't manually declare them unless overriding.

Auto-generated assumption Claims must still be materialized in the graph and surfaced in review/rendering. They should carry provenance such as:

```python
metadata={
    "generated_by": "gaia.std.likelihood.two_binomial_ab_test@v1",
    "role": "standard_assumption",
}
```

The helper may save authoring effort, but it must not hide priors or assumptions.

At IR level, these appear as ordinary `Knowledge(type="claim")` nodes with bound parameters. The IR doesn't distinguish "standard library Claims" from user Claims — they're all just parameterized Claims with priors.

## 9.3 Module-based schema extension

At the Lang layer, users normally call standard helpers such as `ab_test(...)` or `binomial_test(...)`. At the IR layer, those helpers lower to a module use, not to free-form strings.

A likelihood module defines the statistical model, required bindings, score shape, and BP effect:

```python
class LikelihoodModuleSpec:
    module_ref: str
    input_schema: dict[str, type]
    output_schema: dict[str, type]
    premise_schema: dict[str, type]

    target_role: str
    score_role: str
    score_value_path: str = "value"
    score_type: Literal["log_lr", "bayes_factor", "likelihood_table", "custom"]
    effect: Literal["add_log_odds", "multiply_odds", "likelihood_table_update"]
```

A likelihood Strategy instantiates such a module:

```python
class ModuleUseMethod:
    module_ref: str
    input_bindings: dict[str, KnowledgeID]
    output_bindings: dict[str, ValueRef]
    premise_bindings: dict[str, ClaimID] = {}
```

Example:

```python
Strategy(
    type="likelihood",
    premises=[
        ab_counts_true,
        randomization_valid,
        logging_valid,
        stopping_rule_accounted_for,
        ab_log_lr_score_correct,
    ],
    conclusion=B_better,
    reason=(
        "Given valid experiment assumptions and a correctly computed likelihood "
        "score, the AB-test likelihood ratio updates belief in whether B improves conversion."
    ),
    method=ModuleUseMethod(
        module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
        input_bindings={
            "counts": ab_counts_true,
            "target": B_better,
        },
        output_bindings={
            "score": ab_log_lr_score,
        },
        premise_bindings={
            "data_observed": ab_counts_true,
            "random_assignment": randomization_valid,
            "consistent_logging": logging_valid,
            "stopping_rule_accounted_for": stopping_rule_accounted_for,
            "score_correct": ab_log_lr_score_correct,
        },
    ),
    assertions=[],
)
```

The module spec, not the author, defines that this is a two-binomial AB-test likelihood, that the score is a log likelihood ratio, and that the BP effect is to add the score value to the target's log-odds.

## 9.4 Semantics

If the Strategy is included by review policy:

```text
look up method.module_ref in the module registry
validate input/output/premise bindings against the module spec
extract the score from method.output_bindings[spec.score_role]

if all Strategy.premises are true:
    apply the module-defined effect to the target
else:
    neutral
```

For binary target `H` and log-likelihood ratio `s`:

```text
if premises true:
    odds(H) *= exp(s)
else:
    no update
```

The Strategy itself has no probability. The score is model/data-derived evidence strength; the premises carry epistemic reliability.

The score value and the score correctness Claim are distinct:

```text
ab_log_lr_score          = value record or artifact containing log_lr = 1.73
ab_log_lr_score_correct  = Claim that the value was correctly computed/bound
```

The likelihood Strategy consumes both: the value through `method.output_bindings`, and the correctness gate through `premises`/`premise_bindings`.

---

# 10. Compute Strategy

## 10.1 Purpose

`Strategy(type="compute")` represents execution or validation of a deterministic computation that produces a parameterized Claim or artifact.

Example use cases:

- compute a p-value
- compute a likelihood ratio
- compute an observed rate
- compute a model prediction

## 10.2 Schema extension

```python
class ComputeMethod:
    function_ref: str
    input_bindings: dict[str, ClaimID]
    output: ValueRef
    output_binding: dict[str, str] | None = None
    code_hash: str | None = None
```

Example:

```python
Strategy(
    type="compute",
    premises=[ab_counts_true, two_binomial_formula_correct, implementation_correct],
    conclusion=ab_log_lr_score_correct,
    reason="Compute the AB-test log likelihood ratio from the observed counts.",
    method=ComputeMethod(
        function_ref="two_binomial_log_lr",
        input_bindings={"counts": ab_counts_true},
        output=ab_log_lr_score,
        output_binding={"log_lr": "return_value"},
    ),
)
```

The `output` is the produced value or artifact. The `conclusion` is a Claim about the correctness of that produced value. They should not be the same object.

```text
output:
  ab_log_lr_score, a value record containing log_lr = 1.73

conclusion:
  ab_log_lr_score_correct, a Claim that this value was correctly computed
```

A compute Strategy can itself be reviewed. If computation validity is uncertain, add explicit premise Claims such as:

```text
formula_correct
implementation_correct
input_binding_correct
constants_correct
```

Do not add a compute prior.

---

# 11. Opaque conditional Strategy

`Strategy(type="opaque_conditional")` is a legacy escape hatch for old-style CPT reasoning.

It may reference a parameterization record such as:

```python
OpaqueConditionalMethod(parameter_ref="cond_001")
```

It should not be the preferred v6 path.

Recommended lint:

```text
Opaque conditional strategy found.
Prefer explicit premise Claims + deduction, or likelihood strategy for statistical evidence.
```

---

# 12. ReviewManifest and Warrant

## 12.1 Warrant is not Knowledge

A v6 Warrant is not a Claim and does not enter BP.

It is a review block attached to a Strategy:

```python
class Warrant:
    id: str
    subject_strategy_id: StrategyID
    subject_hash: str

    status: Literal[
        "unreviewed",
        "accepted",
        "rejected",
        "needs_inputs",
        "superseded",
    ]

    blocking: bool = True
    review_question: str | None = None
    required_inputs: list[ClaimID] = []
    reviewer_notes: list[ReviewNote] = []
    resolution: str | None = None
```

## 12.2 Subject hash

A Warrant should be tied to the hash of the Strategy it reviewed.

Suggested hash payload:

```text
strategy.type
strategy.premises
strategy.conclusion
strategy.reason
strategy.assertions
strategy.method payload
strategy.formal_expr canonical hash
```

If the Strategy changes, the old Warrant should become `superseded` or invalid.

## 12.3 Review policy

Strict mode:

```text
accepted       -> include Strategy
unreviewed     -> exclude / error
needs_inputs   -> exclude
rejected        -> exclude
superseded      -> exclude
```

Draft mode:

```text
accepted       -> include
unreviewed     -> include with warning
needs_inputs   -> exclude or include with strong warning, configurable
rejected        -> exclude
superseded      -> exclude
```

Audit mode:

```text
No BP lowering required; produce review report.
```

## 12.4 Warrant vs assertion helper

v6 intentionally separates:

```text
assertion helper:
  generated Claim such as S = Implies(G, C)
  lives in Knowledge
  may be listed in Strategy.assertions

review Warrant:
  ReviewManifest object
  status controls whether Strategy may assert helpers
  no prior/posterior
```

The old “warrant prior” should be removed.

---

# 13. Parameterization

## 13.1 Claim priors

The only normal epistemic priors are Claim priors:

```python
ClaimPriorRecord(
    claim_id="randomization_valid",
    prior=0.98,
    rationale="Experiment platform used hash randomization and no SRM was detected.",
)
```

## 13.2 No warrant priors

v6 should not have:

```text
WARRANT_PRIORS
Strategy priors
support priors
relation priors
compute priors
```

If something is uncertain, it should become a premise Claim.

## 13.3 Likelihood scores

Likelihood Strategy needs score values. A score value is not itself a Strategy prior and should not be confused with the Claim that the score was correctly computed.

Scores may live in:

1. a value record, such as `LikelihoodScoreRecord(value=1.73)`;
2. an artifact referenced by `ArtifactRef`; or
3. a future value-carrying Knowledge object, provided its truth/correctness gate is modeled separately.

Recommended first-class parameterization:

```python
class LikelihoodScoreRecord:
    score_id: str
    module_ref: str
    target: ClaimID
    score_type: Literal["log_lr", "bayes_factor", "likelihood_table", "custom"]
    value: JsonValue | ArtifactRef
    query: str | dict | None = None
    rationale: str | None = None
```

This is model/data evidence strength. It is consumed by a module-based likelihood Strategy. The uncertainty that this score was computed from the correct inputs, formula, code, or binding is represented by ordinary premise Claims such as `ab_log_lr_score_correct`.

---

# 14. BP lowering contract

## 14.1 Claim variables

Every `Knowledge(type="claim")` becomes a Boolean random variable.

```text
X_C ∈ {false, true}
```

Claim priors come from parameterization or defaults.

## 14.2 Operators

Operators lower to deterministic constraints defining their helper conclusion.

```text
helper = f(variables)
```

Operator conclusions are not asserted true by default.

## 14.3 Deduction Strategy

For an included deduction Strategy:

```text
assert each helper in Strategy.assertions
```

Usually:

```text
G = AllTrue(premises)
S = Implies(G, conclusion)
assert S
```

Hard semantics:

```text
forbid S=false
```

Implementation may use an epsilon relaxation for numerical stability, but this is not an IR-level probability.

## 14.4 Likelihood Strategy

For an included likelihood Strategy:

```text
module_spec = registry[Strategy.method.module_ref]
score = resolve(Strategy.method.output_bindings[module_spec.score_role])
target = resolve(Strategy.method.input_bindings[module_spec.target_role])

if premises all true:
    apply module_spec.effect(score, target)
else:
    neutral
```

For `effect="add_log_odds"` and score type `log_lr`, this means:

```text
log_odds(target) += score.value
```

BP can implement this as a gated likelihood factor or equivalent lowering. This is a backend detail and does not introduce `Factor` to Gaia IR.

## 14.5 Compute Strategy

Compute Strategy either:

1. materializes output Claims/artifacts before BP, or
2. validates that output Claims correspond to inputs and function references.

Any uncertainty about formulas, code, constants, or bindings must be explicit in premises.

---

# 15. Migration from current IR

## 15.1 Keep

Keep:

- `Knowledge`
- `Operator`
- `Operator.conclusion`
- generated helper claims
- `Strategy`
- `FormalStrategy`
- `FormalExpr`
- `CompositeStrategy` as a grouping/view/legacy construct

## 15.2 Add

Add:

- `Knowledge(type="context")`
- `Parameter.value`
- `Strategy.method`
- `Strategy.reason`
- `Strategy.assertions`
- `Strategy(type="likelihood")`
- `Strategy(type="compute")`
- `ModuleUseMethod` and module specs for standard likelihood updates
- `ReviewManifest`
- `Warrant`
- likelihood score parameterization

## 15.3 Deprecate or reinterpret

Deprecate as core v6 semantics:

- `StrategyType.INFER`
- `StrategyType.NOISY_AND`
- `StrategyType.SUPPORT` as soft warrant support
- warrant prior
- Strategy prior
- relation helper auto-assert

Reinterpret:

```text
current generated implication warrant helper
  -> v6 assertion helper listed in Strategy.assertions

current Warrant-as-probability
  -> removed

human review warrant
  -> ReviewManifest.Warrant
```

## 15.4 Lowering changes

Required changes:

1. Do not propagate `metadata.prior` into support/deduction helper claims in v6 mode.
2. Do not auto-pin relation Operator conclusions to true.
3. Assert helper claims only if they appear in an included Strategy's `assertions`.
4. Gate inclusion by ReviewManifest in strict/reviewed modes.
5. Add likelihood strategy lowering.

---

# 16. Examples

## 16.1 Source report deduction

Domain:

```text
A paper reports X.
The extracted statement is correct.
The source is reliable for this claim.
Therefore X.
```

Claims:

```text
paper_reports_X
extraction_correct
source_reliable_for_X
X
```

Generated helpers:

```text
G = AllTrue(paper_reports_X, extraction_correct, source_reliable_for_X)
S = Implies(G, X)
```

Strategy:

```python
Strategy(
    type="deduction",
    premises=[paper_reports_X, extraction_correct, source_reliable_for_X],
    conclusion=X,
    reason="A correct extraction from a reliable source report establishes X.",
    assertions=[S],
)
```

## 16.2 Gated equivalence relation

Domain:

```text
Given ratio_mapping_valid, the claim '3:1 dominant:recessive ratio'
is equivalent to 'dominant phenotype probability is 0.75'.
```

Generated helpers:

```text
G = AllTrue(ratio_mapping_valid)
R = Equivalent(ratio_3_to_1, p_equals_075)
S = Implies(G, R)
```

Strategy asserts `S`.

This means the equivalence has force only to the extent that `ratio_mapping_valid` is credible.

## 16.3 AB test likelihood

Claims (instances of parameterized Claim classes):

```text
B_better                          — target hypothesis Claim
ab_counts_true                    — ABCounts(experiment=exp, ctrl_n=10000, ctrl_k=500, treat_n=10000, treat_k=550)
randomization_valid               — RandomAssignment(experiment=exp)
logging_valid                     — ConsistentLogging(experiment=exp)
stopping_rule_accounted_for       — NoEarlyStopping(experiment=exp)
ab_log_lr_score                   — LikelihoodScoreRecord(target=B_better, module_ref="gaia.std.likelihood.two_binomial_ab_test@v1", score_type="log_lr", value=1.73)
ab_log_lr_score_correct           — Claim that ab_log_lr_score was correctly computed and bound
formula_correct                   — FormulaCorrect(formula_name="two_binomial_log_lr")
implementation_correct            — ImplementationCorrect(formula_name="two_binomial_log_lr")
```

Note: `experiment=exp` means these Claims reference a `Setting` node via Knowledge parameter. At IR level, this is stored as a QID reference in the `Parameter.value` field.

Compute Strategy:

```python
Strategy(
    type="compute",
    premises=[ab_counts_true, formula_correct, implementation_correct],
    conclusion=ab_log_lr_score_correct,
    reason="Compute the two-binomial log likelihood ratio from AB counts.",
    method=ComputeMethod(
        function_ref="two_binomial_log_lr",
        input_bindings={"counts": ab_counts_true},
        output=ab_log_lr_score,
        output_binding={"value": "return_value"},
    ),
)
```

Likelihood Strategy:

```python
Strategy(
    type="likelihood",
    premises=[
        ab_counts_true,
        randomization_valid,
        logging_valid,
        stopping_rule_accounted_for,
        ab_log_lr_score_correct,
    ],
    conclusion=B_better,
    reason="Apply the computed AB likelihood score to B_better under valid experiment assumptions.",
    method=ModuleUseMethod(
        module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
        input_bindings={
            "counts": ab_counts_true,
            "target": B_better,
        },
        output_bindings={
            "score": ab_log_lr_score,
        },
        premise_bindings={
            "data_observed": ab_counts_true,
            "random_assignment": randomization_valid,
            "consistent_logging": logging_valid,
            "stopping_rule_accounted_for": stopping_rule_accounted_for,
            "score_correct": ab_log_lr_score_correct,
        },
    ),
)
```

In practice, the Lang layer provides `ab_test(counts, target)` helpers that auto-generate these standard assumption Claims, so users don't manually declare them unless overriding defaults.

---

# 17. Open questions

1. Should `Strategy.assertions` be required for every `Strategy(type="deduction")`?
   - Recommended: yes, after formalization.

2. Should `StrategyType.SUPPORT` be kept as a legacy alias?
   - Recommended: yes for migration, but canonical v6 should emit `deduction`.

3. Should likelihood scores be stored primarily as Claims or parameterization records?
   - Recommended: support both; prefer parameterized Claim when the score itself should be inspectable or reusable.

4. Should `CompositeStrategy` remain core or become a view/grouping object?
   - Recommended: keep for compatibility, but do not rely on it for core semantics.

5. Should review status live in the graph file or separate manifest?
   - Recommended: separate `ReviewManifest`, distributed with package.

---

# 18. Final contract

Gaia IR v6 should be summarized as:

```text
Knowledge:
  What claims, settings, questions, and raw contexts exist?

Operator:
  What deterministic helper expressions are defined?

Strategy:
  Which reviewed information-use steps assert helpers, apply likelihoods,
  or validate computations?

ReviewManifest/Warrant:
  Which Strategies are accepted, rejected, unreviewed, or need more inputs?
```

The important conceptual correction is:

```text
Strategy is not a probability edge.
Warrant is not a probability variable.
Generated helper claims are not automatically true.
```

Instead:

```text
Claim carries uncertainty.
Strategy carries solid reasoning structure.
Likelihood carries statistical evidence strength.
Warrant carries review status.
```
