# Gaia Python Ecosystem Integration Spec

Status: Draft 0.1  
Target: Gaia v0.6–v1.0  
Primary goal: reuse mature Python packages without letting them define Gaia semantics.

---

## 0. One-line invariant

Gaia owns scientific semantics; external Python packages provide validation, computation, graph algorithms, probability inference, units, optimization, diagnostics, data handling, and interop through explicit adapters.

In short:

```text
Libraries compute.
Gaia defines what the computation means.
```

---

## 1. Scope

This spec defines how Gaia should integrate mature Python packages while preserving Gaia's own semantic core.

It covers:

```text
1. Dependency layering
2. Optional extras
3. Adapter architecture
4. Package-to-Gaia module mapping
5. Backend capability contracts
6. Evidence adapter contracts
7. Unit / quantity adapter contracts
8. Graph / explain / audit integration
9. Probabilistic inference integration
10. Testing and snapshot strategy
11. Version-by-version adoption plan
12. Acceptance checklist
```

This spec is intended to support the existing Gaia roadmap:

```text
v0.5.x  Contract freeze
v0.6    Evidence contract + contexted belief state
v0.7    Evidence model adapters
v0.8    Context reproducibility
v0.9    Quantity / unit / measurement semantics
v0.10   Explain / sensitivity / audit
v0.11   Cross-package reasoning
v1.0    Stable propositional scientific reasoning kernel
```

---

## 2. Non-goals

Gaia should not outsource these concepts to external libraries:

```text
1. Claim semantics
2. Action semantics
3. EvidenceMetadata semantics
4. Review gating semantics
5. InformationContext / BeliefContext semantics
6. BeliefState semantics
7. Gaia IR schema
8. context_id hashing rules
9. scientific package provenance
10. cross-package claim ownership
```

External packages must not determine whether:

```text
observe(E) means E enters the information state I;
review accepted means a factor is active;
a posterior is P(A | I) rather than a raw score;
a support action is structural rather than probabilistic evidence;
an evidence factor is independent of another evidence factor.
```

Those are Gaia semantics.

---

## 3. Required architectural rule

All external package usage must go through adapters or utility layers.

Allowed:

```text
Gaia IR -> Adapter -> external package model -> Adapter result -> Gaia BeliefState
```

Not allowed:

```text
External package model == Gaia IR
External package node == Gaia Claim
External package factor == Gaia EvidenceMetadata
External package output == Gaia BeliefState without normalization
```

The external package must be replaceable without changing Gaia Lang or Gaia IR semantics.

---

## 4. Dependency tiers

### 4.1 Core dependencies

These may be normal Gaia dependencies.

```text
pydantic
```

Optional but strongly recommended for CLI distribution:

```text
typer
rich
```

### 4.2 Recommended internal tooling dependencies

These should be used in development and may be installed as extras:

```text
pytest
hypothesis
deepdiff
networkx
numpy
scipy
```

### 4.3 Optional capability extras

Gaia should define optional extras rather than requiring all scientific packages by default.

Recommended extras:

```toml
[project.optional-dependencies]

cli = [
  "typer",
  "rich",
]

graph = [
  "networkx",
]

prob = [
  "numpy",
  "scipy",
]

pgm = [
  "pgmpy",
  "pyagrum",
]

ppl = [
  "pymc",
  "arviz",
  "numpyro",
  "jax",
]

units = [
  "pint",
]

symbolic = [
  "sympy",
  "z3-solver",
  "cvxpy",
]

data = [
  "pandas",
  "xarray",
]

ontology = [
  "rdflib",
  "owlready2",
]

parser = [
  "lark",
]

dev = [
  "pytest",
  "hypothesis",
  "deepdiff",
]
```

Gaia core must remain installable without heavy optional dependencies such as PyMC, JAX, NumPyro, Pyro, pyAgrum, or Owlready2.

---

## 5. Package responsibility map

| Gaia capability | Recommended package | Integration style | Target phase |
|---|---|---|---|
| IR validation | Pydantic | core schema models | v0.5.x / v0.6 |
| CLI | Typer + Rich | command and rendering layer | v0.6+ |
| Graph analysis | NetworkX | graph views for explain/audit | v0.6+ |
| Basic statistics | NumPy + SciPy | evidence adapters | v0.7 |
| Discrete probabilistic graphical models | pgmpy / pyAgrum | optional backend adapter | v0.9+ |
| Continuous Bayesian models | PyMC / NumPyro / Pyro | optional evidence/model adapter | v0.7+ optional, v0.9+ deeper |
| Bayesian diagnostics | ArviZ | diagnostics normalization | v0.7+ optional |
| MaxEnt / optimization | SciPy + CVXPY | MaxEnt adapter | v0.9+ |
| Symbolic math | SymPy | expression adapter | v0.9+ |
| Hard constraints | Z3 | consistency-check adapter | v0.9+ |
| Units | Pint | unit adapter | v0.9 |
| Tabular data | pandas | DatasetRef loader | v0.7+ |
| Multidimensional scientific data | xarray | DatasetRef loader | v0.9+ |
| RDF / OWL interop | RDFLib / Owlready2 | ontology export/import adapter | v0.11+ |
| Standalone parser | Lark | optional future surface language | v1.1+ |
| Testing | pytest / Hypothesis / DeepDiff | tests and snapshots | v0.5.x+ |

---

## 6. Core semantic objects Gaia must own

The following objects must remain Gaia-native:

```text
Claim
Note
Question
Action
Derive
Observe
Compute
Infer
Equal
Contradict
Exclusive
EvidenceMetadata
ReviewManifest
BeliefContext
BeliefState
Gaia IR Knowledge
Gaia IR Strategy
Gaia IR Operator
ParameterizationRecord
DependencyContextRecord
```

External libraries may provide implementation support, but cannot redefine their semantics.

---

## 7. Adapter architecture

### 7.1 BackendAdapter protocol

Backends that run inference over a Gaia problem should implement:

```python
from typing import Protocol, Any

class BackendAdapter(Protocol):
    name: str
    capabilities: set[str]

    def supports(self, problem: "GaiaProblem") -> bool:
        ...

    def compile(self, problem: "GaiaProblem") -> "BackendModel":
        ...

    def run(self, model: "BackendModel", query: "GaiaQuery") -> "BackendResult":
        ...

    def normalize_result(
        self,
        result: "BackendResult",
        context: "BeliefContext",
    ) -> "BeliefState":
        ...
```

Required rule:

```text
BackendResult must never be returned directly to users as Gaia semantics.
It must be normalized into BeliefState.
```

### 7.2 EvidenceAdapter protocol

Evidence adapters convert scientific data/model specs into Gaia likelihood evidence.

```python
from typing import Protocol

class EvidenceAdapter(Protocol):
    name: str
    evidence_kind: str

    def supports(self, spec: "EvidenceSpec") -> bool:
        ...

    def to_evidence_metadata(self, spec: "EvidenceSpec") -> "EvidenceMetadata":
        ...

    def to_infer_action(self, spec: "EvidenceSpec") -> "Infer":
        ...
```

Required output:

```text
hypothesis claim
 evidence claim
 P(E | H)
 P(E | ¬H)
 source_id
 data_id
 model_id
 independence_group
 assumptions
 diagnostics, if available
```

### 7.3 UnitAdapter protocol

```python
from typing import Protocol, Any

class UnitAdapter(Protocol):
    name: str

    def parse_quantity(self, value: Any, unit: str) -> "Quantity":
        ...

    def check_compatible(self, a: "Quantity", b: "Quantity") -> bool:
        ...

    def convert(self, q: "Quantity", target_unit: str) -> "Quantity":
        ...

    def dimensionality(self, q: "Quantity") -> "Dimension":
        ...
```

Pint should be the first implementation, but Gaia's public Quantity semantics should not equal Pint's internal object model.

### 7.4 GraphViewAdapter protocol

Graph tooling should be used through views.

```python
class GraphViewAdapter(Protocol):
    name: str

    def claim_graph(self, ir: "GaiaIR") -> "GraphView":
        ...

    def evidence_graph(self, ir: "GaiaIR") -> "GraphView":
        ...

    def dependency_graph(self, package: "GaiaPackage") -> "GraphView":
        ...
```

NetworkX may implement GraphView, but Gaia should not require NetworkX objects inside Gaia IR.

---

## 8. Pydantic schema integration

### 8.1 Required usage

Use Pydantic for:

```text
EvidenceMetadata
BeliefContext
BeliefState
ReviewManifest
ParameterizationRecord
DependencyContextRecord
Adapter result schemas
```

### 8.2 Gaia-owned additions

Pydantic does not provide Gaia's semantic versioning. Gaia must implement:

```text
schema_version fields
canonical JSON serialization
stable SHA-256 hashing
migration utilities
strict/lenient load modes
```

### 8.3 Canonical JSON requirement

Every schema object that participates in hashing must support:

```python
obj.to_canonical_json()
obj.stable_hash()
```

or equivalent utilities:

```python
canonical_json(obj)
stable_hash(obj)
```

Non-hash fields must be explicitly marked, for example:

```text
generated_at
elapsed_ms
debug logs
absolute file paths
```

---

## 9. CLI integration

### 9.1 Recommended packages

```text
Typer for command structure
Rich for formatted output
```

### 9.2 Required commands affected by this spec

```bash
gaia infer
gaia explain
gaia audit
gaia check
gaia context diff
```

### 9.3 CLI output rule

Human-readable CLI output may use Rich formatting, but machine-readable output must remain stable JSON.

Required machine-readable files:

```text
.gaia/ir.json
.gaia/review_manifest.json
.gaia/context.json
.gaia/belief_state.json
.gaia/beliefs.json
```

---

## 10. Graph analysis integration

### 10.1 Recommended package

```text
NetworkX
```

### 10.2 Use cases

NetworkX may be used for:

```text
cycle detection
orphan claim detection
connected components
support/evidence path search
explain traversal
duplicate evidence source graph
cross-package bridge graph
package dependency graph
```

### 10.3 Non-use cases

NetworkX must not define:

```text
Gaia IR identity
Claim identity
EvidenceMetadata identity
BeliefContext identity
```

Graph views are derived from Gaia IR, not the other way around.

---

## 11. Probabilistic inference integration

### 11.1 Gaia-native backend remains allowed

Gaia should keep its existing binary claim graph backend as the reference backend for:

```text
small exact inference
JT / BP / GBP development
review gating tests
contract snapshots
```

### 11.2 Optional discrete PGM backends

Optional adapters may target:

```text
pgmpy
pyAgrum
```

These adapters should support:

```text
binary claim variables
discrete CPTs
evidence pinning
posterior marginal queries
optional model evidence if backend supports it
```

They must return Gaia BeliefState.

### 11.3 Optional continuous Bayesian backends

Optional adapters may target:

```text
PyMC
NumPyro
Pyro
```

Initial use should be evidence-adapter oriented:

```text
external Bayesian model -> posterior / Bayes factor / likelihood ratio -> Gaia EvidenceMetadata
```

Gaia IR should not be fully lowered to PPL programs until the Gaia evidence and context contracts are stable.

### 11.4 Diagnostics normalization

If a PPL backend is used, diagnostics should be normalized into:

```text
BeliefState.diagnostics
EvidenceMetadata.model_diagnostics
```

ArviZ should be the default diagnostics source for PyMC / NumPyro style outputs.

---

## 12. Evidence adapter integration

### 12.1 v0.7 first adapters

The first evidence adapters should be:

```text
BinomialEvidenceAdapter
TwoBinomialEvidenceAdapter
GaussianMeasurementEvidenceAdapter
BayesFactorEvidenceAdapter
```

### 12.2 Recommended packages

```text
NumPy
SciPy
```

### 12.3 Adapter output invariant

Every evidence adapter must output either:

```text
P(E | H), P(E | ¬H)
```

or:

```text
likelihood ratio / Bayes factor
```

which is then normalized into `EvidenceMetadata`.

### 12.4 Required metadata

Each generated evidence factor must include:

```text
evidence_kind
source_id, if known
data_id, if known
model_id, if known
independence_group, if known
assumptions
query
adapter_name
generated_from
```

### 12.5 Duplicate evidence rule

If two active evidence factors share the same non-null `independence_group`, Gaia must warn during audit.

---

## 13. MaxEnt / optimization integration

### 13.1 Recommended packages

```text
SciPy
CVXPY
```

### 13.2 Gaia-owned MaxEnt schema

Gaia must own:

```text
MaxEntPriorSpec
support
base_measure
constraints
parameterization
coordinate_system
justification
provenance
```

### 13.3 Solver usage

Allowed:

```text
MaxEntPriorSpec -> SciPy/CVXPY optimization -> prior distribution summary
```

Not allowed:

```text
CVXPY problem object == Gaia prior spec
```

### 13.4 Continuous prior warning

If a continuous MaxEnt prior lacks a base measure or parameterization, Gaia must warn or reject according to strictness level.

---

## 14. Symbolic and hard-constraint integration

### 14.1 Recommended packages

```text
SymPy
Z3
```

### 14.2 SymPy use cases

SymPy may be used for:

```text
formula canonicalization
simple algebraic simplification
residual expression construction
symbolic derivative for simple models
LaTeX rendering
```

### 14.3 Z3 use cases

Z3 may be used for:

```text
operator consistency checks
exclusive partition satisfiability
simple numerical range constraints
contradiction checks
type/range validation
```

### 14.4 Separation rule

Z3 answers hard logical questions:

```text
I entails A?
I entails not A?
I is inconsistent?
```

Probability backends answer probabilistic questions:

```text
P(A | I)
```

Do not conflate the two.

---

## 15. Unit and measurement integration

### 15.1 Recommended package

```text
Pint
```

### 15.2 Gaia-owned schema

Gaia must own:

```text
Quantity
UnitRef
DimensionRef
Uncertainty
MeasurementSpec
MeasurementClaim
```

### 15.3 Pint responsibilities

Pint may provide:

```text
unit parsing
unit conversion
dimensionality check
quantity arithmetic
```

### 15.4 Gaia responsibilities

Gaia must define:

```text
what measurement means
how uncertainty becomes likelihood
how observed measurement enters context
how density units are tracked
how quantity claims are rendered and hashed
```

---

## 16. Data integration

### 16.1 Recommended packages

```text
pandas
xarray
```

### 16.2 DatasetRef rule

Gaia IR should not store large datasets inline.

Use:

```text
DatasetRef
source_id
data_hash
schema
slice/query/statistic
provenance
```

Adapters may load the referenced data using pandas or xarray.

### 16.3 Data hash requirement

Evidence adapters that consume external data must record:

```text
data_id
data_hash, if available
source_id
query/slice used
```

This is required for reproducibility and double-count detection.

---

## 17. Ontology / RDF / OWL integration

### 17.1 Recommended packages

```text
RDFLib
Owlready2
```

### 17.2 Target phase

This is not part of v0.6 or v0.7.

Target:

```text
v0.11+
```

### 17.3 Allowed uses

```text
export Gaia claims to RDF
import ontology classes as entity/type hints
map Gaia namespaces to URIs
cross-package concept alignment
SPARQL interop
OWL consistency checks as optional validation
```

### 17.4 Non-use rule

RDF triples must not become Gaia's native claim semantics.

Gaia claims may be exported to RDF; they are not defined by RDF.

---

## 18. Parser integration

### 18.1 Recommended package

```text
Lark
```

### 18.2 Target phase

Standalone parser is not a v1.0 requirement.

Target:

```text
v1.1+
```

### 18.3 Rule

Do not build a standalone `.gaia` surface language until Gaia Lang / IR / Evidence / Context contracts are stable.

---

## 19. Testing integration

### 19.1 Recommended packages

```text
pytest
hypothesis
deepdiff
```

### 19.2 pytest required uses

```text
unit tests
integration tests
CLI tests
snapshot tests
regression tests
```

### 19.3 Hypothesis required uses

Hypothesis should test invariants such as:

```text
probability values are clamped or rejected according to policy
context_id stable under non-semantic output changes
context_id changes under semantic changes
unobserved likelihood does not update posterior
review rejected means factor inactive
canonical JSON roundtrip preserves identity
```

### 19.4 DeepDiff required uses

DeepDiff should support:

```text
golden snapshot diffs
context diffs
belief_state diffs
IR diffs
```

Snapshot diff must ignore:

```text
generated_at
elapsed_ms
absolute paths
random temp paths
debug-only logs
```

---

## 20. Version-by-version adoption plan

### 20.1 v0.5.x — Contract freeze

Packages to use:

```text
Pydantic
pytest
DeepDiff
Hypothesis
NetworkX, optional
```

Deliverables:

```text
stable schema models
golden snapshots
code-truth docs
version matrix
canonical JSON / hash tests
```

Non-goals:

```text
PyMC / NumPyro
Pint
RDF / OWL
standalone parser
```

---

### 20.2 v0.6 — Evidence contract + contexted belief state

Packages to use:

```text
Pydantic
Typer / Rich, if CLI migration is desired
NetworkX, optional for explain/audit
pytest / Hypothesis / DeepDiff
```

Deliverables:

```text
EvidenceMetadata
BeliefContext
BeliefState
likelihood / likelihood_ratio / bayes_factor helpers
context_id
belief_state.json
gaia explain minimal
gaia audit evidence minimal
```

External computation packages are not required for v0.6.

---

### 20.3 v0.7 — Evidence model adapters

Packages to use:

```text
NumPy
SciPy
ArviZ optional
PyMC / NumPyro optional
```

Deliverables:

```text
BinomialEvidenceAdapter
TwoBinomialEvidenceAdapter
GaussianMeasurementEvidenceAdapter
BayesFactorEvidenceAdapter
adapter diagnostics
evidence provenance
duplicate independence_group warnings
```

Rule:

```text
Adapters output Gaia EvidenceMetadata / InferAction.
They do not bypass Gaia evidence semantics.
```

---

### 20.4 v0.8 — Context reproducibility

Packages to use:

```text
Pydantic
DeepDiff
Hypothesis
```

Deliverables:

```text
context diff
context load/verify
stable context hashing
dependency context records
prior resolution hashing
```

---

### 20.5 v0.9 — Quantity / unit / measurement

Packages to use:

```text
Pint
SciPy
pandas, optional
xarray, optional
SymPy, optional
Z3, optional
CVXPY, optional for MaxEnt
```

Deliverables:

```text
Quantity
UnitRef
Uncertainty
MeasurementSpec
GaussianMeasurementEvidence with units
unit compatibility checks
measurement likelihood conversion
basic MaxEnt prior spec
```

---

### 20.6 v0.10 — Explain / sensitivity / audit

Packages to use:

```text
NetworkX
DeepDiff
SciPy
Rich
```

Deliverables:

```text
path-based explain
sensitivity perturbation
prior sensitivity
evidence-group sensitivity
double-count audit
orphan claim audit
review gate audit
```

---

### 20.7 v0.11 — Cross-package reasoning

Packages to use:

```text
NetworkX
Pydantic
RDFLib optional
Owlready2 optional
```

Deliverables:

```text
package dependency graph
bridge graph
foreign context verification
cross-package evidence source audit
namespace / URI mapping optional
```

---

### 20.8 v1.0 — Stable kernel

Packages to use:

```text
minimal required dependencies only
optional backend extras remain optional
```

Deliverables:

```text
stable Gaia core contracts
stable IR schema
stable evidence contract
stable context / belief state
stable review gating
pluggable backend adapters
```

v1.0 must not depend on heavyweight optional backends.

---

## 21. Backend capability registry

Gaia should expose a backend registry.

Example:

```python
@dataclass(frozen=True)
class BackendCapability:
    name: str
    supports_binary_claims: bool = False
    supports_discrete_cpts: bool = False
    supports_continuous_latents: bool = False
    supports_model_evidence: bool = False
    supports_exact_inference: bool = False
    supports_approximate_inference: bool = False
    supports_diagnostics: bool = False
```

Registry example:

```python
BACKENDS = {
    "gaia-native": GaiaNativeBackend(),
    "pgmpy": PgmpyBackendAdapter(),
    "pyagrum": PyAgrumBackendAdapter(),
    "pymc": PyMCBackendAdapter(),
    "numpyro": NumPyroBackendAdapter(),
}
```

Backend selection must be explicit or recorded:

```text
BeliefContext.inference.method
BeliefContext.inference.actual_method
BeliefContext.inference.config
```

---

## 22. Adapter result normalization

Every adapter result must be normalized before entering Gaia outputs.

### 22.1 Inference result normalization

External inference outputs must become:

```text
BeliefState
```

Required fields:

```text
context_id
beliefs
method_used
is_exact
treewidth, if applicable
elapsed_ms, if measured
diagnostics
```

### 22.2 Evidence result normalization

External statistical outputs must become:

```text
EvidenceMetadata
InferAction
```

Required fields:

```text
evidence_kind
p_e_given_h / p_e_given_not_h or likelihood_ratio / bayes_factor
source_id
data_id
model_id
independence_group
assumptions
query
diagnostics
```

### 22.3 Unit result normalization

External unit objects must become Gaia-native:

```text
Quantity
UnitRef
DimensionRef
```

---

## 23. Security and dependency hygiene

### 23.1 Optional imports

Heavy dependencies must be imported lazily.

Allowed:

```python
def run_pymc_adapter(...):
    import pymc as pm
```

Not allowed in Gaia core import path:

```python
import pymc
import numpyro
import pyagrum
import owlready2
```

### 23.2 Error messages

If an optional dependency is missing, Gaia should return:

```text
This feature requires gaia[ppl]. Install with: pip install 'gaia-lang[ppl]'
```

### 23.3 Reproducibility

BeliefContext should record adapter names and versions where available.

Example:

```json
{
  "adapter_versions": {
    "scipy": "...",
    "pint": "...",
    "pymc": "..."
  }
}
```

Exact version capture is required for optional probabilistic and optimization backends once used in a BeliefState.

---

## 24. Acceptance checklist

This spec is satisfied when:

```text
[ ] Gaia core imports without heavy optional scientific packages.
[ ] EvidenceMetadata, BeliefContext, and BeliefState use stable schema models.
[ ] External package usage is behind adapters or utility boundaries.
[ ] Inference backend outputs are normalized into BeliefState.
[ ] Evidence adapter outputs are normalized into EvidenceMetadata / InferAction.
[ ] Unit adapter outputs are normalized into Gaia Quantity / UnitRef.
[ ] NetworkX graph views do not mutate Gaia IR.
[ ] Optional dependencies are loaded lazily.
[ ] Missing optional dependencies produce clear installation messages.
[ ] context_id records adapter-relevant semantic configuration.
[ ] Golden snapshots ignore non-semantic fields but catch semantic changes.
[ ] Hypothesis tests cover canonical JSON and context_id invariants.
[ ] Duplicate evidence auditing uses Gaia metadata, not backend internals.
[ ] v1.0 Gaia core does not require PPL, ontology, parser, or heavy scientific extras.
```

---

## 25. Minimal PR plan

### PR-A: Optional dependency layout

Files:

```text
pyproject.toml
docs/specs/gaia-python-ecosystem-integration-spec.md
```

Tasks:

```text
1. Add optional extras groups.
2. Ensure core install remains lightweight.
3. Add missing optional dependency error helper.
```

---

### PR-B: Adapter base protocols

Files:

```text
gaia/adapters/base.py
gaia/adapters/registry.py
```

Tasks:

```text
1. Add BackendAdapter protocol.
2. Add EvidenceAdapter protocol.
3. Add UnitAdapter protocol.
4. Add registry functions.
```

---

### PR-C: SciPy evidence adapters

Files:

```text
gaia/adapters/evidence/scipy_binomial.py
gaia/adapters/evidence/scipy_gaussian.py
```

Tasks:

```text
1. Implement BinomialEvidenceAdapter.
2. Implement GaussianMeasurementEvidenceAdapter.
3. Return EvidenceMetadata / InferAction.
```

---

### PR-D: NetworkX graph views

Files:

```text
gaia/adapters/graph/networkx_views.py
```

Tasks:

```text
1. Build claim graph view.
2. Build evidence graph view.
3. Build dependency graph view.
4. Use in explain/audit without mutating IR.
```

---

### PR-E: Pint unit adapter

Files:

```text
gaia/adapters/units/pint_adapter.py
```

Tasks:

```text
1. Parse Gaia Quantity into Pint quantity.
2. Validate compatibility.
3. Convert units.
4. Normalize back to Gaia Quantity.
```

---

## 26. Final design rule

Gaia should maximize reuse of mature Python packages, but only below the semantic boundary.

The semantic boundary is:

```text
Claim / Action / Evidence / Review / Context / BeliefState / IR
```

Everything below that boundary may be delegated.
Everything above that boundary must remain Gaia-owned.
