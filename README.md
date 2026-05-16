# Gaia Lang

[![CI](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml/badge.svg)](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml)
[![Docs](https://github.com/SiliconEinstein/Gaia/actions/workflows/docs.yml/badge.svg)](https://siliconeinstein.github.io/Gaia/)
[![PyPI](https://img.shields.io/pypi/v/gaia-lang.svg)](https://pypi.org/project/gaia-lang/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Contributing?** Read [`AGENTS.md`](AGENTS.md).

Gaia is a formal language for scientific reasoning. It helps you turn informal scientific arguments into explicit propositions, reviewable reasoning steps, and probabilistic belief updates. The recommended v0.5 style is deliberately small: write the uncertain scientific statements as `claim(...)`, keep background context as non-probabilistic `note(...)`, connect claims with `derive(...)`, `observe(...)`, `compute(...)`, and reviewable relations such as `equal(...)` or `contradict(...)`, then let inference compute the marginal belief of every claim.

The probability semantics follow the Jaynesian program: once the information set is made explicit, posterior beliefs are not informal guesses. They are the result of applying probability theory to the declared structure. Gaia's job is to make that structure inspectable enough that humans and agents can argue about the right premises, rather than hiding uncertainty inside prose.

## Quick Example

Galileo's falling-body argument is a good example of the v0.5 style. Daily experience supports both models: heavy bodies often fall faster in air. The difference is that the Aristotelian weight-speed model also produces an internal contradiction in the tied-body thought experiment, while the medium-resistance model can predict the vacuum counterfactual without treating vacuum falling as an observed fact.

```mermaid
flowchart TD
    subgraph inputs["Starting claims"]
        direction LR
        daily["📋 Heavy faster in air<br/>explicit prior 0.900"]:::premise
        aristotle["🏛️ Weight-speed model<br/>MaxEnt neutral"]:::premise
        medium["🌬️ Medium-resistance model<br/>MaxEnt neutral"]:::premise
    end

    subgraph daily_paths["1. Daily check"]
        direction LR
        derive_a_daily(["🧠 derive"]):::strategy
        a_pred["🏛️ predicts:<br/>heavy faster in air"]:::derived
        equal_a{{"≡ equal"}}:::relation_op

        derive_m_daily(["🧠 derive"]):::strategy
        m_pred["🌬️ predicts:<br/>heavy faster in air"]:::derived
        equal_m{{"≡ equal"}}:::relation_op
    end

    subgraph contradiction_path["2. Tied-body contradiction"]
        direction LR
        derive_fast(["🧠 derive"]):::strategy
        faster["🪨+🪶 faster<br/>than 🪨"]:::derived
        derive_slow(["🧠 derive"]):::strategy
        slower["🪨+🪶 slower<br/>than 🪨"]:::derived
        contra{{"⊗ contradict"}}:::contra
    end

    subgraph vacuum_path["3. Vacuum prediction"]
        direction LR
        derive_vacuum(["🧠 derive"]):::strategy
        vacuum["💡 Equal fall<br/>in vacuum"]:::derived
    end

    aristotle --> derive_a_daily --> a_pred
    a_pred --- equal_a
    daily --- equal_a

    medium --> derive_m_daily --> m_pred
    m_pred --- equal_m
    daily --- equal_m

    aristotle --> derive_fast --> faster
    aristotle --> derive_slow --> slower
    faster --- contra
    slower --- contra

    medium --> derive_vacuum --> vacuum

    classDef premise fill:#ddeeff,stroke:#4488bb,color:#222
    classDef strategy fill:#f3e5f5,stroke:#7b1fa2,color:#222
    classDef derived fill:#ddffdd,stroke:#44aa44,color:#222
    classDef relation_op fill:#fff3cd,stroke:#b58900,color:#222
    classDef contra fill:#ffebee,stroke:#c62828,color:#222
```

Only the everyday observation receives an explicit prior. The two model
hypotheses are independent inputs, but the example intentionally leaves them
without author priors: Gaia applies MaxEnt, which gives the neutral starting
point `0.5` without pretending that `0.5` is a sourced prior. Relation helper
claims are folded into the `equal` / `contradict` operator boxes to keep the
diagram readable. Derived claims receive no independent prior and are
marginalized by inference.

Current prior coverage for this example:

| Claim | Prior source | Meaning |
|-------|--------------|---------|
| `daily_observation` | `user_priors`, value `0.9` | Familiar in-air empirical background |
| `aristotle_model` | MaxEnt | Independent model hypothesis with no sourced prior |
| `medium_model` | MaxEnt | Independent model hypothesis with no sourced prior |
| `vacuum_equal_fall_prediction` | derived | No external prior; produced from the medium-resistance model path |

`gaia run infer` is a local numerical preview over the compiled graph. It does not
require `.gaia/review_manifest.json` entries to be accepted before showing how
the authored reasoning changes beliefs. Review status is still important for
`gaia build check --gate`, `gaia inquiry review`, traces, and publication decisions,
but it is not a numeric prior and does not suppress local preview beliefs. The
current compiled graph gives:

| Claim | Local preview belief |
|-------|-------------------------------:|
| `daily_observation` | 0.964 |
| `aristotle_model` | 0.008 |
| `medium_model` | 0.643 |
| `vacuum_equal_fall_prediction` | 0.821 |

The core DSL for this example is:

```python
from gaia.engine.lang import claim, contradict, derive, equal, note

# 📝 Background notes describe setups. They do not carry probabilities.
thought_setup = note("Tied-body setup: a heavy body and a light body are bound together.")
vacuum_setup = note("Vacuum setup: the resisting medium is absent.")

# 📋 The everyday observation both sides must explain.
daily_observation = claim("In air, heavy bodies often fall faster than light bodies.")

# 🏛️ Model A says weight itself sets the natural falling speed.
aristotle_model = claim("Model A: weight itself causes greater natural falling speed.")

# 🌬️ Model B says the observed in-air difference comes from the medium.
medium_model = claim("Model B: in-air speed differences are caused by medium resistance.")

# ✅ First check: both models can match familiar falling in air.
aristotle_daily_prediction = derive(
    "Under Model A, heavy bodies should fall faster in air.",
    given=aristotle_model,
    rationale="Weight directly increases natural falling speed.",
)
equal(
    aristotle_daily_prediction, daily_observation,
    rationale="The daily observation matches Model A's prediction.",
)

medium_daily_prediction = derive(
    "Under Model B, heavy bodies can fall faster than light bodies in air.",
    given=medium_model,
    rationale="Medium resistance can create the observed speed difference.",
)
equal(
    medium_daily_prediction, daily_observation,
    rationale="The daily observation matches Model B's prediction.",
)

# 🤔 Galileo's tied-body test: Model A pulls in two opposite directions.
# If the tied pair is heavier, it should fall faster; if the light body
# retards the heavy body, the same tied pair should fall slower.
composite_faster = derive(
    "The tied composite should fall faster than the heavy body alone.",
    given=aristotle_model,
    background=[thought_setup],
    rationale="The composite has greater total weight.",
)
composite_slower = derive(
    "The tied composite should fall slower than the heavy body alone.",
    given=aristotle_model,
    background=[thought_setup],
    rationale="The slower light body should retard the heavy body.",
)
contradict(
    composite_faster, composite_slower,
    rationale="Model A yields incompatible predictions for the same composite.",
)

# 💡 Counterfactual prediction: remove the medium, remove the in-air difference.
vacuum_equal_fall_prediction = derive(
    "In vacuum, bodies of different weights fall at the same rate.",
    given=medium_model,
    background=[vacuum_setup],
    rationale="If medium resistance causes the difference, no medium removes it.",
)
```

The belief table above also uses the `priors.py` pattern shown in the quick
start below; the complete runnable package lives in
`examples/galileo-v0-5-gaia`.

## How it Works

```
Python DSL  →  gaia build compile  →  Gaia IR (factor graph)  →  gaia run infer  →  beliefs
```

1. **Declare** claims, notes, actions, and relations using the Python DSL.
2. **Compile** to Gaia IR — a canonical graph of knowledge nodes, actions, and deterministic operators.
3. **Infer** locally — exact inference or belief propagation previews posterior marginals for every claim in the compiled graph.
4. **Review / gate** warrants separately when deciding whether the package is ready to publish or register.

The system implements a Jaynes-style Robot architecture: you (or an AI agent) provide the declared structure; the engine computes the posterior implied by that structure. Construction can be wrong — and that is useful. Bad structure shows up as surprising beliefs, uncovered priors, failed gates, or contradictions that force you to expose hidden assumptions.

## Install

```bash
pip install gaia-lang
```

For development:

```bash
git clone https://github.com/SiliconEinstein/Gaia.git
cd Gaia && uv sync
```

## Gallery

Published Gaia knowledge packages:

| Package | Source | Knowledge nodes |
|---------|--------|-----------------|
| [SuperconductivityElectronLiquids.gaia](https://github.com/kunyuan/SuperconductivityElectronLiquids.gaia) | arXiv:2512.19382 — Superconductivity in Electron Liquids | 78 |
| [watson-rfdiffusion-2023-gaia](https://github.com/kunyuan/watson-rfdiffusion-2023-gaia) | Watson et al. 2023 — De novo design of protein structure and function with RFdiffusion | 128 |
| [GalileoFallingBodies.gaia](https://github.com/kunyuan/GalileoFallingBodies.gaia) | Galileo's falling bodies thought experiment | 7 |

## CLI Workflow

```
gaia build init → gaia pkg add → /gaia:formalization → gaia build compile → gaia run infer → gaia run render → /gaia:publish → gaia pkg register
(scaffold)  (add deps)  (author DSL + priors)  (DSL → IR)   (BP beliefs)  (present)    (fill narrative) (registry PR)
```

`gaia ...` steps are CLI commands; `/gaia:...` steps are [Claude Code](https://claude.ai/code) skills provided by this repo's plugin (see "All Skills" above) — invoke them by typing the slash command in a Claude Code session.

| Command | Purpose |
|---------|---------|
| `gaia build init <name>` | Scaffold a new Gaia knowledge package |
| `gaia pkg add <package>` | Install a registered Gaia package from the [official registry](https://github.com/SiliconEinstein/gaia-registry) |
| `gaia build compile [path]` | Compile Python DSL to Gaia IR (`.gaia/ir.json`, `.gaia/ir_hash`, compile metadata, package manifests) |
| `gaia build check [path]` | Validate package structure and IR consistency (used by registry CI) |
| `gaia build check --brief [path]` | Show per-module warrant structure overview (claims, strategies, priors) |
| `gaia build check --show <name> [path]` | Expand a module or claim label with full warrant trees |
| `gaia build check --hole [path]` | Detailed prior review report for all independent claims (holes + covered) |
| `gaia build check --warrants [path]` | Export reviewable warrants and audit questions |
| `gaia build check --warrants --blind [path]` | Export warrants without status values or prior diagnostics for blank-slate review |
| `gaia build check --inquiry [path]` | Show goal-oriented reasoning progress and review status |
| `gaia build check --gate [path]` | Run publication-quality gate checks and exit non-zero on failure |
| `gaia run infer [path]` | Preview posterior beliefs from explicit priors and the compiled reasoning graph |
| `gaia run infer --depth 1 [path]` | Joint cross-package inference merging dependency factor graphs |
| `gaia run render --target github [path]` | Generate GitHub publication bundle (`.github-output/`): README, wiki pages, graph data, assets |
| `gaia run render --target docs [path]` | Generate per-module detailed reasoning to `docs/detailed-reasoning.md` |
| `gaia run render [path]` | Default: always render docs; also render GitHub output when fresh `.gaia/beliefs.json` exists (`--target all`) |
| `gaia inspect starmap [path]` | Emit a starmap of a Gaia knowledge package in three formats. Default `--format html` (`.gaia/starmap.html`): single-file interactive WebGL viewer (~10k nodes), double-click to open, no server required. `--format dot` (`.gaia/starmap.dot`): paper-ready Graphviz source. `--format svg` (`.gaia/starmap.svg`): rendered via Graphviz with embedded glow filters when `--theme stellaris`. `--theme {light,stellaris,dark}` (default `light`): `stellaris`/`dark` is a deep-space palette with sfdp force-directed layout, multi-layer SVG glows on contradictions, gold-edge support strategies, and root-claim highlight |
| `gaia inspect starmap-replay [path]` | Render an HTML replay from an LKM discovery run. Requires `artifacts/lkm-discovery/retrieval_log.jsonl` and `artifacts/lkm-discovery/graph_growth_log.jsonl`; default output is `.gaia/starmap-replay.html` |
| `gaia inquiry review [path]` | Semantic review loop. Runs BP and surfaces diagnostic findings on the package (low-belief leaves, contradictions, hypothesis equipoise, etc.). Subcommands: `focus`, `reject`, `obligation`, `hypothesis`, `tactics` for managing the inquiry state |
| `gaia trace verify <trace>` | ARM execution-trace tooling. `verify`: schema + hash-chain check. `review`: full eight-section review. `show`: print event stream in `tactic_log` style |
| `gaia pkg register [path]` | Submit package to the [Gaia Official Registry](https://github.com/SiliconEinstein/gaia-registry) |

## Quick Start

This walkthrough uses the Galileo example from above.

**1. Initialize and write code**

```bash
gaia build init galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia
```

Place the DSL code from the Quick Example into `src/galileo_falling_bodies/__init__.py`.

**2. Compile and validate**

```bash
gaia build compile .
gaia build check .
```

**3. Assign informative priors** for independent probabilistic inputs via `priors.py`:

`src/galileo_falling_bodies/priors.py`:

```python
from gaia.engine.lang import register_prior

from . import daily_observation

register_prior(
    daily_observation,
    0.9,
    justification="Familiar empirical background in air.",
)
```

The v0.5 prior contract is deliberately strict:

- Give external priors only to independent probabilistic inputs that are load-bearing for exported goals and are not already pinned by a zero-premise observation.
- A zero-premise `observe(...)` pins its conclusion to `1 - CROMWELL_EPS`; do not add a separate external prior for it.
- Do not assign priors to claims concluded by `derive(...)`, `compute(...)`, or `observe(..., given=...)`; BP marginalizes them from the declared graph.
- Do not assign priors to structural/helper claims from `~`, `&`, `|`, `infer(...)`, `associate(...)`, `equal(...)`, `contradict(...)`, `exclusive(...)`, or generated formalization helpers.
- Do not export the legacy `PRIORS = {...}` dict from `priors.py`; v0.5+ rejects it. Use `register_prior(...)` so each prior has explicit source provenance and can participate in multi-source resolution.
- Do not register a `0.5` prior merely to say "neutral". If a model hypothesis has no sourced prior information yet, leave it unset and let `gaia build check --hole .` report it as MaxEnt. Claims reported as MaxEnt are independent degrees of freedom without external priors; leaving them unset means Gaia uses the maximum-entropy distribution over those free variables, subject to the hard logical constraints already declared.

**4. Infer and publish**

```bash
gaia build compile .                    # re-compile to inject priors into metadata
gaia run infer .                      # compute beliefs via belief propagation
gaia run render . --target github     # generate GitHub README/wiki/data bundle
```

Then use `/gaia:publish` to fill in the narrative, and `gaia pkg register` to submit to the official registry.

For the full tutorial, see [CLI Workflow](docs/foundations/cli/workflow.md).

## DSL Surface

### Recommended v0.5 Authoring Surface

#### Knowledge

| Function | Description |
|----------|-------------|
| `claim(content, proposition=None, *, prior=None, formula=None, kind=ClaimKind.GENERAL, background=None, parameters=None, provenance=None, ...)` | Scientific assertion — the only knowledge type carrying probability. Inline `prior=` is a compatibility shortcut routed through `register_prior(..., source_id="claim_inline")` |
| `note(content, *, format="markdown")` | Background context — no probability, no BP participation |
| `question(content)` | Open research inquiry |

#### Action Verbs

| Function | Description |
|----------|-------------|
| `observe(conclusion, *, given, background, rationale)` | Empirical warrant; with no `given`, pins the conclusion to `1 - CROMWELL_EPS` |
| `derive(conclusion, *, given, background, rationale)` | Reviewable deterministic derivation; lowers to a deterministic implication in the compiled graph |
| `compute(ClaimType, *, fn, given, background, rationale)` | Deterministic computation with claim inputs |
| `infer(evidence, *, hypothesis, background=None, rationale="", p_e_given_h, p_e_given_not_h=0.5)` | Probabilistic prediction/evidence link; returns the evidence claim and creates an internal likelihood warrant for review |
| `associate(a, b, *, p_a_given_b, p_b_given_a, pattern=None, background=None, rationale="")` | Symmetric probabilistic association; returns a reviewable association helper claim. Marginal priors belong on claims or in `priors.py`, not in `associate(...)` |
| `depends_on(conclusion, *, given, background=None, rationale="")` | Scaffold record for load-bearing dependencies that are not formalized yet |
| `candidate_relation(claims=[...], *, pattern=None, background=None, rationale="")` | Scaffold record for a hypothesized relation that is not formalized yet |
| `materialize(scaffold, *, by, rationale="")` | Bookkeeping link from scaffold to the formal graph records that handle it |
| `@compose(name, version, background=None, warrants=None, rationale="", label=None)` | Decorates a Python workflow and records its child actions as a reviewable Compose DAG |

`observe(...)`, `derive(...)`, `compute(...)`, and `infer(...)` return the affected conclusion/evidence claim. `associate(...)` and formal relation verbs return generated helper claims because the public semantic object is the declared relation. Scaffold verbs are recorded in `.gaia/formalization_manifest.json`; `candidate_relation(...)` does not create helper claims, strategies, operators, or BP factors. A `@compose` call returns the wrapped function's conclusion claim while also recording a Compose action in the compiled IR.

#### Relations

| Function | Semantics |
|----------|-----------|
| `equal(a, b)` | Reviewable claim that A and B have the same truth value |
| `contradict(a, b)` | Reviewable claim that A and B cannot both be true |
| `exclusive(a, b)` | Reviewable claim that exactly one of A and B is true |

Use `candidate_relation(claims=[...], pattern=None | "equal" | "contradict" | "exclusive")` when the relation is worth tracking but not ready to enter inference. Upgrade it to `equal(...)`, `contradict(...)`, `exclusive(...)`, or `associate(...)` only after the relation is formalized and reviewable as semantics; use `materialize(...)` to record the link.

#### Structural Proposition Helpers

| Function | Description |
|----------|-------------|
| `not_(a)` / `~a` | Boolean negation helper |
| `and_(a, b, ...)` / `a & b` | Boolean conjunction helper |
| `or_(a, b, ...)` | Boolean disjunction helper |

The infix shorthand forms are `~a`, `a & b`, and `a | b`.

Legacy and experimental strategy functions such as `support`, `deduction`, `abduction`, and `induction` are documented separately, but new v0.5 packages should prefer the action/relation surface above. If a step is uncertain, expose the uncertainty as an explicit premise or use `infer(...)`; do not hide it inside a prose rationale.

## Architecture

```
gaia/
├── lang/       DSL runtime, declarations, and compiler
├── ir/         Gaia IR schema, validation, formalization
├── bp/         Belief propagation engine (junction tree, TRW-BP, Mean Field VI)
├── cli/        CLI commands (init, compile, check, add, infer, render, starmap, inquiry, trace, register)
├── inquiry/    Semantic review loop — diagnostic kinds, focus/reject/obligation/hypothesis state
└── trace/      ARM execution-trace verifier and reviewer (schema + hash chain)
```

## Documentation

- [Plausible Reasoning Theory](docs/foundations/theory/01-plausible-reasoning.md) — Polya, Cox, Jaynes: why probability is the unique formalism
- [Language Reference](docs/for-users/language-reference.md)
- [Generated DSL API](docs/reference/dsl.md)
- [Package Model](docs/foundations/gaia-lang/package.md)
- [Knowledge & Reasoning Semantics](docs/foundations/gaia-lang/knowledge-and-reasoning.md)
- [CLI Workflow](docs/foundations/cli/workflow.md)
- [Gaia IR Specification](docs/foundations/gaia-ir/02-gaia-ir.md)
- [Registry Design](docs/specs/2026-04-02-gaia-registry-design.md)

## Testing

```bash
make test       # fast local slice; excludes slow regression snapshots and scale tests
make test-slow  # slow regression slice
make test-all   # full suite with coverage
```

## License

MIT
