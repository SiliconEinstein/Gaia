# Synthesis Structure Reference (closure chain)

This file complements `SKILL.md`. It contains the reusable section outline plus the banned-phrase checklist.

## Standard outline (any domain)

The synthesis answers exactly one question: **how is this result closed?** All sections serve that question. Adapt the closure-chain expression in §1 to the domain.

| § | section | what goes here |
|---|---------|----------------|
| — | **Title** | system / setting + quantitative result + framing question. Localize to user's prompt language. |
| — | **Abstract** | ≤ 250 English-word equivalents (~ 350 CJK characters). System, observational signals, theoretical task, central inversion result, what it resolves, what it leaves open. End with keywords. |
| — | **Figure 1** | The rendered closure-chain map (caller-supplied), embedded immediately after the abstract and before §1. Caption in domain language — e.g. *"Closure-chain map of <topic>: how the inputs combine to fix <target>."* — with zero banned phrases. §1 references it. |
| 1 | Introduction: the closure chain | State the closure-chain schematic explicitly: `(theoretical / computational inputs) → (intermediate quantities) → (observables / benchmarks) ↔ (target parameter)`. Instantiate with domain symbols. Frame the question as "does this number close the chain consistently", not "is this case typical". Reference Figure 1. |
| 2 | Observational / experimental constraints | Anchoring measurements with units and uncertainties. Which observation disciplines which input. |
| 3 | Theoretical / computational inputs | Method (computational / fit / simulation); intermediate quantities computed; model prunings; validity conditions. Quote computed numbers by author–year. |
| 4 | Inversion / fitting | The equation, optimization, or procedure that fixes the target result. Quote it explicitly. Resulting value. Clean separation of measured / computed / fitted / assumed. |
| 5 | Cross-method or cross-formalism comparison | Analytical vs numerical, mean-field vs many-body, model-A vs model-B, in-distribution vs out-of-distribution, etc. Quote discrepancies with units. Explain origin. Narrate any partial-disconfirm verification edges from the graph. For accepted contradictions, explain the direct scientific conflict and its associated open problem. Cite both sides by author–year. |
| 6 | Open problems and what would discriminate | Assumptions carrying the conclusion; theory-experiment gaps; theory-theory tensions; *specific* experiments / calculations to discriminate. Name measurements and thresholds. For each accepted contradiction, state the source claims, why they are adjudicably conflicting, and what open problem would discriminate them. Cite both sides by author–year. |
| 9 | References | Author–year, fully bibliographic. Build entries from the `data.papers` metadata block (`en_title` or `zh_title`, `authors` split on `\|`, `publication_date`, `publication_name`, `doi`). End with: *"For further information about each cited result, refer to the original paper via the DOI listed above."* |
| 10 | (Optional) methodology / provenance appendix | Only place where the audit table or system identifiers (`gcn_*`, `gfac_*`, `paper:<id>`) may appear. The rendered graph itself is **not** appendix material — it has been promoted to Figure 1. |

## Banned-phrase checklist (run before declaring done)

### English ban list

```
\b(evidence graph|subgraph|dependency graph|evidence chain|chain-internal|chain-backed)\b
\b(premise|factor|claim id|upstream support|upstream conclusion|upstream claim)\b
\b(tier ?[012]|first layer|second layer)\b   # graph-tier sense only
\b(audit table|audit trail|retrieval bundle|retrieval system)\b
\b(LKM|Large Knowledge Model)\b
\b(gcn_|gfac_|paper:|source package id)\b
```

### Simplified Chinese ban list

```
证据图|子图|依赖图|证据链|链内|链支持
前提|因子|声明 ?id|上游支撑|上游结论|上游声明
第 ?[012] ?层|第一层|第二层      # graph-tier sense only
审计表|核查表|审计轨迹|检索包|检索系统
LKM|大知识模型
gcn_|gfac_|paper:|来源包 ?id
证据链与上下文                    # graph's own section title
```

### Word allow-list (legitimate domain uses)

These are *not* bans, even though they share roots with banned terms — the test is whether a domain reader (who has never heard of the graph) parses them in the physical / scholarly sense:

- English: "closure chain", "reaction chain", "supply chain", "Markov chain", "tier-1 evidence" (clinical research sense).
- Chinese: `闭合链`, `推理链`, `反应链`, `供应链`, `马尔可夫链`, `一级证据` (clinical sense).

When grepping, exclude those phrases from the match (e.g. two-step grep, or `grep -v` post-filter).

### Locale-mirror rule

For any language other than English or Simplified Chinese, mirror each banned term to the equivalent native term before grepping. Document the locale-specific list in the run's `notes.md` so future runs in the same locale can re-use it.

## Mandatory inputs reminder

The skill **requires** the following from the caller:

1. Audited evidence graph source (DOT or Mermaid `flowchart`) **plus a rendered raster** (PNG / PDF / SVG) — the raster becomes Figure 1 of the body.
2. Audit table with payload anchors (premise / factor / step references into the underlying source data).
3. `data.papers` subset (paper-id → bibliographic-metadata) for the references list.

If any input is missing, **stop** and request it. Do not write a synthesis from raw source JSON without the audited graph — the graph is what disciplines the synthesis's structure and prevents drift.

## Citation rendering from `data.papers`

Each entry in `data.papers` looks like:

```json
"paper:812085204238729217": {
  "id": "812085204238729217",
  "doi": "10.1088/...",
  "publication_name": "Plasma Sources Sci. Technol.",
  "zh_title": "...",
  "en_title": "...",
  "authors": "A A Belevtsev | V F Chinnov | E Kh Isakaev",
  "publication_date": "2006-8-1"
}
```

Render as a typical journal-style reference; example output:

```
[1] A. A. Belevtsev, V. F. Chinnov, E. Kh. Isakaev. <Title>. Plasma Sources Sci. Technol., 2006. https://doi.org/10.1088/...
```

Match the rendering convention to the journal / venue the user is targeting (numbered vs author-year). Always include the DOI when present, so the user can navigate to the original paper.
