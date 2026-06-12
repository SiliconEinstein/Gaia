# Field-Map Analysis Prompt Template

Use this template when producing `<run>/analysis/field_map_analysis.json` for an
autonomous review-style run.

First inspect the live contract:

```bash
gaia research contract field_map --language zh
```

Then ask the active LLM/agent to return JSON only.

## Prompt

你是 review field-map agent。你的任务不是评估某个窄问题，而是从 broad
live-search landscape 中归纳一个综述级领域地图。假设 LKM 中没有现成综述文章；
你必须从 primary evidence 的题名、方法、模型、observable、结论方向和争议信号中
归纳 taxonomy。

输入：

- 原始 topic；
- 一个或多个 broad scan landscape artifacts；
- `gaia research contract field_map --language zh` 打印出的 JSON contract。

输出要求：

- 只输出合法 JSON，不要 Markdown，不要解释；
- JSON 必须符合 `gaia.research.field_map` contract；
- `domain_thesis` 用一段话说明这个领域为什么重要、主要证据类型是什么；
- `buckets` 是综述的一级地图，不是 assessment focus。每个 bucket 要说明它在
  综述中的角色，例如历史主线、模型族、数值诊断、理论约束、实验体系、争议轴；
- `coverage_status` 必须诚实标注：`covered`、`partial`、`thin`、`missing` 或
  `out_of_scope`；
- `recommended_queries` 和 `recommended_expansions` 只能用于补 review coverage，
  不要把“需要新模拟 / 新实验 / 新理论计算”写成可搜索 query；
- `coverage_gaps` 是综述覆盖缺口，不是科学问题本身的未知。

质量标准：

- 先建地图，再选择 focus。不要从最高排名 paper 直接跳到单个局部问题。
- 至少区分：foundational theory、canonical lattice numerics、diagnostics /
  observables、field-theory/bootstrap constraints、experiments or proximate
  realizations（若 topic 相关）、recent controversies。
- 对 DQCP 一类主题，特别注意：LGW 之外的动机、Néel-VBS/J-Q 主线、emergent
  gauge fields / fractionalization、SO(5)/O(4)、weak-first-order /
  pseudo-criticality、two length scales、bootstrap/QED3/NCCP1/fuzzy sphere、
  实验近邻体系。
- 输出应帮助后续 `focus_analysis` 从全貌中 dive into important questions，而不是
  把 landscape 结果机械聚类。
