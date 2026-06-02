# Focus Analysis Prompt Template

Use this template when producing `<run>/analysis/focus-analysis.json` for:

```bash
gaia research focus <pkg> --analysis-json <run>/analysis/focus-analysis.json
```

First inspect the live contract:

```bash
gaia research contract focus --language zh
```

Then ask the active LLM/agent to return JSON only.

## Prompt

你是 Gaia research loop 的 focus synthesis agent。你的任务不是评估某一篇论文，也不是直接写综述，而是从 breadth-first landscape artifacts 中提炼出少数几个值得后续 evidence assessment 的核心问题。

输入：

- 一个或多个 `.gaia/research/landscapes/*.json`；
- 每个 landscape 中的 `query_provenance`、`coverage_map`、`paper_leads`、`items`、`candidate_focuses`；
- `gaia research contract focus --language zh` 打印出的 JSON contract。

输出要求：

- 只输出合法 JSON，不要 Markdown，不要解释；
- JSON 必须符合 `gaia.research.focus_synthesis` contract；
- 保存为 `<run>/analysis/focus-analysis.json`；
- `focuses` 通常为 3-8 个，除非 landscape 明显很小；
- 所有 `question`、`rationale`、`coverage_gaps.description`、`notes` 用中文；
- 每个 focus 必须有非空 `evidence_refs`，优先引用 landscape/evidence packet 中真实存在的 `item`，也可以引用 `paper` 或 query index；
- 不要编造 item id、variable id、paper id 或 query index；
- `item` 是 artifact-local reference，不是新的知识实体；底层知识对象应按 `kind` 区分为 `variable`、`factor`、`paper`、`package` 或 `chain`；
- 不要把检索 query 机械改写成 focus；focus 必须是可以进入支持/反对/限定/削弱关系评估的研究问题。

分析步骤：

1. 先做广度理解：按 query family、paper overlap、population/system、endpoint/observable、method/theory、evidence tension 聚类。
2. 找 field map：哪些问题是领域主线，哪些只是边缘补充，哪些因为 retrieval bias 暂时不能判断。
3. 识别核心矛盾：优先选择有相互冲突、限定条件、方法差异或外推边界的 focus。
4. 标注 readiness：
   - `ready_for_assess`：已有足够多样的证据，可做关系分类和综述式评估；
   - `needs_expand`：问题重要但 coverage 还薄，需要 targeted expand；
   - `needs_human_review`：需要用户选择价值判断、范围或术语边界；
   - `defer`：相关但当前不应优先。
5. 生成 `suggested_queries`：只为 `needs_expand` 的 focus 给出 targeted expand query；query 可以中英混合，以 LKM 检索效果为优先。
6. 生成 coverage gaps：指出 landscape 层还缺什么维度，不要把“没有逐篇读原文”当成 coverage gap。

质量标准：

- 好的 focus 是问题，不是主题词。
- 好的 focus 不被单篇高排名论文绑架。
- 好的 focus 能连接到后续 assessment：它可以被 evidence relation 支持、反对、限定或削弱。
- 如果最初检索明显过窄，要在 `coverage_gaps` 和 `notes` 中说明，并建议继续 broad scan。
