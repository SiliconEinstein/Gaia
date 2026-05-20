# Gaia Lang

[![CI](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/SiliconEinstein/Gaia/actions/workflows/ci.yml)
[![Nightly](https://github.com/SiliconEinstein/Gaia/actions/workflows/nightly.yml/badge.svg?branch=main)](https://github.com/SiliconEinstein/Gaia/actions/workflows/nightly.yml)
[![Docs](https://github.com/SiliconEinstein/Gaia/actions/workflows/docs.yml/badge.svg?branch=main)](https://siliconeinstein.github.io/Gaia/)
[![PyPI alpha](https://img.shields.io/badge/pypi-0.5.0a1-orange)](https://pypi.org/project/gaia-lang/0.5.0a1/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> **Contributing?** Read [`AGENTS.md`](AGENTS.md).

Gaia is a Python DSL and CLI for plausible reasoning. It helps you, or your
agent, turn scientific arguments into explicit claims, reviewable reasoning
steps, and probabilistic belief updates.

The goal is practical: constrain an LLM agent with scientific logic until it can
act more like **Jaynes' Robot**. The agent must say what it assumes, expose how
claims depend on each other, and let probability theory compute what follows
from the declared information set.

## Version Status

`main` is the active v0.5 development trunk. The published v0.5 artifact is
currently the alpha preview `gaia-lang==0.5.0a1`; the source tree is tracking
the upcoming `0.5.0` line until the stable v0.5 release is cut.

- Use `gaia-lang==0.5.0a1` or `pip install --pre gaia-lang` if you want the
  current v0.5 alpha CLI, DSL, Bayes, and package workflow.
- The exact alpha source is the
  [`v0.5.0a1`](https://github.com/SiliconEinstein/Gaia/releases/tag/v0.5.0a1)
  tag at `803c0918`.
- Use `gaia-lang==0.4.4` and the [`release/0.4`](https://github.com/SiliconEinstein/Gaia/tree/release/0.4)
  branch if you need the stable v0.4.x line.
- v0.5 is breaking relative to v0.4; see the
  [v0.5.0a1 release notes](docs/releases/0.5.0a1.md) and
  [migration guide](docs/migration.md).
- New PRs should target `main`; exact prerelease sources are immutable tags
  such as `v0.5.0a1`.

| Channel | Install | Source |
|---------|---------|--------|
| v0.5 alpha | `pip install gaia-lang==0.5.0a1` | [`v0.5.0a1`](https://github.com/SiliconEinstein/Gaia/releases/tag/v0.5.0a1) |
| v0.5 nightly | install from `main` or use the nightly artifact | [`main`](https://github.com/SiliconEinstein/Gaia/tree/main) |
| v0.4 stable | `pip install gaia-lang==0.4.4` | [`release/0.4`](https://github.com/SiliconEinstein/Gaia/tree/release/0.4) |

## What Gaia Does

```text
Python DSL / CLI authoring
  -> gaia build compile
  -> Gaia IR + factor graph
  -> gaia run infer
  -> posterior beliefs and review artifacts
```

In v0.5, the recommended authoring style is deliberately small:

- write uncertain scientific statements as `claim(...)`;
- keep definitions, setups, and context as non-probabilistic `note(...)`;
- connect claims with `derive(...)`, `observe(...)`, `compute(...)`, and
  `infer(...)`;
- declare reviewable relations with `equal(...)`, `contradict(...)`,
  `exclusive(...)`, and `associate(...)`;
- assign external probabilities with `register_prior(...)` only when there is a
  real independent probabilistic input;
- leave unsupported independent inputs unset, so Gaia applies MaxEnt instead of
  pretending that a neutral `0.5` was a sourced prior.

Review status and probability are separate. Local inference shows what the
compiled graph currently implies numerically. Review and gate commands decide
whether the reasoning is publishable, auditable, or ready to register.

## Install

For the current v0.5 alpha:

```bash
pip install gaia-lang==0.5.0a1
```

Or, if you intentionally allow prereleases:

```bash
pip install --pre gaia-lang
```

For the stable v0.4.x line:

```bash
pip install gaia-lang==0.4.4
```

For development:

```bash
git clone https://github.com/SiliconEinstein/Gaia.git
cd Gaia
uv sync --extra dev
```

## Quick Start

```bash
gaia build init my-paper-gaia
cd my-paper-gaia

# Add claims and reasoning steps either by editing Python or through the CLI.
gaia author claim "The intervention changes the observable." \
  --dsl-binding-name intervention_changes_observable

gaia build compile .
gaia build check --hole .
gaia run infer .
```

For a full walkthrough, see [`docs/for-users/quick-start.md`](docs/for-users/quick-start.md).

## Minimal DSL Example

```python
from gaia.engine.lang import claim, contradict, derive, equal, note, register_prior

setup = note("A heavy body and a light body are tied together.")

daily_observation = claim("In air, heavy bodies often fall faster than light bodies.")
aristotle_model = claim("Weight itself causes greater natural falling speed.")
medium_model = claim("In-air speed differences are caused by medium resistance.")

register_prior(
    daily_observation,
    0.9,
    justification="Everyday in-air observations make this background likely.",
)

aristotle_daily = derive(
    "Under the weight-speed model, heavy bodies should fall faster in air.",
    given=[aristotle_model],
)
equal(aristotle_daily, daily_observation)

medium_daily = derive(
    "Under the medium-resistance model, heavy bodies can fall faster in air.",
    given=[medium_model],
)
equal(medium_daily, daily_observation)

composite_faster = derive(
    "The tied composite should fall faster than the heavy body alone.",
    given=[aristotle_model],
    background=[setup],
)
composite_slower = derive(
    "The tied composite should fall slower than the heavy body alone.",
    given=[aristotle_model],
    background=[setup],
)
contradict(composite_faster, composite_slower)

vacuum_equal_fall_prediction = derive(
    "In vacuum, bodies of different weights fall at the same rate.",
    given=[medium_model],
)
```

The runnable package lives in
[`examples/galileo-v0-5-gaia`](examples/galileo-v0-5-gaia).

## Where the Probabilities Come From

Run the Galileo example:

```bash
gaia build compile examples/galileo-v0-5-gaia
gaia run infer examples/galileo-v0-5-gaia
```

The compiled reasoning graph has three paths: both candidate models can explain
the daily in-air observation, but only the Aristotelian weight-speed model also
creates the tied-body contradiction.

```mermaid
flowchart TD
    subgraph inputs["Starting claims"]
        direction LR
        daily["Heavy faster in air<br/>0.900 -> 0.964"]:::premise
        aristotle["Weight-speed model<br/>0.500 -> 0.010"]:::premise
        medium["Medium-resistance model<br/>0.500 -> 0.642"]:::premise
    end

    subgraph daily_paths["1. Daily check"]
        direction LR
        derive_a_daily(["derive"]):::strategy
        a_pred["weight-speed predicts:<br/>heavy faster in air<br/>0.963"]:::derived
        equal_a{{"equal<br/>0.999"}}:::relation_op

        derive_m_daily(["derive"]):::strategy
        m_pred["medium-resistance predicts:<br/>heavy faster in air<br/>0.964"]:::derived
        equal_m{{"equal<br/>1.000"}}:::relation_op
    end

    subgraph contradiction_path["2. Tied-body contradiction"]
        direction LR
        derive_fast(["derive"]):::strategy
        faster["tied composite faster<br/>than heavy body<br/>0.338"]:::derived
        derive_slow(["derive"]):::strategy
        slower["tied composite slower<br/>than heavy body<br/>0.338"]:::derived
        contra{{"contradict<br/>0.997"}}:::contra
    end

    subgraph vacuum_path["3. Vacuum prediction"]
        direction LR
        derive_vacuum(["derive"]):::strategy
        vacuum["equal fall in vacuum<br/>0.821"]:::derived
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

Current local inference on `main` / the v0.5 line gives:

| Claim | Starting information | Local posterior belief |
|-------|----------------------|-----------------------:|
| `daily_observation` | `register_prior(..., 0.9)` from `priors.py` | 0.964 |
| `aristotle_model` | independent input with no external prior, so MaxEnt starts it at 0.5 | 0.010 |
| `medium_model` | independent input with no external prior, so MaxEnt starts it at 0.5 | 0.642 |
| `vacuum_equal_fall_prediction` | derived claim, no independent prior | 0.821 |

Those posteriors are not hand-written. Gaia lowers the compiled package into a
factor graph:

- `register_prior(...)` writes auditable prior records. The resolver chooses the
  winning record and stores it in claim metadata before inference.
- An independent claim with no prior record gets the MaxEnt neutral baseline
  rather than a fake author prior.
- `derive(...)` lowers to a Jaynes-style conditional implication. If the premise
  is true, the conclusion is true up to the Cromwell bound; if the premise is
  false, the derivation contributes no information and falls back to the
  conclusion's base rate, usually MaxEnt.
- `equal(...)` and `contradict(...)` assert deterministic relation factors. In
  the Galileo graph, both models explain the daily observation, but the
  Aristotelian model also implies two tied-body predictions that cannot both be
  true. Inference therefore strongly suppresses that model.
- The final numbers are posterior marginals computed by `gaia run infer`; for
  this small graph Gaia uses exact Junction Tree inference.

## v0.5 Authoring Surface

| Layer | Python DSL | CLI |
|-------|------------|-----|
| Knowledge | `claim`, `note`, `question` | `gaia author claim/note/question` |
| Reasoning actions | `derive`, `observe`, `compute`, `infer` | `gaia author derive/observe/compute/infer` |
| Relations | `equal`, `contradict`, `exclusive`, `associate`, `decompose` | `gaia author equal/contradict/exclusive/associate/decompose` |
| Scaffolds | `depends_on`, `candidate_relation`, `materialize` | `gaia author depends-on/candidate-relation/materialize` |
| Composition | `compose`, `composition` | `gaia author compose/composition` |
| Priors | `register_prior` | `gaia author register-prior` |
| Typed terms | `Variable`, `Nat`, `Real`, `Probability`, `Bool` | `gaia author variable` |
| Continuous quantities | `Normal`, `LogNormal`, `Beta`, `Gamma`, `StudentT`, `Cauchy`, `ChiSquared`, `Binomial`, `Poisson` | `gaia bayes <distribution>` for CLI-authored Bayes snippets |
| Bayesian model comparisons | `gaia.engine.bayes.model`, `data`, `compare` | `gaia bayes model/compare` |

Old v5 names remain available only through the compatibility layer. New packages
should use the v0.5 surface above.

## CLI Map

The CLI is self-documenting. Use `gaia --help`, `gaia <group> --help`, and
`gaia <group> <verb> --help` as the command-surface authority.

| Group | Verbs | Purpose |
|-------|-------|---------|
| `gaia build` | `init`, `compile`, `check` | Create packages, compile Python DSL to Gaia IR, and validate structure/prior holes/gates. |
| `gaia author` | `claim`, `note`, `question`, `derive`, `observe`, `compute`, `infer`, `equal`, `contradict`, `exclusive`, `associate`, `decompose`, `parameter`, `register-prior`, `variable`, `depends-on`, `candidate-relation`, `materialize`, `compose`, `composition` | Agent-first authoring commands that append checked DSL statements to package source files. |
| `gaia bayes` | `model`, `compare`, `binomial`, `beta-binomial`, `poisson`, `normal`, `log-normal`, `beta`, `exponential`, `gamma`, `student-t`, `cauchy`, `chi-squared` | CLI helpers for Bayesian model comparison declarations and distribution literals. |
| `gaia pkg` | `add`, `add-import`, `add-module`, `register`, `scaffold` | Manage package dependencies, sibling modules, scaffolds, and registry publication. |
| `gaia run` | `infer`, `render` | Compute local posterior beliefs and render package outputs. |
| `gaia inspect` | `starmap`, `starmap-replay` | Inspect compiled graph visualizations and replay artifacts. |
| `gaia inquiry` | `focus`, `review`, `obligation`, `hypothesis`, `tactics`, `reject` | Run the semantic inquiry and review loop over a compiled package. |
| `gaia trace` | `verify`, `review`, `show` | Verify and review ARM execution traces. |
| `gaia review` | skeleton only | Reserved top-level home for future reviewer tooling; do not confuse it with `gaia inquiry review` or `gaia trace review`. |
| `gaia search` | `lkm auth`, `lkm claims`, `lkm reasoning`, `lkm reasoning-search`, `lkm variables`, `lkm paper-graph` | Query an external retrieval backend; the `lkm` backend wraps the Bohrium LKM knowledge-graph search API. |

The Bohrium LKM knowledge-graph search backend is available under `gaia search lkm`; run `gaia search lkm auth login` to set up your access key (or set `GAIA_LKM_ACCESS_KEY` / `LKM_ACCESS_KEY`), then `gaia search lkm --help` for the full verb surface.

The authoring CLI is intentionally conservative: target files must already
exist, sibling files should be created with `gaia pkg add-module`, and literal
`__all__` blocks are updated only when the verb is meant to export the new
binding.

## Examples

| Example | Demonstrates | Try it |
|---------|--------------|--------|
| [`examples/galileo-v0-5-gaia`](examples/galileo-v0-5-gaia) | Competing model hypotheses, daily evidence, contradiction, derived counterfactual prediction | `gaia build compile examples/galileo-v0-5-gaia && gaia run infer examples/galileo-v0-5-gaia` |
| [`examples/mendel-v0-5-gaia`](examples/mendel-v0-5-gaia) | CLI-authored probability example with priors, relations, and generated source files | `gaia build compile examples/mendel-v0-5-gaia` |

## Documentation

Start with [`docs/README.md`](docs/README.md). Common entry points:

- [`docs/for-visitors/what-is-gaia.md`](docs/for-visitors/what-is-gaia.md) - conceptual overview.
- [`docs/for-users/quick-start.md`](docs/for-users/quick-start.md) - first package walkthrough.
- [`docs/for-users/language-reference.md`](docs/for-users/language-reference.md) - practical v0.5 DSL cheat sheet and language reference.
- [`docs/for-users/cli-commands.md`](docs/for-users/cli-commands.md) - workflow-oriented CLI guide and command map.
- [`docs/reference/cli/index.md`](docs/reference/cli/index.md) - generated CLI reference.
- [`docs/reference/engine/lang/dsl.md`](docs/reference/engine/lang/dsl.md) - generated DSL API reference.
- [`docs/reference/engine/bayes.md`](docs/reference/engine/bayes.md) - generated Bayes API reference.
- [`docs/foundations/gaia-ir/02-gaia-ir.md`](docs/foundations/gaia-ir/02-gaia-ir.md) - IR contract.
- [`docs/specs/2026-04-02-gaia-registry-design.md`](docs/specs/2026-04-02-gaia-registry-design.md) - registry design.

## Architecture

```text
gaia/
  engine/
    lang/       Python DSL runtime, compiler, formulas, roles, review manifest
    bayes/      Bayesian model comparison helpers
    packaging   Package loading, compile/register interfaces
    bp/         Factor graph lowering and inference
    inquiry/    Semantic review loop
    trace/      ARM trace verification and review
    ir/         Persistent Gaia IR schemas and validation
  cli/          Typer command groups for authoring, build, run, review, and registry workflows
```

## Development

```bash
make test       # fast local slice; excludes slow tests
make test-slow  # slow regression slice
make test-all   # full pytest suite
make docs-build # strict MkDocs build
```

## License

MIT
