# Hole And Bridge Tutorial

> **Status:** Current canonical

This is the smallest end-to-end workflow for Gaia's public-premise and bridge model:

1. Package A exports a conclusion.
2. Gaia automatically derives a `local_hole` from A's unresolved premise.
3. Package B declares `fills(...)` against that hole.
4. Both packages register into the registry.

This flow has been exercised against the official `SiliconEinstein/gaia-registry`.

## What Gaia Does Automatically

You do **not** mark holes manually.

Given an exported conclusion, Gaia computes its dependency closure during `gaia compile`:

- unresolved local claim premise -> `local_hole`
- unresolved foreign claim premise -> `foreign_dependency`

Those results are written into:

- `exports.json`
- `premises.json`
- `holes.json`
- `bridges.json`

`holes.json` is just the `local_hole` subset of `premises.json`.

## Package A: Produce A Hole

`pyproject.toml`:

```toml
[project]
name = "paper-a-gaia"
version = "1.0.0"
dependencies = [
  "gaia-lang>=0.1.0",
]

[tool.gaia]
namespace = "github"
type = "knowledge-package"
uuid = "11111111-1111-1111-1111-111111111111"
```

`src/paper_a/__init__.py`:

```python
from gaia.lang import claim, deduction

missing_lemma = claim("A missing lemma.")
main_theorem = claim("A theorem that depends on the missing lemma.")

deduction(
    premises=[missing_lemma],
    conclusion=main_theorem,
    reason="The theorem requires the missing lemma.",
)

__all__ = ["main_theorem"]
```

Compile and inspect:

```bash
gaia compile .
gaia check .
```

Expected result:

- `exports.json` contains `main_theorem`
- `premises.json` contains `missing_lemma` with `role = "local_hole"`
- `holes.json` contains the same `missing_lemma`

## Package B: Fill The Hole

Package B depends on package A.

`pyproject.toml`:

```toml
[project]
name = "paper-b-gaia"
version = "1.0.0"
dependencies = [
  "gaia-lang>=0.1.0",
  "paper-a-gaia>=1.0.0,<2.0.0",
]

[tool.gaia]
namespace = "github"
type = "knowledge-package"
uuid = "22222222-2222-2222-2222-222222222222"
```

`src/paper_b/__init__.py`:

```python
from gaia.lang import claim, fills
from paper_a import missing_lemma

bridge_result = claim("A result that establishes the missing lemma.")

fills(
    source=bridge_result,
    target=missing_lemma,
    reason="This result proves the lemma required by package A.",
)

__all__ = ["bridge_result"]
```

Compile and inspect:

```bash
gaia compile .
gaia check .
```

Expected result:

- `exports.json` contains `bridge_result`
- `bridges.json` contains one `fills` relation
- that relation points to:
  - A's `target_qid`
  - A's `target_interface_hash`
  - the resolved dependency version

## Important Constraint

`fills(target=...)` is validated against the dependency package's compiled manifests.

That means:

1. A must be compiled first.
2. B must resolve the same package that Gaia validates.
3. The target claim must appear in A's `premises.json`.
4. Its role must be `local_hole`.

If A's current release no longer exposes that premise as a hole, B's compile fails.

## Registration Order

Register package A first, then package B.

```bash
gaia register /path/to/paper-a
gaia register /path/to/paper-b
```

Why the order matters:

- B's bridge manifest records A's `target_resolved_version`
- registry validation checks B against A's registered release interface

## What To Look For In The Registry

After A is registered:

- `packages/paper-a/releases/1.0.0/premises.json`
- `packages/paper-a/releases/1.0.0/holes.json`

After B is registered:

- `packages/paper-b/releases/1.0.0/bridges.json`

After index build:

- `index/premises/by-qid/...`
- `index/holes/by-qid/...`
- `index/bridges/by-target-qid/...`
- `index/bridges/by-target-interface/...`

## Practical Notes

- Today, authors still write `from paper_a import missing_lemma` at the source level.
- Gaia does **not** trust that import by itself.
- During compile, Gaia re-validates the target against A's manifest interface.

So the stable contract is not "this symbol is forever a hole".
The stable contract is:

- this claim has a given `qid`
- in this release
- with this `interface_hash`
- and role `local_hole`

That is the object that `fills` really targets.
