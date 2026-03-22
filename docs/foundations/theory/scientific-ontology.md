# Scientific Ontology

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 |
| 日期 | 2026-03-22 |
| 状态 | **Target design — foundation baseline** |
| 关联文档 | [theoretical-foundation.md](theoretical-foundation.md) — Gaia 的认识论总纲, [inference-theory.md](inference-theory.md) — operator / BP contract, [../language/gaia-language-spec.md](../language/gaia-language-spec.md) — 作者可写的语言 surface, [../graph-ir.md](../graph-ir.md) — 结构化 IR, [../review/service-boundaries.md](../review/service-boundaries.md) — ReviewService / CurationService 边界 |

---

## 1. Purpose

This document defines the scientific object model that later Gaia foundation docs should reuse.

Its job is to answer four questions before language and BP details diverge:

1. What kinds of scientific objects exist in Gaia?
2. Which objects are truth-apt and may participate in BP?
3. Which operations are deterministic entailments versus probabilistic support?
4. Which distinctions belong in Gaia Language, and which belong only in review / curation?

This document is normative for ontology and modeling boundaries.

It does **not** define:

- exact Gaia Language syntax
- Graph IR field layout
- factor potential formulas
- server API contracts

## 2. First Principle

Gaia does not formalize abstract logic in isolation. It formalizes a system of **scientific assertions with evidence provenance, applicability conditions, uncertainty, and revisability**.

Therefore the core boundary is:

- **Only closed, truth-apt scientific assertions may participate in BP**
- **Open templates, discovery workflows, and research tasks do not participate in BP directly**

## 3. Object Classes

### 3.1 `Template`

A `Template` is an open proposition schema or predicate-like pattern.

Examples:

- `falls_at_rate(x, medium)`
- `critical_temperature(material, pressure)`
- `P(x) -> Q(x)`

`Template` is analogous to a predicate or open formula. It is **not** a closed proposition and does not directly carry a truth belief.

`Template` does **not** enter BP.

### 3.2 `ClosedClaim`

A `ClosedClaim` is a closed, truth-apt scientific assertion.

Examples:

- "The feather and hammer fall at the same rate in lunar vacuum."
- "This sample exhibits superconductivity below 90 K."

`ClosedClaim` is the default BP-bearing assertion class.

### 3.3 `ObservationClaim`

An `ObservationClaim` is a `ClosedClaim` whose primary authority comes from observation rather than derivation.

Examples:

- reported experimental outcome
- measured astronomical signal
- instrument reading interpreted as a proposition

`ObservationClaim` is still a claim, not a separate logical species. Its distinction matters for review, provenance, and default priors.

### 3.4 `MeasurementClaim`

A `MeasurementClaim` is an observation-centered claim tied to quantity, unit, calibration, and uncertainty structure.

Examples:

- "The transition temperature is 92 +/- 1 K."
- "The measured redshift is z = 0.5."

`MeasurementClaim` is a specialized `ObservationClaim`. It remains truth-apt, but usually carries stronger quantitative metadata requirements.

### 3.5 `HypothesisClaim`

A `HypothesisClaim` is a claim proposed as an explanatory or predictive candidate rather than a settled law or direct observation.

Examples:

- dark-matter interpretation of an anomaly
- hidden-variable explanation of a contradiction pattern

`HypothesisClaim` enters BP like other closed claims, but its epistemic status is distinct.

### 3.6 `LawClaim`

A `LawClaim` is a closed, general scientific assertion whose content includes explicit scope, domain, and regime.

Examples:

- "For rigid bodies in vacuum near Earth, acceleration is mass-independent."
- "For ideal gases in the dilute regime, PV = nRT."

`LawClaim` is not a bare template. It is a **closed** proposition, typically with explicit quantification or domain restriction.

`LawClaim` may participate in BP.

### 3.7 `PredictionClaim`

A `PredictionClaim` is a claim derived from a model, law, or hypothesis under specific assumptions.

Examples:

- "Under the tied-bodies setup, the composite must fall faster."
- "Given model M and parameters theta, the spectrum should peak at lambda."

It is still a `ClosedClaim`, but its provenance and evaluation policy differ from direct observations.

### 3.8 `RegimeAssumption`

A `RegimeAssumption` is a background condition, idealization, or applicability constraint under which a reasoning step or law is intended to hold.

Examples:

- vacuum
- non-relativistic regime
- negligible air resistance
- near-Earth approximation

`RegimeAssumption` is truth-apt and challengeable. In the language it will usually surface through `#setting` and `under:`.

### 3.9 `AbstractClaim`

An `AbstractClaim` is a new, weaker closed claim extracted from multiple more specific claims.

Required property:

- each member claim entails the `AbstractClaim`

This is an upward, truth-preserving move. `AbstractClaim` is a claim, not a template.

### 3.10 `GeneralizationCandidate`

A `GeneralizationCandidate` is a stronger, broader candidate law or explanatory pattern induced from multiple specific cases.

Required property:

- member claims support it, but do **not** individually entail it

This is a non-deductive object. It may later be promoted to a `LawClaim`, but it is not equivalent to an `AbstractClaim`.

### 3.11 `Question`

A `Question` is an inquiry artifact, not a truth-apt proposition.

Examples:

- unresolved scientific problem
- follow-up investigation target

`Question` does not enter BP directly.

## 4. Operator Families

### 4.1 `reasoning_support`

`reasoning_support` is a probabilistic support relation between premises and a conclusion.

This is the family that covers ordinary reasoning links such as:

- deductive-style support
- abductive support
- inductive support

Its exact update laws are defined in [inference-theory.md](inference-theory.md), not here.

### 4.2 `entailment`

`entailment` is a deterministic truth-preserving relation between closed claims.

If `A entails B`, then:

- `A` supports `B`
- `not A` does **not** in general imply `not B`

This family is the right semantic home for many abstraction-style edges.

### 4.3 `instantiation`

`instantiation` derives a specific closed claim from a more general law or schema claim.

Examples:

- from a universal law to a case-specific instance
- from a schema claim to a concrete bound case

`instantiation` is structurally distinct from generic entailment, but its BP kernel may ultimately reuse deterministic entailment semantics.

### 4.4 `inductive_support`

`inductive_support` is probabilistic support from specific cases to a broader hypothesis or law candidate.

It is not truth-preserving. It must remain distinct from `entailment`.

### 4.5 `contradiction` / `equivalence`

These are constraint relations among truth-apt claims.

- `contradiction`: the claims should not both be true
- `equivalence`: the claims should agree in truth value

They may participate in BP as relation-bearing variables and constraint factors, but their exact runtime lowering belongs to [inference-theory.md](inference-theory.md) and [../bp-on-graph-ir.md](../bp-on-graph-ir.md).

## 5. Constructive Operations vs BP Operators

The following distinction is mandatory:

### 5.1 Graph-construction / research operations

These create or propose new knowledge structure:

- `abstraction`
- `generalization`
- `hidden premise discovery`
- `independent evidence audit`

They are **not** automatically BP edge types.

### 5.2 BP operator families

These determine how belief updates propagate once the graph is accepted:

- `reasoning_support`
- `entailment`
- `instantiation`
- `inductive_support`
- `contradiction`
- `equivalence`

Jaynes-style weak syllogisms are contracts on these BP operators, not new language declarations.

## 6. What Enters BP

### 6.1 BP-bearing objects

The following may enter BP after review / acceptance:

- `ClosedClaim`
- `ObservationClaim`
- `MeasurementClaim`
- `HypothesisClaim`
- `LawClaim`
- `PredictionClaim`
- `RegimeAssumption`
- accepted `contradiction` / `equivalence` relations

### 6.2 Non-BP objects

The following do **not** enter BP directly:

- `Template`
- `Question`
- `GeneralizationCandidate` before acceptance
- review findings
- curation suggestions
- loop-audit artifacts
- independent-evidence audit reports

## 7. Language Mapping

Gaia Language should keep a small declaration surface and express most ontology distinctions through parameters and package metadata.

### 7.1 Declaration-level mapping

- `#claim` remains the main surface for truth-apt assertions
- `#setting` remains the main surface for assumptions and regimes
- `#relation` remains the main surface for explicit contradiction / equivalence declarations
- `#question` remains the main surface for open scientific questions

### 7.2 Parameter-level mapping

The following distinctions should appear in language metadata rather than as many new top-level declarations:

- `kind:` for node semantics
  - `observation`
  - `measurement`
  - `hypothesis`
  - `law`
  - `prediction`
- `mode:` for support semantics
  - `deductive`
  - `inductive`
  - `abductive`
- `under:` for regime / background / idealization conditions

### 7.3 `from:` vs `under:`

This is a core distinction:

- `from:` lists load-bearing premises of the reasoning step
- `under:` lists background conditions, regimes, and idealizations under which the reasoning is intended to hold

`under:` is a role in a reasoning step, not a separate node ontology.

## 8. Review / Curation Boundary

Ontology does not collapse review artifacts into knowledge content.

- A potential contradiction discovered by curation is **not yet** a contradiction claim in the accepted graph
- A corroboration / independent-evidence finding is **not** a language relation or BP factor
- A generalization candidate is **not yet** a law

These remain review / curation artifacts until accepted by the appropriate workflow.

## 9. Consequences for Later Docs

Later docs should follow these rules:

1. `theoretical-foundation.md` should explain why scientific reasoning needs this ontology.
2. `gaia-language-spec.md` should expose only the author-facing subset.
3. `graph-ir.md` should define structural representation of accepted ontology objects.
4. `inference-theory.md` should define BP operator contracts on the BP-bearing subset only.
5. Review / curation docs should define how non-BP artifacts are proposed, audited, and possibly accepted.

## 10. Current Direction

For the current foundation reset, Gaia should prefer:

- a small authoring language
- a richer scientific ontology
- a clean separation between accepted graph structure and research / curation artifacts
- loopy BP on accepted closed claims, not on templates or workflow objects
