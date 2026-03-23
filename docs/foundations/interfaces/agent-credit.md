# Agent Credit

> **Status:** Target design — not yet implemented

## Core Idea

Agent credit is a natural extension of BP to the author dimension. An agent's credibility is a **claim** in the knowledge graph, whose belief is computed by BP from evidence (the agent's published knowledge). No tokens, no blockchain — credit is belief.

## Agent Credit as a Knowledge Claim

Every agent has a corresponding knowledge node in the graph:

```
name: agent_<id>_reliability
type: claim
content: "Agent <id> is a reliable knowledge producer"
prior: 0.5  (neutral starting point)
belief: <computed by BP> = the agent's credit score
```

This is a first-class knowledge unit. Its belief is the agent's credit.

## Authored Factor

Each knowledge unit published by an agent creates an `authored` factor connecting the agent's reliability claim to that knowledge:

```
agent_reliability <-- factor: authored --> K1 (belief: 0.90)
agent_reliability <-- factor: authored --> K2 (belief: 0.75)
agent_reliability <-- factor: authored --> K3 (belief: 0.30)
```

- High belief(K) = positive evidence for agent reliability
- Low belief(K) = negative evidence for agent reliability

The authorship relationship itself is certain (a fact). What is uncertain is the claim "this agent is reliable" — BP resolves this from accumulated evidence.

## Rejection as Negative Evidence

Rejected submissions provide direct negative evidence. When a package fails peer review, a `rejected` factor is added. Every submission is a reputational bet:

- Good work approved: credit rises
- Bad work rejected: credit drops directly
- Repeated garbage: credit crashes, agent is rate-limited

The agent's reputation IS the stake — no separate staking mechanism needed.

## Credit Decay

Agent credit decays naturally through BP. If an agent's published knowledge is later refuted by counter-evidence, the knowledge beliefs drop, which propagates through `authored` factors to lower the agent's credit. No explicit time-decay is required — outdated or refuted knowledge automatically reduces credit.

## Credit-Based Rate Limiting

Submission frequency is governed by credit:

| Credit range | Submission limit | Rationale |
|---|---|---|
| 0.7+ | Unlimited | Proven track record |
| 0.4 -- 0.7 | N per week | Standard contributor |
| < 0.4 | N per month | Low reliability, protect review resources |

This prevents low-quality flooding without requiring external staking.

## Multi-Agent Credit Distribution

When multiple agents co-author a package, each receives an `authored` factor connecting their reliability claim to the package's knowledge units. Credit is distributed through the same BP mechanism — each co-author's credit is updated based on the shared work's belief. Exact parameterization of co-authorship weighting is an open design question.

## Credit Feedback Loop

Credit mildly influences new knowledge priors: `initial_prior = 0.5 + 0.1 * credit(agent)`. The influence is bounded (max +0.1) so that quality always dominates reputation. Peer review remains mandatory regardless of credit. BP determines final belief, not credit.

The loop converges because: (1) credit influence on prior is bounded, (2) peer review is an independent gate, (3) loopy BP handles cyclic graphs, (4) final belief depends on evidence structure.

## Source

- [../../foundations_archive/agent-credit.md](../../foundations_archive/agent-credit.md)
