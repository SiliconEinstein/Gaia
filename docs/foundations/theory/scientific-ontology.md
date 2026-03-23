# Scientific Ontology

> **Status:** Current canonical

## 1. First Principle

Gaia does not formalize abstract logic in isolation. It formalizes **scientific assertions with evidence provenance, applicability conditions, uncertainty, and revisability**.

The core boundary: only closed, truth-apt scientific assertions participate in belief propagation. Open templates, discovery workflows, research tasks, and review artifacts do not.

## 2. What Makes Scientific Reasoning Different

Compared to formal deductive logic, scientific reasoning has five additional layers:

1. **World interface**: premises come from observations, measurements, experiments, and literature -- not from axioms.
2. **Uncertainty**: we rarely prove a proposition true; we assess how believable it is given current evidence.
3. **Applicability conditions**: scientific laws almost always carry regime restrictions, idealizations, and background assumptions.
4. **Defeasibility**: new evidence can weaken old conclusions. Contradiction is not system failure but a knowledge-update signal.
5. **Open-ended discovery**: abduction, induction, and hidden-premise discovery lie outside pure deductive logic.

Therefore Gaia needs:

- a language that can express scientific assertions with their applicability conditions
- an inference system that updates beliefs consistently under uncertainty
- a knowledge lifecycle that accommodates contradiction, retraction, and revision

## 3. Scientific Object Classes

### BP-bearing objects (truth-apt, closed assertions)

| Class | Description | Example |
|---|---|---|
| **ClosedClaim** | A concrete, truth-apt scientific assertion | "The feather and hammer fall at the same rate in lunar vacuum" |
| **ObservationClaim** | A claim whose authority comes from observation | A reported experimental outcome or instrument reading |
| **MeasurementClaim** | An observation with quantitative metadata | "The transition temperature is 92 +/- 1 K" |
| **HypothesisClaim** | An explanatory or predictive candidate | A dark-matter interpretation of an anomaly |
| **LawClaim** | A general assertion with explicit scope and regime | "For ideal gases in the dilute regime, PV = nRT" |
| **PredictionClaim** | A claim derived from a model under specific assumptions | "Given model M, the spectrum should peak at lambda" |
| **RegimeAssumption** | A background condition or idealization | Vacuum, non-relativistic regime, negligible air resistance |

All of these carry a belief value in [0, 1] and participate in BP after acceptance.

### Non-BP objects

| Class | Description | Why excluded |
|---|---|---|
| **Template** | An open proposition schema (e.g., `P(x) -> Q(x)`) | Not closed; no truth value |
| **Question** | An inquiry artifact | Not truth-apt |
| **GeneralizationCandidate** | A broader pattern induced from cases, before acceptance | Not yet accepted into the graph |
| Review findings, curation suggestions | Workflow artifacts | Not knowledge assertions |

## 4. Defeasibility

Scientific beliefs change with new evidence. This is formalized through three mechanisms:

- **Belief update via BP**: when new factors (reasoning links) are added to the graph, BP recomputes all beliefs. A previously high-belief claim can be lowered by new contradictory evidence.
- **Contradiction**: an explicit relation declaring that two claims should not both be true. BP automatically weakens the less-supported claim.
- **Retraction**: an explicit declaration that prior evidence against a claim is withdrawn. The retracted evidence's influence is inverted.

Defeasibility is not a bug or a special case -- it is the core feature that distinguishes scientific reasoning from deductive proof. In Gaia, non-monotonicity (new premises can lower belief in old conclusions) is built into the inference engine.

## 5. Propositions, Not Entities

Traditional knowledge graphs store **entities** (Einstein, Ulm) connected by **relations** (bornIn). Gaia stores **propositions** ("Einstein was born in Ulm") connected by **reasoning links** (premises support conclusions).

| Dimension | Entity-level (traditional KG) | Proposition-level (Gaia) |
|---|---|---|
| Node | A thing in the world | A claim about the world |
| Edge | A relation (bornIn) | A reasoning step (premises -> conclusion) |
| Uncertainty | None (stored = true) | Prior, belief, probability |
| Contradiction | Data quality error | First-class citizen |
| Provenance | Optional metadata | Core structure (reasoning chain) |

## 6. Language Surface Mapping

Gaia Language expresses ontology through a small set of declarations with parameter-level distinctions:

- `#claim` -- the main declaration for truth-apt assertions, with `kind:` parameter (observation, hypothesis, law, prediction, etc.)
- `#setting` -- background conditions and regime assumptions
- `#relation` -- explicit contradiction or equivalence declarations
- `#question` -- open scientific questions (non-BP)

The `from:` parameter lists load-bearing premises; `under:` lists background conditions. This distinction separates the logical structure of reasoning from its applicability context.

## Source

- [../../foundations_archive/theory/scientific-ontology.md](../../foundations_archive/theory/scientific-ontology.md)
- [../../foundations_archive/theory/theoretical-foundation.md](../../foundations_archive/theory/theoretical-foundation.md) (sections 1.1, 1.2)
