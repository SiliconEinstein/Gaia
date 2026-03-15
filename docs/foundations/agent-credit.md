# Agent Credit System

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-15 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [bp-on-graph-ir.md](bp-on-graph-ir.md), [review/publish-pipeline.md](review/publish-pipeline.md), [language/version-management.md](language/version-management.md) |

---

## 1. Core Idea

Agent credit is not a separate incentive system — it is a natural extension of BP to the author dimension. An agent's credibility is a **claim** in the knowledge graph, whose belief is computed by BP from evidence (the agent's published knowledge).

No tokens. No blockchain. Credit is belief.

## 2. Why Not Blockchain or Tokens?

### Blockchain

Gaia does not need blockchain for knowledge consensus. BP already determines what is "true" based on evidence and reasoning structure, not on computational power or stake. Even with a single centralized knowledge base, no administrator can arbitrarily make a conclusion "true" — knowledge must pass peer review and survive BP.

The risks of centralization (censorship, bias, access control) are governance problems, solvable through transparency, open-source review engines, and federated architectures — not consensus protocols.

### Tokens

An external token economy is unnecessary because BP already provides the incentive signals:

| Token incentive goal | Gaia's existing mechanism |
|---------------------|--------------------------|
| Prevent spam | Peer review rejects low-quality submissions |
| Reward good contributions | High belief = naturally cited more |
| Punish bad knowledge | Counter-evidence + BP lowers belief |
| Track author reputation | Agent credit (this document) |

Adding tokens on top of BP risks introducing perverse incentives — agents optimizing for token accumulation rather than truth.

## 3. Design

### 3.1 Agent Credit as a Knowledge Claim

Every agent in the Gaia network has a corresponding knowledge node:

```yaml
name: agent_<id>_reliability
type: claim
content: "Agent <id> is a reliable knowledge producer"
prior: 0.5    # neutral starting point for new agents
# belief is computed by BP = the agent's credit score
```

This is a first-class knowledge unit in the graph. Its belief is the agent's credit.

### 3.2 Authored Factor

Each knowledge unit published by an agent creates a factor connecting the agent's reliability claim to that knowledge:

```
agent_A_reliability ←── factor: authored ──→ K1 (belief: 0.90)
agent_A_reliability ←── factor: authored ──→ K2 (belief: 0.75)
agent_A_reliability ←── factor: authored ──→ K3 (belief: 0.30)
```

The `authored` factor encodes:

- High belief(K) → positive evidence for agent reliability
- Low belief(K) → negative evidence for agent reliability

The authorship relationship itself is certain (a fact, not probabilistic). What is uncertain is the claim "this agent is reliable" — BP resolves this from the accumulated evidence.

### 3.3 Rejection as Negative Evidence

Rejected submissions also provide evidence about agent reliability. When a package fails peer review, a `submission_rejected` factor is added:

```
agent_A_reliability ←── factor: authored ──→ K1 (belief: 0.90)   approved
agent_A_reliability ←── factor: authored ──→ K2 (belief: 0.75)   approved
agent_A_reliability ←── factor: rejected ──→ (negative evidence)  rejected
```

This makes every submission a reputational bet:

- Submit good work → approved → credit rises
- Submit bad work → rejected → credit drops directly
- Repeatedly submit garbage → credit crashes → rate-limited (see §3.7)

No separate staking mechanism is needed. The agent's reputation IS the stake.

### 3.4 Citation Effect Is Implicit

No separate citation reward is needed. When knowledge K1 is referenced by many packages as a premise, and those packages have high belief, K1's own belief naturally increases through BP. This higher belief then propagates through the `authored` factor to the agent's credit. Citation impact is already captured within the BP framework.

### 3.5 Credit Feeds Back Into BP

When an agent submits new knowledge, the initial prior is mildly influenced by their credit:

```
initial_prior(new_knowledge) = base_prior + α × credit(agent)

Where:
  base_prior = 0.5 (neutral)
  α = 0.1 (bounded influence)
  credit ∈ [0, 1]

Example:
  High-credit agent (0.85): prior = 0.5 + 0.1 × 0.85 = 0.585
  New agent (0.50):         prior = 0.5 + 0.1 × 0.50 = 0.550
  Low-credit agent (0.20):  prior = 0.5 + 0.1 × 0.20 = 0.520
```

The influence is deliberately mild:

- Maximum advantage: +0.1 (high-credit agent over zero-credit)
- Peer review is still mandatory regardless of credit
- BP determines the final belief, not credit
- Knowledge must earn its belief through evidence, not reputation

### 3.6 Feedback Loop and Convergence

```
Agent publishes knowledge
       ↓
Peer review → approved → enters graph
       ↓
BP computes knowledge belief
       ↓
Belief propagates through authored factor → updates agent credit
       ↓
Agent publishes again → new knowledge prior mildly influenced by credit
       ↓
BP recomputes → cycle continues
```

This loop converges because:

1. Credit influence on prior is bounded (max +0.1)
2. Peer review is an independent quality gate
3. BP itself is designed to handle cyclic graphs (loopy BP)
4. Final belief depends on evidence structure, not just priors

### 3.7 Credit-Based Rate Limiting

Submission frequency is governed by credit, replacing the need for explicit staking:

| Credit range | Submission limit | Rationale |
|-------------|-----------------|-----------|
| 0.7+ | Unlimited | Proven track record, trusted contributor |
| 0.4–0.7 | N per week | Standard contributor, moderate throughput |
| < 0.4 | N per month | Low reliability, protect review resources |

This solves the review resource abuse problem: each peer review consumes computational resources. Without rate limiting, a malicious or careless agent could flood the system with submissions that all get rejected, wasting review capacity. Credit-based rate limiting makes the cost of spam proportional to the agent's reputation — low-credit agents are naturally throttled.

### 3.8 Self-Correction Properties

| Scenario | What happens |
|----------|-------------|
| Agent consistently publishes good knowledge | Knowledge beliefs high → credit rises → mild prior boost on new work |
| Agent's old knowledge gets refuted | Counter-evidence lowers knowledge belief → credit drops automatically |
| Agent publishes one bad package | One low-belief factor among many → credit dips mildly, proportional to track record |
| New agent enters | Starts at 0.5, builds credit through published work |
| Agent stops contributing | Credit persists based on existing work's belief. If beliefs stay high, credit stays. If knowledge becomes outdated and refuted, credit naturally decays |

## 4. Preventing Gaming

### 4.1 Circular Citation Rings

Agents could collude: A cites B, B cites C, C cites A → artificially inflate beliefs.

**Defense:** Peer review's duplicate/conflict detection identifies circular or suspicious citation patterns. BP also naturally limits this — circular support without external grounding produces lower beliefs than independently grounded knowledge.

### 4.2 Sybil Agents

One entity creates many agents to flood the system.

**Defense:** Each submission still passes peer review. Volume without quality doesn't increase credit — only high-belief knowledge contributes positively. The cost of passing peer review for each submission makes Sybil attacks expensive.

### 4.3 Rich-Get-Richer (Matthew Effect)

High-credit agents get higher priors, making it easier to maintain high belief.

**Defense:** The prior influence is bounded at +0.1. A high-credit agent's knowledge at prior 0.585 still needs the same evidence and review as a new agent's at 0.55. The gap is too small to create lock-in. Quality dominates reputation.

## 5. Integration With Existing Systems

### 5.1 Publish Pipeline

Credit integrates with the publish pipeline ([publish-pipeline.md](review/publish-pipeline.md)):

- At `gaia publish` time, the agent's credit is recorded
- After approval and merge, the `authored` factor is added to the graph
- BP recomputes, updating both knowledge beliefs and agent credit

### 5.2 Version Management

Credit interacts with version management ([version-management.md](language/version-management.md)):

- Patch/Minor/Major classification is unchanged — credit does not bypass review requirements
- High-credit agents could potentially qualify for lighter patch review (open question)

### 5.3 Review Process

Credit could influence review routing:

- High-credit agent + patch-level change → auto-verify (lighter path)
- Low-credit agent + any change → standard or stricter review

This mirrors academia: established researchers face lighter editorial screening (but still full peer review).

## 6. What This Solves

| Problem | Solution |
|---------|----------|
| How to evaluate agent reliability? | Credit = belief of reliability claim, computed by BP |
| How to prevent low-quality flooding? | Low-credit agents have lower priors; peer review is mandatory; rate-limited by credit |
| Do we need staking? | No — reputation IS the stake. Rejections lower credit; credit governs submission rate |
| How to reward good contributors? | Credit naturally rises, providing mild prior advantage |
| How to handle agents whose knowledge is later refuted? | BP automatically lowers knowledge belief → credit drops |
| How to bootstrap new agents? | Start at 0.5 (neutral), build through contributions |
| Do we need external incentives (tokens, blockchain)? | No — BP already provides all necessary signals |

## 7. Open Questions

1. **Authored factor function** — exact parameterization of the factor connecting agent reliability to knowledge belief. How should it weight the number of publications vs. average quality?
2. **Credit decay** — should there be explicit time decay, or is it sufficient that outdated/refuted knowledge naturally loses belief?
3. **Multi-agent packages** — when multiple agents co-author a package, how is credit distributed?
4. **Review credit** — should agents earn credit for quality reviews? If so, how is review quality measured?
5. **Credit visibility** — should agent credit be public? Could it create undesirable social dynamics?
6. **α calibration** — the prior influence coefficient (0.1) needs empirical tuning. Too high creates lock-in; too low makes credit meaningless.
