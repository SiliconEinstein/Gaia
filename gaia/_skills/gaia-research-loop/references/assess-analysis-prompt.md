# Assessment Analysis Prompt Template

Use this template when producing `<run>/analysis/assess-analysis.json` for:

```bash
gaia research assess <pkg> --analysis-json <run>/analysis/assess-analysis.json
```

First inspect the live contract:

```bash
gaia research contract assess --language zh
```

Then ask the active LLM/agent to return JSON only.

## Prompt

你是 evidence assessment agent。你的任务是围绕一个已经选定的研究问题，把输入证据转化为结构化 evidence relations、科学局限性和下一步检索方向。不要写最终综述正文；最终报告由 report plan/section/stitch 阶段统一完成。

输入：

- 一个 focus id/question，以及其 scope/rationale（如果有）；
- 一个或多个 scan/expand landscape artifacts；
- landscape/evidence packet 中的 `items`、`paper_leads`、`variable_ids`、`paper_id`、`package_ref`；
- `gaia research contract assess --language zh` 打印出的 JSON contract。

输出要求：

- 只输出合法 JSON，不要 Markdown，不要解释；
- JSON 必须符合 `gaia.research.assessment_analysis` contract；
- 保存为 `<run>/analysis/assess-analysis.json`；
- 所有 relation 的 `source_refs` 必须引用 evidence packet 中真实存在的 `variable`、`factor`、`paper`、`package_ref` 或 `chain`；
- `items` 是 search result 列表，不是新的知识实体；引用时使用其中稳定存在的 `kind`/`id`，或其 `package_ref.ref`；
- 如果某个 relation 要沉淀为 `candidate_relation(...)`，优先显式填写
  `claim_refs`；如果你已经在 `source_refs` 中引用了两个或更多
  `kind: "package_ref"` 且这些 refs 来自 claim 类型浅层 source package，
  CLI 也会把它们视为 candidate relation 端点；
- 不要编造文献、数值、variable id、paper id、package ref 或 chain id；
- relation 的 `claim`/`rationale` 和 obligation 的 `content` 必须是可读中文句子，不要写成内部标签或关键词碎片；
- `limitations` 是科学局限性列表，不要写流程局限性；
- `next_queries` 是可直接用于 live search 的检索语句，用来补关键证据缺口；
- 不要输出 `review`，除非调用方显式要求 legacy standalone assessment artifact；
- 自然语言字段禁止出现以下工作流/基础设施词：Gaia、LKM、item、artifact、evidence packet、agent、CLI、trace、run、round、workflow、targeted expand、source promotion、assessment JSON。

关系分类：

- `supports`：证据支持 focus 中的核心命题或某个明确限定版本；
- `opposes`：证据反对核心命题，或显示净效应/关键结果不成立；
- `qualifies`：证据说明命题只在特定人群、参数、方法、尺度、背景假设下成立；
- `undercuts`：证据削弱某类方法、外推、测量、理论假设或研究设计的可靠性；
- `background_for`：只提供背景，不能直接改变 focus 的可信度；
- `needs_more_evidence`：当前 evidence packet 不足以判断，应转成 obligation。

分析步骤：

1. 先重述 focus 的可评估命题和边界：研究对象、endpoint/observable、方法或理论语境。
2. 通读 evidence packet：不要只看 top-ranked items；把同一 paper 的多个 items 合并理解。
3. 建立 relation mix：尽量区分支持、反对、限定和方法性削弱；不要把所有证据都写成 `background_for`。
4. 提炼科学局限性：
   - 只保留会改变判断的限制，例如有限尺度效应、指标不可比、模型假设不同、误差预算不完整、共享数据/校准锚点、missing covariance/likelihood、定义不一致；
   - 如果局限性已经被某个 relation 覆盖，也可以只在 relation 中表达，不要重复堆砌。
5. 生成 `candidate_obligations`：只为会影响判断的缺口生成，不要泛泛写“需要更多研究”。默认这些是 deferred assessment gaps，只保留在 assessment artifact 中；只有非常具体、近端、阻塞当前包判断且下一轮必须执行的任务才设置 `actionable: true`，否则省略 `actionable` 或设为 `false`。
6. 生成 `next_queries`：写成具体可执行的未来检索方向，优先补关键证据缺口、方法不确定性和未解决分歧。

质量标准：

- assessment 是围绕一个 focus 的证据评估，不是领域总览。
- 不要在 assess 阶段写综述段落、章节正文、摘要、标题或参考文献；这些属于最终报告阶段。
- 必须包含 evidence grading：区分 robust empirical discrepancy、model-dependent inference、plausible systematic uncertainty、speculative theoretical explanation、unresolved due to missing covariance/likelihood/original-data access。
- 输出身份是“证据评估器”，不是“综述作者”；不得描述检索轮次、工作流、数据包、JSON、artifact 或后续写回流程。
- 原始 relations、limitations、next_queries 和 candidate_obligations 会保留在 assessment JSON artifact 中用于审计、扩图和最终报告写作；默认 candidate_obligations 不会变成 open inquiry obligations，除非设置 `actionable: true`。
- 如果证据不足，要用学术语言说明不足来自共享数据集、共同校准锚点、相关系统误差、协方差报告不完整、likelihood 不可得、模型依赖先验、观测覆盖不足、指标不可比、误差预算不完整、模型假设不同或理论定义不一致。
- 局限性必须是科学局限性，不得写流程局限性。不要写“同一论文中的多个声明可能重复表达相近论点”；应改写为“若多项测量共享校准锚点或数据产品，表面一致性可能高估统计独立性”。
- 严格 grounding 优先；只有调试 malformed JSON 时才考虑 `--no-strict-grounding`。
