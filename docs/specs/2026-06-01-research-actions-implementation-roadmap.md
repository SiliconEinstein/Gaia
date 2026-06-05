# Research Actions Implementation Roadmap

> **状态：** package-native research actions 的 canonical implementation roadmap。
>
> **日期：** 2026-06-01
>
> **Canonical overview：**
> [Research Actions Package-Native Overview](2026-06-01-research-actions-package-native-overview.md)
>
> **迁移说明：**
> [Research Actions Migration Notes](2026-06-01-research-actions-migration-notes.md)
>
> **知识模型说明：**
> [Research Actions Knowledge Model](2026-06-01-research-actions-knowledge-model.md)

## 1. 实现原则

`gaia research` 应该按小切片实现。每个切片都必须保留 overview 中的硬性不变量：

- 不创建平行 focus registry；
- 不创建平行 obligation ledger；
- 默认不写 stable source；
- `gaia build check` 仍然是 package structural validation path；
- early Explore 保持 breadth-first，默认 pull budget 为 0。

当前实现已经越过早期 artifact-only 计划。canonical behavior 是：

- `explore` / `expand` 默认写 landscape trace、同步 inquiry hypotheses /
  obligations，并把浅层 search items 物化成本地 source package；
- `focus` 默认把最多 3 个 accepted focuses 写成 package `question(...)`，并设置
  active inquiry focus；
- `assess` 默认写 review `note(...)`、inquiry hypotheses / obligations，必要时写
  `candidate_relation(...)` scaffold，并可显式物化 LKM paper / paper-from-claim /
  reasoning-chain evidence package；
- `propose` 默认从 assessment 写 proposal trace；显式 `--accept` 时把 accepted
  open-ended research questions 写成 package `question(...)`，并把相关 hypotheses /
  obligations 写入 inquiry state；
- `report` / `stop` 已提供确定性 Markdown rendering 和 auditable stop criteria；
- `promote` 目前只写窄的 `materialize(...)` scaffold-to-formal link。

旧的 `docs/superpowers/plans/2026-06-01-*` 与 `2026-06-02-*` milestone plans 是已执行
或被当前 package/inquiry-centric design 取代的历史计划；不要再把它们作为实现锚点。

## 2. 已实现基线

当前 `gaia research` CLI surface：

```bash
gaia research status <pkg>
gaia research explore <pkg> --mode scan --search-json <search.json>
gaia research expand <pkg> --focus <focus> --search-json <search.json>
gaia research focus <pkg> --analysis-json <focus-analysis.json>
gaia research assess <pkg> --focus <focus> --analysis-json <assess-analysis.json>
gaia research propose <pkg> --from-assessment <assessment.json>
gaia research report <pkg> --artifact <artifact.json>
gaia research stop <pkg> --landscape <landscape.json> --assessment <assessment.json>
gaia research promote <pkg> --scaffold <binding> --by <formal_binding>
```

Deep LKM evidence entry points are explicit and assessment-scoped:

```bash
gaia research assess <pkg> \
  --focus <focus> \
  --materialize-paper <paper_id> \
  --materialize-paper-from-claim <claim_id> \
  --materialize-chain <claim_id>
```

Hard invariants for this baseline:

- `.gaia/research/` is trace / audit / cache, not a semantic source of truth.
- Accepted process state lives in `.gaia/inquiry`.
- Accepted scaffold / durable knowledge lives in package source.
- Broad `explore` and targeted `expand` do not deep-pull paper graphs.
- Stable truth claims and formal relations require an explicit promotion /
  formalization step.

## 3. 唯一后续执行序列

### N0. Documentation Source-Of-Truth Cleanup

Goal: remove conflicting historical implementation plans and leave one current roadmap.

Success criteria:

- this roadmap and `docs/foundations/cli/research-loop.md` describe the same default
  state flow;
- historical superpowers plans are replaced by superseded stubs or removed;
- no document says research actions default to artifact-only behavior, except when
  explicitly describing `--artifact-only`;
- future implementation work points back to this roadmap before creating a new
  bite-sized plan.

### N1. Propose Action (implemented)

Implement:

```bash
gaia research propose <pkg> --from-assessment <assessment.json>
```

Behavior:

- write a proposal artifact with open-ended research questions, candidate hypotheses,
  suggested simulations / experiments / proofs / benchmarks, and unresolved obligations;
- default to trace artifact plus inquiry suggestions;
- add `--accept` only when the accepted target can be expressed through existing Gaia
  primitives such as inquiry obligation / hypothesis or package `question(...)`;
- do not write stable truth claims.

Validation:

- proposal schema rejects stable-claim-looking payloads;
- accepted questions route through the same authored-source path used by `focus`;
- event payload records proposal counts and whether anything was accepted.

Current implementation also exposes `gaia research contract propose` and renders proposal
artifacts through `gaia research report`.

### N2. Promotion Boundary And Deferred Formalization

Immediate goal: keep `promote` narrow and make the deferred boundary explicit.

Current `promote` should remain a scaffold bookkeeping action:

```bash
gaia research promote <pkg> --scaffold <binding> --by <formal_binding>
```

It records that an already-reviewed formal graph record materializes a scaffold. It should
not synthesize new formal `claim(...)`, `derive(...)`, `infer(...)`, `contradict(...)`, or
relation statements yet.

Deferred work: full LKM-to-Gaia formal source promotion and review-gated source synthesis.
This is intentionally **not** part of the next implementation slice because it requires a
separate design pass. Before expanding `promote` beyond the current `materialize(...)`
link, write and review a focused sub-spec that defines:

- how assessment `supports` / `opposes` / `qualifies` / `undercuts` maps, or refuses to
  map, to `claim(...)`, `derive(...)`, `infer(...)`, `contradict(...)`, `question(...)`,
  and `obligation`;
- how chain-backed LKM claims differ from no-chain source claims;
- how to preserve LKM provenance in generated Gaia statements;
- how to detect duplicate claims, shared-factor leakage, scope mismatch, and
  over-strong contradictions;
- which parts are deterministic CLI validation and which parts remain agent / human
  judgment.

Only after that deferred sub-spec is reviewed should implementation extend
`gaia research promote` beyond the current `materialize(...)` link.

Immediate validation:

- roadmap and CLI docs clearly state that formal source synthesis is deferred;
- current `promote` keeps writing only `materialize(...)` links;
- tests continue to cover the existing scaffold-to-formal-link behavior.

Deferred validation:

- promotion cannot synthesize formal source from ungrounded assessment refs;
- promotion refuses unsupported relation / hint combinations;
- generated source passes `gaia build check`;
- all generated statements carry provenance to the source package, LKM paper, chain, or
  assessment artifact.

### N3. Legacy `gaia-lkm-explore` Migration And Deprecation Gate

Implement only after N1 and N2 are stable enough to cover the old workflow.

Required work:

- document or implement a read-only import path from `.gaia/exploration/` to
  `.gaia/research/` provenance;
- mark `gaia-lkm-explore` as deprecated compatibility surface;
- update docs and skills so `gaia research` is the only canonical workflow;
- keep useful deterministic utilities only when they write package-native artifacts.

Validation:

- at least one real LKM-backed live run completes with `gaia research` and does not call
  the old entry point;
- old `.gaia/exploration/` artifacts are never treated as canonical semantic state;
- deprecation docs include replacement commands.

### N4. Later Ecosystem Work

These remain outside the immediate implementation sequence:

- LKM public writeback protocol;
- Propose -> external discovery / research -> Merge loop;
- external TUI or hosted product surface;
- large-scale review-generation evaluation beyond local package artifacts.
