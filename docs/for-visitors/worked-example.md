# Worked Example: Galileo's Falling Bodies

> **Status:** Current canonical

This walkthrough follows one real knowledge package from authoring to inference. The package captures Galileo's famous thought experiment: if heavier objects really fall faster, tying a heavy ball to a light ball produces a contradiction.

## The Paper

In 1638, Galileo published a thought experiment that dismantled nearly 2,000 years of accepted physics. Aristotle had taught that heavier objects fall faster. Galileo asked: what happens if you tie a heavy ball to a light ball?

- The light ball should drag the heavy one down, making the pair fall *slower* than the heavy ball alone.
- But the pair is heavier than the heavy ball alone, so it should fall *faster*.

Both conclusions follow from the same rule. They cannot both be true. Therefore the rule itself must be wrong.

## Step 1: Author the Package

A knowledge package is a set of files written in Gaia's structured language. Here are key excerpts from the Galileo package (translated from the original Chinese):

```typ
#setting[
  Imagine a heavy ball H and a light ball L dropped from the same height.
  First consider their individual "natural fall speeds," then consider
  what happens when they are tied together as a composite HL.
] <setting.thought_experiment_env>
```

This declares an experimental **setting** -- the scenario under discussion. It does not make any truth claim; it sets the stage.

```typ
#claim(from: (<aristotle.everyday_observation>,))[
  The speed of a falling object is proportional to its weight --
  heavier objects fall faster.
] <aristotle.heavier_falls_faster>
```

This declares a **claim** and says it is supported by a prior observation (`from:` names its evidence). The label `<aristotle.heavier_falls_faster>` lets other nodes reference it.

```typ
#relation(
  type: "contradiction",
  between: (<galileo.composite_is_slower>, <galileo.composite_is_faster>),
)[
  "HL is slower than H" and "HL is faster than H" are mutually exclusive.
] <galileo.tied_balls_contradiction>
```

This declares a **contradiction** between two claims. Both were derived from Aristotle's rule, but they cannot both be true.

## Step 2: Build the Knowledge Graph

Running `gaia build` compiles the package into a knowledge graph. Here is the structure that emerges:

```
  thought_experiment_env          vacuum_env
  (setting)                       (setting)
        |                             |
        v                             |
  everyday_observation                |
  (observation)                       |
        |                             |
        v                             |
  heavier_falls_faster --------+      |
  (claim)                      |      |
        |          |           |      |
        v          v           |      |
  composite_    composite_     |      |
  is_slower     is_faster      |      |
  (claim)       (claim)        |      |
        |           |          |      |
        +--- X -----+          |      |
        contradiction          |      |
             |                 |      |
             v                 v      v
        vacuum_prediction  <---+------+
        (claim: "all objects fall at the same rate in vacuum")
```

Each box is a knowledge node. Arrows are reasoning links. The **X** marks a contradiction: two claims derived from the same premise that cannot both be true.

## Step 3: Infer Beliefs

Running `gaia infer` executes belief propagation on the graph. The algorithm passes messages along every link until beliefs stabilize. Here is what happens:

| Node | Description | Prior | Belief |
|------|-------------|-------|--------|
| `thought_experiment_env` | The tied-ball scenario | 1.0 (setting) | 1.0 |
| `vacuum_env` | Idealized vacuum | 1.0 (setting) | 1.0 |
| `everyday_observation` | Stones fall faster than feathers | 0.5 | 0.5 |
| `heavier_falls_faster` | Aristotle's law | 0.5 | ~0.25 |
| `composite_is_slower` | HL is slower (drag argument) | 0.5 | ~0.35 |
| `composite_is_faster` | HL is faster (weight argument) | 0.5 | ~0.35 |
| `vacuum_prediction` | All objects fall equally in vacuum | 0.5 | ~0.65 |

What happened:

- **Settings stay at 1.0.** They are given facts about the scenario, not debatable claims.
- **Aristotle's law dropped.** The contradiction between its two consequences forced the system to lower trust in their shared premise.
- **Both contradicting claims dropped.** They cannot both be true, so belief propagation lowered both.
- **The vacuum prediction rose.** It is supported by the contradiction (which undermines the old law) and by observations about air resistance.

No human had to decide which claim wins. The structure of the reasoning determined the outcome.

## Step 4: Publish

Running `gaia publish` sends the package to the shared knowledge base. It now lives alongside packages from other papers, connected through shared claims and cross-references.

## What Happens Next

Suppose a later package introduces Newton's derivation: F = ma and F = mg imply a = g, meaning acceleration is independent of mass. This new package:

- Adds an independent theoretical path to the vacuum prediction, raising its belief further.
- Adds a second contradiction against Aristotle's law, driving its belief even lower.

Suppose yet another package records the Apollo 15 lunar experiment, where a hammer and a feather fell at the same rate on the Moon. Now three independent lines of evidence converge:

1. Galileo's thought experiment (logical contradiction)
2. Newton's derivation (theoretical proof)
3. Apollo 15 (direct experimental observation)

Belief propagation combines them all. Aristotle's law drops to near zero. The vacuum prediction rises to near one. The entire history of the scientific debate -- from ancient Greece to the surface of the Moon -- is captured in one connected graph, with every claim carrying a trust score that reflects the totality of the evidence.
