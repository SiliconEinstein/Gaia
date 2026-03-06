# Galileo's Tied Balls: Overturning Aristotle with a Thought Experiment

## Overview

Galileo's 1638 *Discorsi e dimostrazioni matematiche intorno a due nuove scienze* contains one of history's most elegant thought experiments. By imagining tying a heavy and light ball together, he showed that Aristotle's "heavier falls faster" law leads to a self-contradiction: the combined object must simultaneously fall faster (because it is heavier) and slower (because the light ball drags the heavy one). No laboratory was needed -- pure reasoning exposed a flaw that had survived nearly two millennia.

This example demonstrates how Gaia models the accumulation of evidence against an established theory. Six knowledge packages, spanning from Aristotle's *Physics* (c. 350 BCE) to the Apollo 15 lunar experiment (1971 CE), are committed to the graph in chronological order. Belief propagation automatically tracks how the credibility of Aristotle's law erodes as contradictions, alternative theories, and direct experimental confirmation enter the hypergraph.

---

## Package 1: Prior Knowledge Graph (`aristotle_physics`)

The starting state of the graph represents pre-Galilean accepted wisdom. Aristotle's doctrine of natural motion and everyday empirical observation combine to support a proportionality law: heavier objects fall faster.

### Nodes

| ID | Type | Subtype | Content | Prior |
|----|------|---------|---------|-------|
| 5001 | paper-extract | premise | Aristotle's doctrine of natural motion: every body has a natural place; earthy bodies move downward with a speed determined by their nature (weight). | 0.9 |
| 5002 | paper-extract | premise | Empirical observation: a stone dropped alongside a leaf reaches the ground first. Heavier objects appear to fall faster in everyday experience. | 0.95 |
| 5003 | paper-extract | conclusion | Aristotle's law of falling bodies: the speed of a falling body is proportional to its weight (v proportional to W). Heavier objects fall faster than lighter ones. | 0.7 |

### Edges

| ID | Type | Tail | Head | Probability | Reasoning |
|----|------|------|------|-------------|-----------|
| 5001 | abstraction | [5001, 5002] | [5003] | 0.85 | Aristotle generalizes from the doctrine of natural motion (node 5001) and the everyday observation that stones fall faster than leaves (node 5002) to the universal law that speed of fall is proportional to weight (node 5003). |

### After propagation

Node 5003 (Aristotle's law) receives belief approximately 0.70, reflecting its status as widely accepted but imprecise ancient wisdom. The prior is deliberately set below 1.0 because even within the Aristotelian tradition, the proportionality claim was debated.

---

## Package 2: The Tied Balls Paradox (`galileo1638_tied_balls`)

This is the heart of Galileo's thought experiment. Starting from Aristotle's own premises, Galileo constructs two valid deductive chains that arrive at contradictory conclusions about the same physical setup. The contradiction proves that the shared premise -- Aristotle's law -- must be false.

### Setup

Imagine tying a heavy ball H to a light ball L with a cord. Now drop the combined object HL.

### Nodes

| ID | Type | Subtype | Content | Prior |
|----|------|---------|---------|-------|
| 5004 | conjecture | premise | Setup: Tie a heavy ball H (weight W_H) to a light ball L (weight W_L < W_H) with a cord. Consider the combined object HL. | 0.99 |
| 5005 | deduction | conclusion | Deduction A: By Aristotle's law, L falls slower than H. When tied together, L acts as a drag on H, retarding its natural motion. Therefore the combined object HL must fall slower than H alone. | 0.9 |
| 5006 | deduction | conclusion | Deduction B: The combined object HL has total weight W_H + W_L, which is greater than W_H. By Aristotle's law, a heavier body falls faster. Therefore HL must fall faster than H alone. | 0.9 |
| 5007 | deduction | conclusion | Contradiction: Deductions A and B both follow validly from Aristotle's law applied to the same setup. Yet they yield mutually exclusive predictions -- the combined object HL cannot be both faster and slower than H alone. Therefore Aristotle's law is internally self-contradictory. | 0.95 |
| 5008 | deduction | conclusion | Galileo's conclusion: since Aristotle's law (v proportional to W) leads to a self-contradiction when applied to composite bodies, the law must be rejected. Speed of fall cannot depend on weight in the way Aristotle claimed. | 0.85 |

### Edges

| ID | Type | Tail | Head | Probability | Reasoning |
|----|------|------|------|-------------|-----------|
| 5002 | deduction | [5003, 5004] | [5005] | 0.95 | From Aristotle's law (node 5003) and the setup (node 5004): L is lighter than H, so L falls slower. When tied together, L drags on H. Therefore the composite HL is slower than H alone. |
| 5003 | deduction | [5003, 5004] | [5006] | 0.95 | From Aristotle's law (node 5003) and the setup (node 5004): HL has combined weight W_H + W_L > W_H. By the same law, heavier falls faster. Therefore HL is faster than H alone. |
| 5004 | contradiction | [5005, 5006] | [] | null | Nodes 5005 and 5006 make mutually exclusive claims about the same object under the same conditions. The combined object HL cannot be simultaneously faster and slower than H alone. This is a logical contradiction. |
| 5005 | deduction | [5007, 5003] | [5008] | 0.90 | The contradiction (node 5007) arises from valid deductions that share a single premise: Aristotle's law (node 5003). Since the deductions are logically valid, the error must lie in the premise. Therefore Aristotle's law is self-contradictory and must be rejected (node 5008). |

### After propagation

The contradiction edge (5004) connecting nodes 5005 and 5006 is the critical structure. Belief propagation recognizes that these two nodes cannot both be true. Since both are validly derived from the same premise -- Aristotle's law (node 5003) -- BP propagates the inconsistency back to the shared source. The belief in node 5003 drops to roughly 0.20--0.50, depending on edge probabilities and the BP schedule. Meanwhile, node 5008 (Galileo's rejection of Aristotle) rises to approximately 0.75--0.85.

This is the key mechanism: **contradiction edges drive belief revision in shared premises**.

---

## Package 3: Medium Density (`galileo1638_medium_density`)

Galileo did not stop at the thought experiment. He also observed that the medium through which objects fall affects their speed, providing a physical explanation for why Aristotle's everyday observations seemed plausible.

### Nodes

| ID | Type | Subtype | Content | Prior |
|----|------|---------|---------|-------|
| 5009 | paper-extract | premise | Galileo's observation: objects of different densities fall at noticeably different rates in water and viscous media, but the difference diminishes in thinner media such as air. | 0.9 |
| 5010 | paper-extract | premise | As the density of the medium decreases, the difference in fall rates between heavy and light objects decreases proportionally. | 0.85 |
| 5011 | deduction | conclusion | Air resistance is a confounding variable: Aristotle's observation (stones fall faster than leaves) is explained by differing air resistance, not by differing intrinsic fall speeds. The medium, not the weight, produces the apparent speed difference. | 0.8 |

### Edges

| ID | Type | Tail | Head | Probability | Reasoning |
|----|------|------|------|-------------|-----------|
| 5006 | deduction | [5009, 5010] | [5011] | 0.85 | Galileo reasons by extrapolation: if the difference in fall rates diminishes as the medium becomes thinner, then in the limiting case of no medium (vacuum), the difference would vanish entirely. Therefore the observed difference in air is due to the medium, not to any intrinsic property of weight. |

### After propagation

Node 5011 (air resistance as confounding variable) achieves belief approximately 0.75. This provides an alternative explanation for node 5002 (the empirical observation that stones fall faster than leaves), undermining the evidential support that node 5002 previously gave to Aristotle's law (node 5003). The belief in node 5003 drops further.

---

## Package 4: Vacuum Prediction (`galileo1638_vacuum_prediction`)

Galileo makes a testable prediction: in a vacuum, all objects fall at the same rate regardless of weight. He also provides partial experimental confirmation through inclined plane experiments.

### Nodes

| ID | Type | Subtype | Content | Prior |
|----|------|---------|---------|-------|
| 5012 | conjecture | conclusion | Prediction: in a true vacuum (zero air resistance), all objects fall at the same rate regardless of their weight. | 0.85 |
| 5013 | paper-extract | premise | Inclined plane experiments: Galileo measured that balls of different weights rolling down smooth inclined planes arrive at the bottom at nearly the same time, and that the distance traveled is proportional to the square of the elapsed time. | 0.9 |
| 5014 | deduction | conclusion | The inclined plane results are consistent with the equal-fall-rate hypothesis and inconsistent with v proportional to W, providing partial experimental support for the vacuum prediction (node 5012). | 0.8 |

### Edges

| ID | Type | Tail | Head | Probability | Reasoning |
|----|------|------|------|-------------|-----------|
| 5007 | deduction | [5008, 5011] | [5012] | 0.85 | If Aristotle's law is wrong (node 5008) and the observed difference is due to the medium (node 5011), then removing the medium should remove the difference: all objects would fall equally in a vacuum. |
| 5008 | deduction | [5013, 5012] | [5014] | 0.80 | The inclined plane results (node 5013) match the prediction that fall rate does not depend on weight (node 5012). Friction on the plane acts as a reduced analog of air resistance, and the near-equal arrival times support equal-rate falling. |

### After propagation

The inclined plane evidence (node 5013) strengthens belief in the vacuum prediction (node 5012) to approximately 0.85. Node 5003 (Aristotle's law) continues its decline as more evidence accumulates against it.

---

## Package 5: Newton's Principia (`newton1687_principia`)

Nearly fifty years after Galileo's *Discorsi*, Newton's *Principia Mathematica* (1687) provides a theoretical derivation from first principles that independently confirms Galileo's conclusion and directly contradicts Aristotle's law.

### Nodes

| ID | Type | Subtype | Content | Prior |
|----|------|---------|---------|-------|
| 5015 | paper-extract | premise | Newton's Second Law: F = ma. The net force on a body equals its mass times its acceleration. | 0.95 |
| 5016 | paper-extract | premise | Newton's Law of Gravitation (near Earth's surface): the gravitational force on a body is F = mg, where g is the gravitational acceleration constant (approximately 9.8 m/s^2) and m is the body's mass. | 0.95 |
| 5017 | deduction | conclusion | Derivation: setting F = ma equal to F = mg yields a = g. The acceleration due to gravity is independent of mass. All objects in free fall experience the same acceleration regardless of their weight. | 0.95 |

### Edges

| ID | Type | Tail | Head | Probability | Reasoning |
|----|------|------|------|-------------|-----------|
| 5009 | deduction | [5015, 5016] | [5017] | 0.95 | From F = ma and F = mg, dividing both sides by m gives a = g. The mass cancels, so acceleration is independent of mass. This is a straightforward algebraic derivation from Newton's two laws. |
| 5010 | deduction | [5017] | [5012] | 0.95 | If a = g for all objects regardless of mass (node 5017), then in a vacuum (no air resistance), all objects fall at the same rate. This independently confirms Galileo's vacuum prediction (node 5012). |
| 5011 | contradiction | [5003, 5017] | [] | null | Newton's result a = g (acceleration independent of mass, node 5017) directly contradicts Aristotle's law v proportional to W (speed proportional to weight, node 5003). If acceleration is the same for all masses, then speed of fall cannot be proportional to weight. |

### After propagation

Edge 5011 is a contradiction edge linking Newton's derivation (node 5017, high prior 0.95) against Aristotle's law (node 5003, already weakened). This provides a second independent line of attack on Aristotle's law, further driving its belief down. Node 5017 achieves belief approximately 0.90--0.95. Node 5003 drops to roughly 0.05--0.15. The Newtonian derivation also strengthens the vacuum prediction (node 5012) via edge 5010, since it provides a theoretical basis that is independent of Galileo's thought experiment.

---

## Package 6: Apollo 15 (`apollo15_1971_feather_drop`)

On August 2, 1971, astronaut David Scott performed the famous hammer-feather drop on the surface of the Moon during the Apollo 15 mission. In the near-perfect vacuum of the lunar surface, a hammer and a falcon feather were dropped simultaneously and hit the ground at the same time. This was the first direct experimental confirmation of the equal-fall-rate hypothesis in an actual vacuum.

### Nodes

| ID | Type | Subtype | Content | Prior |
|----|------|---------|---------|-------|
| 5018 | paper-extract | premise | Apollo 15 experiment conditions: the lunar surface has negligible atmosphere (approximately 3 x 10^-15 atm), providing a near-perfect vacuum environment for free-fall experiments. | 0.99 |
| 5019 | paper-extract | premise | Observation: astronaut David Scott simultaneously released a 1.32 kg geological hammer and a 0.03 kg falcon feather from the same height. Both objects struck the lunar surface at the same time, as recorded on live television. | 0.99 |
| 5020 | deduction | conclusion | The Apollo 15 hammer-feather experiment directly confirms that objects of vastly different masses (factor of 44x) fall at the same rate in a vacuum, consistent with Galileo's prediction (node 5012) and Newton's derivation (node 5017). | 0.99 |

### Edges

| ID | Type | Tail | Head | Probability | Reasoning |
|----|------|------|------|-------------|-----------|
| 5012 | deduction | [5018, 5019] | [5020] | 0.99 | In a near-perfect vacuum (node 5018), a heavy hammer and a light feather fell at the same rate (node 5019). This directly confirms the equal-fall-rate prediction. The mass ratio of 44:1 makes the result decisive -- under Aristotle's law, the hammer should have fallen 44 times faster. |
| 5013 | deduction | [5020] | [5012] | 0.99 | The lunar observation (node 5020) provides direct experimental evidence for the vacuum prediction (node 5012), elevating it from theoretical prediction to observed fact. |
| 5014 | deduction | [5020] | [5017] | 0.95 | The lunar observation (node 5020) is consistent with a = g independent of mass (node 5017), providing direct empirical support for the Newtonian derivation. |

### After propagation

Three independent lines of evidence now converge on the same conclusion:

1. **Galileo's thought experiment** (Package 2) -- logical contradiction in Aristotle's premises
2. **Newtonian theory** (Package 5) -- theoretical derivation from first principles (a = g)
3. **Apollo 15 observation** (Package 6) -- direct experimental confirmation in actual vacuum

Each line is independent: the thought experiment requires no empirical data, the Newtonian derivation depends only on F = ma and F = mg, and the lunar observation is a direct measurement. BP naturally assigns high belief to nodes supported by multiple independent paths and low belief to nodes contradicted by them.

---

## Final Belief Distribution

After all six packages have been committed and belief propagation has converged, the graph shows the following approximate belief distribution:

| Node | Description | Initial Prior | Final Belief Range |
|------|-------------|---------------|--------------------|
| 5003 | Aristotle's law (v proportional to W) | 0.70 | 0.01--0.15 |
| 5005 | Deduction A: combined is slower | 0.90 | 0.20--0.40 |
| 5006 | Deduction B: combined is faster | 0.90 | 0.20--0.40 |
| 5007 | Contradiction in Aristotle's law | 0.95 | 0.85--0.95 |
| 5008 | Galileo's rejection of Aristotle | 0.85 | 0.85--0.95 |
| 5011 | Air resistance as confound | 0.80 | 0.80--0.90 |
| 5012 | Equal fall rate in vacuum | 0.85 | 0.85--1.00 |
| 5014 | Inclined plane confirmation | 0.80 | 0.80--0.90 |
| 5017 | a = g (Newton) | 0.95 | 0.85--1.00 |
| 5020 | Lunar experiment confirmed | 0.99 | 0.90--1.00 |

The most striking feature is the collapse of node 5003 from prior 0.70 to final belief 0.01--0.15. This occurs through the cumulative effect of:

- One contradiction edge within Aristotle's own framework (edge 5004)
- One cross-paradigm contradiction edge from Newtonian mechanics (edge 5011)
- Multiple independent evidence paths supporting the alternative (edges 5007, 5010, 5013, 5014)

Nodes 5005 and 5006 also drop in belief despite being individually valid deductions, because they are linked by a contradiction edge (5004). BP cannot assign high belief to both simultaneously, so it finds the equilibrium by lowering both and propagating the inconsistency back to the shared premise.

---

## Key Takeaways

1. **Thought experiments as nodes and edges.** No special "environment" construct is needed. Galileo's thought experiment is simply new nodes (premises and deductions) and edges (reasoning steps) added to the graph. The setup (node 5004) is a conjecture node; the deductions (nodes 5005, 5006) follow via standard deduction edges; the contradiction (node 5007) is identified by a contradiction edge. The entire argument lives in the same node/edge vocabulary as any empirical observation or theoretical derivation.

2. **Contradiction drives belief revision.** The contradiction edge (5004) between nodes 5005 and 5006 is the structural engine of belief revision. BP detects that these two nodes cannot both be true, and since they share a common premise (Aristotle's law, node 5003), the inconsistency propagates backward to lower belief in that premise. This is precisely how scientific revolutions work: internal contradictions in a theory precede its replacement.

3. **Multiple independent evidence streams converge.** The thought experiment (Package 2), medium-density observations (Package 3), Newtonian theory (Package 5), and lunar experiment (Package 6) are independent paths that all point to the same conclusion. BP naturally assigns higher belief to conclusions supported by multiple independent paths, because the probability of all paths being wrong simultaneously is very low. No special "convergence" logic is needed -- it emerges from the graph topology.

4. **Old theories are not deleted.** Aristotle's law (node 5003) remains in the graph with low belief, preserving the historical record of scientific reasoning. The graph captures not just what we know, but how we came to know it. A future query for "why was Aristotle wrong about falling bodies?" can trace the full chain from node 5003 through the contradiction edges and converging evidence to the current consensus. This is a fundamental advantage over knowledge bases that delete or overwrite superseded theories.

5. **Packages as commit batches.** Each package corresponds to a historical moment when new knowledge entered the graph. This ordering shows how scientific understanding evolved over two millennia: from Aristotle's initial codification of everyday observation (c. 350 BCE), through Galileo's devastating thought experiment and empirical program (1638 CE), to Newton's theoretical unification (1687 CE), and finally to the direct experimental confirmation on the Moon (1971 CE). The commit history *is* the history of science.
