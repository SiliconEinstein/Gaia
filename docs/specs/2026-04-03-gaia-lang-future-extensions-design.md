# Gaia Lang Future Extensions Design

> **Status:** Target design after Phase 1 structural authoring
>
> **Companion current spec:** [2026-04-02-gaia-lang-v5-python-dsl-design.md](2026-04-02-gaia-lang-v5-python-dsl-design.md)
>
> **Depends on:** [Gaia IR v2](../foundations/gaia-ir/02-gaia-ir.md), [Parameterization](../foundations/gaia-ir/06-parameterization.md)

This document collects Gaia Lang features that are intentionally **not** part of the current Phase 1 author-side CLI contract.

Current Phase 1 stops at:

```text
author source
  -> gaia compile
  -> gaia check
  -> git push + git tag
  -> gaia register
```

The topics below remain future extensions.

## 1. Parameterization Layer

Probability values are independent from structural declarations. Authors declare structure; reviewers or downstream systems assign probabilities later.

### 1.1 Minimal Complete Set

A reviewer only needs to parameterize three categories:

| What | Record type | Why |
|------|-------------|-----|
| **Input claims** (not derived from any in-package strategy) | PriorRecord | Package entry assumptions need external judgment |
| **FormalStrategy auto-generated interface claims** | PriorRecord | Public interface claims carry independent uncertainty |
| **Parameterized strategies** (`noisy_and`, `infer`) | StrategyParamRecord | Reasoning strength lives on the support edge |

Not needed:

- external package claims, because they are parameterized by their own package lifecycle
- derived claims created by in-package support chains
- `setting` / `question`
- private helper claims created only to support a formal skeleton
- FormalStrategy objects themselves, because their behavior is derived from skeleton + interface priors

### 1.2 Parameterization API

```python
from gaia.lang.params import parameterize, source

with source(
    model="gpt-5-mini",
    reviewer="alice",
    policy="conservative",
) as src:
    parameterize(some_claim, prior=0.85)
    parameterize(some_strategy, p=0.9)
    parameterize(other_strategy, cpt=[...])
```

The `claim.strategy` convenience accessor is still part of this future design for the `claim(given=[...])` shorthand case.

### 1.3 CPT Tensor Interface

Strategy conditional probabilities vary by type:

| Strategy type | # premises | Parameter shape | Example |
|---|---|---|---|
| `noisy_and` | k | scalar `p` | `p=0.85` |
| `infer` | 1 | 2 values | `cpt=[0.1, 0.9]` |
| `infer` | 2 | 2×2 table | `cpt=[[0.01, 0.3], [0.4, 0.9]]` |
| `infer` | k | `2^k` values | full CPT tensor |

Accepted authoring formats:

- nested Python lists
- dicts keyed by boolean tuples
- numpy arrays for generated tensors

Internally these normalize to `StrategyParamRecord.conditional_probabilities`.

### 1.4 Constraints

- Values are clamped to `[epsilon, 1 - epsilon]`
- Only `claim` can receive a prior
- Only `noisy_and` and `infer` accept `StrategyParamRecord`
- FormalStrategies reject independent strategy parameters
- Helper claims reject independent priors

### 1.5 Example

```python
# .gaia/params/review_alice.py
from gaia.lang.params import parameterize, source
from galileo_falling_bodies import heavy_falls_faster, air_resistance

with source(model="gpt-5-mini", reviewer="alice", policy="conservative"):
    parameterize(heavy_falls_faster, prior=0.95)
    parameterize(air_resistance.strategy, p=0.8)
```

### 1.6 Resolution at Inference Time

When local or server-side inference returns, parameterization resolution may support:

- latest accepted records
- reviewer-specific filtering
- source-specific filtering
- registry-approved records only

## 2. Future Validation Surface

If parameterization becomes part of the CLI, additional checks should be activated:

- every input claim has a `PriorRecord`
- every `noisy_and` / `infer` strategy has a `StrategyParamRecord`
- every public FormalStrategy interface claim has a `PriorRecord`
- no private helper claim carries an independent `PriorRecord`
- all values fall inside the allowed range

## 3. Document Rendering

Rendering remains intentionally decoupled from structural compilation.

Target pipeline:

```text
.gaia/ir.json
  -> gaia render
  -> Typst / LaTeX / HTML / Markdown outputs
```

The renderer should consume IR JSON, not Python source. This keeps authoring, validation, and presentation separate.

## 4. Other Future Extension Points

Potential post-Phase-1 additions:

- local or server-side inference
- richer registry review gates
- review report ingestion
- LKM integration and cross-package relationship discovery
