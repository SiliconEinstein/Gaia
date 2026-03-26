# 审查 Pipeline

> **Status:** Current canonical -- target evolution noted

审查引擎评估知识包并为 belief propagation 生成概率参数。它目前位于 `cli/llm_client.py`，由 `libs/pipeline.py:pipeline_review()` 编排。

## 审查产出

`pipeline_review()` 返回一个 ReviewOutput，包含：

- **`node_priors`** -- `dict[str, float]`，将每个 local canonical node ID 映射到其先验概率。先验按知识类型分配：`setting` = 1.0，`claim`/`question`/`action`/`observation` = 0.5。
- **`factor_params`** -- `dict[str, FactorParams]`，将每个推理 factor 映射到其条件概率。值来自审查链步骤的 `conditional_prior` 字段；如果没有审查数据则默认为 1.0。
- **`review`** -- 原始审查数据，包括摘要文本和按链步骤的评估。
- **`model`** -- 产生审查的模型（`"mock"` 或 LLM 模型名称）。

## ReviewClient (LLM)

ReviewClient 使用 litellm 将包的 markdown 发送给 LLM，附带系统提示（`cli/prompts/review_system.md`）。LLM 返回 YAML，包含每个链步骤的评估，含 `conditional_prior`、`weak_points` 和 `explanation` 字段。

解析器（`_parse_response`）处理多种 YAML 格式：
- 包含 `chains` 列表和 `steps` 的结构化格式
- 使用 `chain_name.step_index` 键的扁平格式
- 解析失败时回退到 `{"summary": "Parse error", "chains": []}`

提供同步（`review_package`）和异步（`areview_package`）接口。

## MockReviewClient

MockReviewClient 在不调用 LLM 的情况下生成确定性的审查输出：

- `review_from_graph_data()` -- 由 `pipeline_review(mock=True)` 使用。遍历 `graph_data` 中的推理 factor，为每个分配 `conditional_prior: 0.85`。
- `review_package()` -- 从 markdown 中解析 `[step:name.N]` 锚点（旧格式）。

Mock 审查被所有 CLI 命令（`gaia infer`、`gaia publish --local`）和测试使用。

## Pipeline 集成

`libs/pipeline.py:pipeline_review()` 编排以下流程：

1. 如果 `mock=True`，调用 `MockReviewClient.review_from_graph_data(graph_data)`
2. 如果 `mock=False`，从图数据渲染 markdown，调用 `ReviewClient.areview_package()`
3. 从 LocalCanonicalGraph 知识节点构建 `node_priors`，使用基于类型的默认值
4. 通过本地图将审查链结论映射回 factor ID 来构建 `factor_params`
5. 返回 ReviewOutput

审查输出直接馈入 `pipeline_infer()`，后者构造 LocalParameterization 并运行 BP。参见 [../gaia-ir/parameterization.md](../gaia-ir/parameterization.md) 了解参数化模型。

## 目标：服务端 ReviewService

目标架构用服务端 ReviewService 替代 CLI 端审查，该服务将：

1. **验证** -- 独立重新编译提交的源码；与提交的 `raw_graph.json` 进行差异对比。
2. **审计规范化** -- 检查每个 LocalCanonicalNode 的分组决策。
3. **多 agent 审查** -- 多个独立的 LLM agent 并行评估，生成 `PeerReviewReport`。
4. **反驳周期** -- 阻塞性发现触发最多 5 轮作者反驳。
5. **守门人** -- 综合结果做出接受/拒绝决策，触发全局规范化和集成。

## 代码路径

| 组件 | 文件 |
|------|------|
| ReviewClient | `cli/llm_client.py:ReviewClient` |
| MockReviewClient | `cli/llm_client.py:MockReviewClient` |
| 审查 pipeline 函数 | `libs/pipeline.py:pipeline_review()` |
| 系统提示 | `cli/prompts/review_system.md` |
| 先验/参数构建器 | `libs/pipeline.py:_build_node_priors()`, `_build_factor_params()` |

## 当前状态

`pipeline_review()` 通过 `mock` 参数同时支持 mock 和 LLM 路径。当前 CLI 命令默认 `mock=True`。真实 LLM 审查需要显式设置 `mock=False` 并提供有效的 API 凭证。审查客户端位于 `cli/` 而非 `libs/`，因为它最初是 CLI 专用的。

## 目标状态

- 将审查逻辑迁移到服务端 ReviewService，在包摄入时自动运行。
- 将 ReviewClient 从 `cli/` 迁移到 `libs/` 或 `services/`。
- 添加 `gaia review` CLI 命令，调用真实 LLM 审查并保存审查附件。
