# Gaia Lang v6 Proposal: Authoring DSL over Strategy/Warrant-Aligned Gaia IR

> Status: design proposal  
> Date: 2026-04-20  
> Scope: Gaia Lang v6 surface API and lowering to Gaia IR v6  
> Companion: `gaia-ir-v6-strategy-warrant-redesign.md`  
> Non-goal: final high-level relation surface design is deferred; this document only specifies the IR-compatible lowering pattern when needed.

---

## 0. Executive summary

Gaia Lang v6 should keep a small, intuitive user-facing surface:

```text
Context
Setting
Claim
Question
```

and a small set of authoring operations:

```text
Claim.supported_by(...)
Claim.derived_from(...)
likelihood_from(...)
compute(...)
```

The core design principles are:

1. **`Claim` is the only probabilistic authoring object.**
2. **`supported_by` is a general surface API, but lowers to canonical `Strategy(type="deduction")` when solid.**
3. **`pattern` is authoring/review metadata, not an IR strategy type.**
4. **Statistical evidence uses `Strategy(type="likelihood")`, not probabilistic support.**
5. **Computation uses `Strategy(type="compute")`.**
6. **Warrants are review blocks generated into `ReviewManifest`; users normally do not instantiate Warrant objects directly.**
7. **No `prior` on supported_by / Strategy / Warrant.**
8. **Unformalized raw text is stored in `Context`.**

---

# 1. User-facing objects

## 1.1 Context

`Context` stores raw text or artifact excerpts that have not yet been formalized into Claims.

```python
ctx = Context("""
Experiment exp_123 ran from March 1 to March 14.
Control A had 10,000 users and 500 conversions.
Treatment B had 10,000 users and 550 conversions.
The assignment was configured as 50/50.
""")
```

Lowering:

```text
Knowledge(type="context")
```

Rules:

- `Context` does not enter BP.
- `Context` cannot be a `Strategy.premise`.
- Claims may reference `Context` via grounding/provenance/background.

## 1.2 Setting

`Setting` stores formalized background context, convention, scope, or units.

```python
ratio_setting = Setting(
    "Ratios are expressed as dominant:recessive phenotype counts."
)
```

Lowering:

```text
Knowledge(type="setting")
```

Rules:

- `Setting` does not carry prior/posterior.
- `Setting` may appear in Strategy background.
- If a background proposition is uncertain, it should be a `Claim`, not a `Setting`.

## 1.3 Claim

`Claim` is the only user-facing object with prior/posterior belief.

```python
b_better = Claim(
    "Variant B has a higher true conversion rate than variant A.",
    prior=0.5,
)
```

Lowering:

```text
Knowledge(type="claim")
```

Rules:

- All epistemic uncertainty should be represented as Claims.
- If a reasoning step is not solid, add more input Claims.
- Do not put uncertainty on the edge.

## 1.4 Question

`Question` is an inquiry lens.

```python
q = Question(
    "Should variant B be shipped?",
    targets=[ship_b],
)
```

Lowering:

```text
Knowledge(type="question")
```

Rules:

- `Question` does not enter BP.
- `Question` organizes inquiry, rendering, and sensitivity analysis.

---

# 2. Parameterized Claims

Gaia Lang v6 should support parameterized Claim classes.

Parameters come in two kinds:

- **Value parameters** (`int`, `float`, `str`, `Enum`): use `{param_name}` template substitution in the docstring.
- **Knowledge parameters** (`Setting`, `Claim`, or subclasses): use `[@param_name]` reference syntax in the docstring. The compiler resolves these to the referenced node's QID at compile time.

Example:

```python
class ABCounts(Claim):
    """[@experiment] recorded {ctrl_k}/{ctrl_n} control and {treat_k}/{treat_n} treatment conversions."""
    experiment: Setting    # Knowledge parameter — rendered via [@experiment]
    ctrl_n: int            # value parameter — rendered via {ctrl_n}
    ctrl_k: int
    treat_n: int
    treat_k: int
```

A ground instance:

```python
exp = Setting("AB test exp_123: 50/50 hash-based randomization, March 1-14.")

ab_counts = ABCounts(
    experiment=exp,
    ctrl_n=10_000,
    ctrl_k=500,
    treat_n=10_000,
    treat_k=550,
    prior=0.99,
    grounding=Grounding(
        kind="source_fact",
        reason="Extracted from experiment dashboard excerpt.",
        source_refs=[ctx],
    ),
)
# ab_counts.content_template = "[@experiment] recorded {ctrl_k}/{ctrl_n} control and {treat_k}/{treat_n} treatment conversions."
# ab_counts.rendered_content = "[@exp_123] recorded 500/10000 control and 550/10000 treatment conversions."
```

Template rendering order:

1. Compiler stores the docstring as canonical `content_template`.
2. Compiler records Knowledge-typed parameter references in `Parameter.value` as QIDs.
3. Compiler applies `str.format()` and reference rendering only to produce derived `rendered_content`.
4. `rendered_content` is display-only and does not participate in canonical hashing.

Lowering:

```text
Knowledge(type="claim")
Parameter.value stores bound values.
Knowledge-typed parameters store the referenced node's QID.
Stable hash uses type + content_template + sorted Parameter(name, type, value).
```

The bound parameter values must be preserved in IR and included in stable hashes.

---

# 3. Grounding

Grounding explains why a root Claim can have a prior.

```python
randomization_valid = Claim(
    "Users were randomly assigned between A and B.",
    prior=0.98,
    grounding=Grounding(
        kind="assumption",
        reason="The experiment platform was configured for hash-based 50/50 randomization and no SRM was detected.",
    ),
)
```

Grounding is not support. It is not a Strategy. It does not enter BP directly.

Recommended grounding kinds:

```text
assumption
source_fact
definition
imported
judgment
open
```

Strict lint:

```text
A root Claim with a non-default prior should have grounding or incoming Strategy support.
```

---

# 4. supported_by: general surface API

## 4.1 Purpose

`Claim.supported_by(...)` remains the general user-facing API.

```python
claim.supported_by(
    inputs=[...],
    pattern="citation" | "observation" | "prediction" | "derivation" | "explanation" | ...,
    reason="...",
    context=[...],
    label="...",
)
```

Important v6 rule:

```text
supported_by has no prior.
```

No:

```python
claim.supported_by(..., prior=0.93)  # removed in v6 core
```

## 4.2 Pattern is metadata

`pattern` does not choose a probability model.

It is used for:

- review question generation
- rendering
- inquiry filtering
- authoring diagnostics
- provenance grouping

It should lower into metadata:

```python
metadata={
    "surface_construct": "supported_by",
    "pattern": "citation",
}
```

## 4.3 Lowering to IR

When the listed inputs make the conclusion solid, `supported_by` lowers to:

```text
Strategy(type="deduction")
```

Example:

```python
x.supported_by(
    inputs=[paper_reports_x, extraction_correct, source_reliable_for_x],
    pattern="citation",
    reason="A correct extraction from a reliable source report establishes X.",
)
```

Canonical helper generation:

```text
G = AllTrue(paper_reports_x, extraction_correct, source_reliable_for_x)
S = Implies(G, x)
```

IR:

```python
FormalStrategy(
    type="deduction",
    premises=[paper_reports_x, extraction_correct, source_reliable_for_x],
    conclusion=x,
    reason="A correct extraction from a reliable source report establishes X.",
    assertions=[S],
    metadata={
        "surface_construct": "supported_by",
        "pattern": "citation",
    },
    formal_expr=FormalExpr(operators=[
        Operator("conjunction", [paper_reports_x, extraction_correct, source_reliable_for_x], conclusion=G),
        Operator("implication", [G, x], conclusion=S),
    ]),
)
```

The accepted Strategy asserts `S`, not an edge probability.

## 4.4 What if support is not solid?

If the step is not solid under the listed inputs, do not lower edge probability.

Instead:

1. Add explicit input Claims.
2. Change the method to likelihood if the evidence is statistical.
3. Mark the generated Warrant as `needs_inputs` or `rejected`.

Example missing inputs:

```python
no_known_retraction = Claim(
    "There is no known retraction or failed replication that invalidates this report.",
    prior=0.9,
)
```

Then add it to `inputs`.

---

# 5. derived_from

`derived_from(...)` is a narrower convenience method for derivational support.

```python
claim.derived_from(
    inputs=[law, instance_conditions],
    reason="Universal instantiation of the law under the listed conditions.",
)
```

Equivalent surface form:

```python
claim.supported_by(
    inputs=[law, instance_conditions],
    pattern="derivation",
    reason="Universal instantiation of the law under the listed conditions.",
)
```

Lowering:

```text
Strategy(type="deduction")
metadata.pattern = "derivation"
```

No prior.

---

# 6. Statistical evidence: likelihood_from

## 6.1 Why a separate API is needed

Statistical data usually does not deduce a hypothesis.

AB counts do not imply:

```text
B is truly better.
```

They provide a likelihood score:

```text
odds(H) *= LR
```

Therefore statistical evidence should not use ordinary `supported_by` unless the conclusion is merely a threshold/criterion Claim such as “p-value exceeds alpha”.

## 6.2 Standard parameterized Claim library

To avoid requiring users to manually declare standard assumptions for every statistical test, Gaia Lang v6 provides a standard library of parameterized Claim classes.

### Standard assumption Claims

```python
class RandomAssignment(Claim):
    “””Users in [@experiment] were randomly assigned between groups.”””
    experiment: Setting

class ConsistentLogging(Claim):
    “””Conversions in [@experiment] were logged consistently across groups.”””
    experiment: Setting

class NoEarlyStopping(Claim):
    “””[@experiment] analysis accounts for the stopping rule.”””
    experiment: Setting

class FormulaCorrect(Claim):
    “””The {formula_name} formula is mathematically correct for this likelihood calculation.”””
    formula_name: str

class ImplementationCorrect(Claim):
    “””The reviewed code for {formula_name} implements the formula without relevant bugs.”””
    formula_name: str
```

### Standard data Claims and score values

```python
class ABCounts(Claim):
    “””[@experiment] recorded {ctrl_k}/{ctrl_n} control and {treat_k}/{treat_n} treatment conversions.”””
    experiment: Setting
    ctrl_n: int
    ctrl_k: int
    treat_n: int
    treat_k: int

class LikelihoodScore:
    “””Value object for a module-produced likelihood score.”””
    target: Claim
    module_ref: str
    score_type: str
    query: str
    value: float
```

`LikelihoodScore` is not the same thing as the Claim that the score was correctly computed. The score is the value consumed by likelihood lowering; score correctness is an ordinary Claim used as a premise gate.

## 6.3 Standard likelihood helpers

The standard library provides one-line helpers that automatically instantiate standard assumptions. These Claims are generated for convenience, but they are still visible graph objects with priors, grounding/provenance, and review surface.

```python
def ab_test(counts: ABCounts, target: Claim) -> Strategy:
    “””Standard AB test likelihood with built-in assumptions.
    
    Automatically creates:
    - RandomAssignment (prior=0.98)
    - ConsistentLogging (prior=0.97)
    - NoEarlyStopping (prior=0.80)
    - FormulaCorrect (prior=0.98)
    - ImplementationCorrect (prior=0.97)
    - LikelihoodScore computation via two_binomial_log_lr
    
    Returns a likelihood_from Strategy with all assumptions gated.
    “””
    exp = counts.experiment
    
    # Standard assumptions — auto-generated, user doesn't declare
    rand = RandomAssignment(experiment=exp, prior=0.98)
    log  = ConsistentLogging(experiment=exp, prior=0.97)
    stop = NoEarlyStopping(experiment=exp, prior=0.80)
    
    # Computation assumptions
    formula = FormulaCorrect(formula_name=”two_binomial_log_lr”, prior=0.98)
    impl = ImplementationCorrect(formula_name=”two_binomial_log_lr”, prior=0.97)
    
    # Compute score
    score_result = compute(
        fn=two_binomial_log_lr,
        inputs={"counts": counts},
        output=LikelihoodScore(
            target=target,
            module_ref=”gaia.std.likelihood.two_binomial_ab_test@v1”,
            score_type=”log_lr”,
            query=”theta_B > theta_A”,
            value=0.0,  # placeholder, computed by fn
        ),
        assumptions=[formula, impl],
        reason=”Compute two-binomial log likelihood ratio.”,
    )
    
    # Likelihood Strategy
    return likelihood_from(
        target=target,
        data=[counts],
        assumptions=[rand, log, stop],
        score=score_result.output,
        score_correctness=score_result.correctness,
        module_ref=”gaia.std.likelihood.two_binomial_ab_test@v1”,
        query=”theta_B > theta_A”,
        reason=”AB test likelihood under standard experiment assumptions.”,
    )
```

### User-facing usage

With the standard library, users write:

```python
exp = Setting(“AB test exp_123: 50/50 hash-based randomization, March 1-14.”)

counts = ABCounts(
    experiment=exp,
    ctrl_n=10_000, ctrl_k=500,
    treat_n=10_000, treat_k=550,
    prior=0.99,
    grounding=Grounding(kind=”source_fact”, reason=”Extracted from dashboard.”),
)

b_better = Claim(
    “Variant B has a higher true conversion rate than A.”,
    prior=0.5,
)

ab_test(counts, b_better)
```

That's it. No manual assumption declaration unless the user wants to override defaults.

### Overriding standard assumptions

If a user needs non-standard priors or additional assumptions:

```python
# Override stopping rule prior
stop_custom = NoEarlyStopping(experiment=exp, prior=0.60)

# Manual likelihood_from with custom assumptions.
# `score_result` may come from compute(...) or a reviewed imported score.
likelihood_from(
    target=b_better,
    data=[counts],
    assumptions=[
        RandomAssignment(experiment=exp, prior=0.98),
        ConsistentLogging(experiment=exp, prior=0.97),
        stop_custom,  # custom prior
        novelty_effect_accounted,  # additional assumption
    ],
    score=score_result.output,
    score_correctness=score_result.correctness,
    module_ref=”gaia.std.likelihood.two_binomial_ab_test@v1”,
    query=”theta_B > theta_A”,
    reason=”AB test with custom stopping rule confidence and novelty effect check.”,
)
```

## 6.4 Low-level likelihood_from API

For non-standard tests or when standard helpers don't apply:

```python
likelihood_from(
    target=claim,
    data=[data_claims],
    assumptions=[assumption_claims],
    score=likelihood_score_value,
    score_correctness=score_correctness_claim,
    module_ref=”...”,
    query=”...”,
    reason=”...”,
)
```

Lowering:

```text
Strategy(type=”likelihood”)
```

with premises:

```text
data claims
assumption claims
score_correctness claim
```

and method payload:

```text
module_ref
input_bindings
output_bindings
premise_bindings
query
```

## 6.5 No likelihood Strategy prior

Do not write:

```python
likelihood_from(..., prior=0.8)
```

If model applicability is uncertain, add an assumption Claim:

```python
model_applicable = Claim(
    “The two-binomial model is appropriate for this experiment.”,
    prior=0.85,
)
```

and include it in assumptions.

---

# 7. compute

## 7.1 Purpose

`compute(...)` is used when values or parameterized Claims are produced by deterministic code/formulas.

It returns a structured result, not a bare Strategy and not just the output value:

```python
class ComputeResult(Generic[T]):
    output: T
    correctness: Claim
    strategy: Strategy
```

This makes the three roles explicit:

```text
output:
  the produced value or artifact

correctness:
  the Claim that the output was correctly computed and bound

strategy:
  the reviewable compute Strategy that produced/validates the output
```

Example:

```python
score_result = compute(
    fn=two_binomial_log_lr,
    inputs={"counts": counts},
    output=LikelihoodScore(
        target=b_better,
        module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
        score_type="log_lr",
        query="theta_B > theta_A",
        value=0.0,
    ),
    assumptions=[
        FormulaCorrect(formula_name="two_binomial_log_lr", prior=0.98),
        ImplementationCorrect(formula_name="two_binomial_log_lr", prior=0.97),
    ],
    reason="Compute the AB-test log likelihood ratio from observed counts.",
)
```

Lowering:

```text
Strategy(type="compute")
```

The lowered compute Strategy uses `score_result.output` as `method.output` and `score_result.correctness` as `conclusion`.

## 7.2 Computation uncertainty

Do not put probability on the compute Strategy.

If something is uncertain, use Claims:

```python
formula_correct = FormulaCorrect(
    formula_name="two_binomial_log_lr",
    prior=0.98,
)

implementation_correct = ImplementationCorrect(
    formula_name="two_binomial_log_lr",
    prior=0.97,
)
```

Then include them in the compute Strategy premises.

---

# 8. ReviewManifest and generated Warrants

## 8.1 User-facing behavior

Users normally do not write Warrant objects directly.

When Gaia Lang emits a Strategy, tooling can generate a Warrant in the `ReviewManifest`.

Example generated review block:

```python
Warrant(
    subject_strategy_id="...",
    subject_hash="...",
    status="unreviewed",
    review_question="Are the listed premises sufficient for this deduction?",
)
```

## 8.2 Review statuses

```text
unreviewed
accepted
rejected
needs_inputs
superseded
```

If reviewer says the Strategy is not solid:

```text
status = "needs_inputs"
required_inputs = [...]
```

The fix is to add explicit Claims and regenerate the Strategy hash.

## 8.3 Warrant has no probability

No:

```python
Warrant(prior=0.7)
```

No:

```python
WARRANT_PRIORS = {...}
```

Warrant is procedural review state, not epistemic uncertainty.

---

# 9. Context extraction workflow

A recommended formalization workflow:

1. Add raw text as `Context`.
2. Extract Claims from Context.
3. Ground extracted Claims with `source_fact` grounding pointing back to Context.
4. Add deduction / likelihood / compute Strategies.
5. Generate ReviewManifest.
6. Review generated Warrants.
7. Add missing premise Claims where needed.

Example:

```python
ctx = Context("""
Control A had 10,000 users and 500 conversions.
Treatment B had 10,000 users and 550 conversions.
""")

exp = Setting("AB test exp_123: 50/50 hash-based randomization, March 1-14.")

ab_counts = ABCounts(
    experiment=exp,
    ctrl_n=10_000,
    ctrl_k=500,
    treat_n=10_000,
    treat_k=550,
    prior=0.99,
    grounding=Grounding(
        kind="source_fact",
        reason="Extracted from dashboard excerpt.",
        source_refs=[ctx],
    ),
)
```

---

# 10. Pattern taxonomy

`pattern` values are authoring/review labels.

Suggested initial set:

```text
derivation
citation
observation
prediction
explanation
definition
measurement
computation
model_assumption
source_extraction
```

They do not directly determine IR StrategyType.

Examples:

```text
supported_by(..., pattern="citation")
  -> usually Strategy(type="deduction")

supported_by(..., pattern="derivation")
  -> Strategy(type="deduction")

likelihood_from(...)
  -> Strategy(type="likelihood")

compute(...)
  -> Strategy(type="compute")
```

---

# 11. Relation surface deferred

This document intentionally does not finalize high-level relation APIs.

However, if a relation surface such as:

```python
equivalent(A, B, inputs=[mapping_valid], reason="...")
```

is later added, the recommended canonical lowering is:

```text
G = AllTrue(mapping_valid)
R = Equivalent(A, B)
S = Implies(G, R)
```

and:

```text
Strategy(type="deduction", assertions=[S])
```

That preserves gated relation semantics while using existing Operator helper mechanics.

---

# 12. End-to-end examples

## 12.1 Citation-like support

```python
paper_reports_x = Claim(
    "Paper P reports that material M is superconducting below 90K.",
    prior=0.98,
    grounding=Grounding(kind="source_fact", reason="Extracted from Paper P."),
)

extraction_correct = Claim(
    "The superconductivity claim was correctly extracted from Paper P.",
    prior=0.95,
)

source_reliable = Claim(
    "Paper P is reliable for this measurement claim.",
    prior=0.85,
)

x = Claim(
    "Material M is superconducting below 90K.",
    prior=0.5,
)

x.supported_by(
    inputs=[paper_reports_x, extraction_correct, source_reliable],
    pattern="citation",
    reason="A correct extraction from a reliable source report establishes the superconductivity claim.",
)
```

Lowering:

```text
Strategy(type="deduction")
G = AllTrue(inputs)
S = Implies(G, x)
assertions=[S]
```

## 12.2 Mendel ratio as likelihood

```python
from gaia.lang.likelihood import binomial_test, BinomialCounts

exp = Setting("Mendel's pea plant crossing experiment, F2 generation.")

p_is_075 = Claim(
    "The true dominant phenotype probability is 0.75 under the Mendelian model.",
    prior=0.5,
)

mendel_counts = BinomialCounts(
    experiment=exp,
    successes=295,
    trials=395,
    prior=0.98,
    grounding=Grounding(kind="source_fact", reason="Extracted from the experimental report."),
)

binomial_test(mendel_counts, target=p_is_075, p_hypothesis=0.75)
```

For manual control, the full low-level form is still available:

```python
binomial_model_valid = Claim(
    "The binomial sampling model is appropriate for this phenotype count experiment.",
    prior=0.85,
)

formula = FormulaCorrect(formula_name="binomial_log_lr", prior=0.98)
impl = ImplementationCorrect(formula_name="binomial_log_lr", prior=0.97)

score_result = compute(
    fn=binomial_log_lr_for_p,
    inputs={"counts": mendel_counts},
    output=LikelihoodScore(
        target=p_is_075,
        module_ref="gaia.std.likelihood.binomial_test@v1",
        score_type="log_lr",
        query="p=0.75",
        value=0.0,
    ),
    assumptions=[formula, impl],
    reason="Compute the likelihood score of the observed counts under p=0.75.",
)

likelihood_from(
    target=p_is_075,
    data=[mendel_counts],
    assumptions=[binomial_model_valid],
    score=score_result.output,
    score_correctness=score_result.correctness,
    module_ref="gaia.std.likelihood.binomial_test@v1",
    query="p=0.75",
    reason="Given the binomial sampling model, the observed counts update belief in p=0.75.",
)
```

## 12.3 AB test

Using the standard library:

```python
from gaia.lang.likelihood import ab_test, ABCounts

exp = Setting("AB test exp_123: 50/50 hash-based randomization, March 1-14.")

b_better = Claim(
    "Variant B has a higher true conversion rate than variant A.",
    prior=0.5,
)

counts = ABCounts(
    experiment=exp,
    ctrl_n=10_000,
    ctrl_k=500,
    treat_n=10_000,
    treat_k=550,
    prior=0.99,
    grounding=Grounding(kind="source_fact", reason="Extracted from experiment dashboard."),
)

ab_test(counts, b_better)
```

For manual control with custom assumptions:

```python
rand = RandomAssignment(experiment=exp, prior=0.98)
log = ConsistentLogging(experiment=exp, prior=0.97)
stop = NoEarlyStopping(experiment=exp, prior=0.60)  # custom: low confidence in stopping rule
novelty = Claim("The novelty effect has been accounted for.", prior=0.75)

formula = FormulaCorrect(formula_name="two_binomial_log_lr", prior=0.98)
impl = ImplementationCorrect(formula_name="two_binomial_log_lr", prior=0.97)

score_result = compute(
    fn=two_binomial_log_lr,
    inputs={"counts": counts},
    output=LikelihoodScore(
        target=b_better,
        module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
        score_type="log_lr",
        query="theta_B > theta_A",
        value=0.0,
    ),
    assumptions=[formula, impl],
    reason="Compute the two-binomial log likelihood ratio.",
)

likelihood_from(
    target=b_better,
    data=[counts],
    assumptions=[rand, log, stop, novelty],
    score=score_result.output,
    score_correctness=score_result.correctness,
    module_ref="gaia.std.likelihood.two_binomial_ab_test@v1",
    query="theta_B > theta_A",
    reason="AB test with custom stopping rule confidence and novelty effect check.",
)
```

---

# 13. Lint rules

Recommended v6 lint rules:

1. `supported_by(...)` must not have `prior`.
2. In strict mode, `supported_by(...)` with empty inputs should error unless marked as definition/axiom/internal/reviewed_declaration.
3. Root Claims with non-default prior should have grounding.
4. Statistical comparisons should prefer `likelihood_from(...)` over `supported_by(...)`.
5. Opaque conditional strategies should warn.
6. Every Strategy should have a first-class `reason`.
7. Every generated Strategy should have a Warrant in ReviewManifest.
8. In strict mode, unreviewed Strategies should not be lowered.
9. `Context` cannot be a Strategy premise.
10. If a reviewer marks a Warrant as `needs_inputs`, the requested inputs should become Claims, not edge probabilities.

---

# 14. Final language contract

Gaia Lang v6 should feel like this:

```text
Use Context for raw material.
Use Claim for anything uncertain.
Use supported_by / derived_from only when the listed inputs make the conclusion solid.
Use likelihood_from for statistical evidence.
Use compute for deterministic calculations.
Let ReviewManifest/Warrant review Strategies, not estimate probabilities.
```

The crucial authoring discipline is:

```text
Do not make the edge probabilistic.
Make the missing assumption explicit.
```
