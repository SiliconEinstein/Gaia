# CLI 生命周期

> **Status:** Current canonical

Gaia CLI（`cli/main.py`）是一个 Typer 应用，提供单包交互工作流。本文档涵盖从 init 到 publish 的完整本地生命周期。

## 工作流概览

```
gaia init  ->  author  ->  gaia build  ->  [agent skills]  ->  gaia infer  ->  gaia publish
```

额外的实用命令：`gaia search`、`gaia clean`。

## 命令

### `gaia init <name>`

使用 v4 DSL 运行时搭建一个新的 Typst 知识包。

- **输入**：包名称。
- **输出**：一个新目录，包含 `typst.toml`、`lib.typ`、vendored `_gaia/` 运行时和模板模块文件。
- **功能**：从 `libs/typst/gaia-lang-v4/` 复制 v4 运行时，并创建最小包结构。
- **不做的事**：不编译、不调用 LLM、不访问网络。

### `gaia build [path]`

从 Typst 源码到 Gaia IR 的确定性降级。

- **输入**：包源码（`.typ` 文件 + `typst.toml`）。
- **输出**：`.gaia/graph/raw_graph.json`、`.gaia/graph/local_canonical_graph.json`、`.gaia/graph/canonicalization_log.json`。
- **功能**：验证包结构、通过 `typst query` 提取知识、编译原始图、构建单例局部规范图。
- **不做的事**：不调用 LLM、不搜索、不分配概率。
- **输出格式**：`--format md`（默认）、`json`、`typst`、`all`。
- **可选**：`--proof-state` 标志运行 `libs/lang/proof_state.analyze_proof_state()` 并生成证明状态报告。

Build 运行 `libs/pipeline.py` 中的统一 `pipeline_build()`：

```
typst_loader.load_typst_package_v4(pkg_path)
    -> compile_v4_to_raw_graph(graph_data)
    -> build_singleton_local_graph(raw_graph)
    -> save artifacts to .gaia/graph/ and .gaia/build/
```

### Agent Skills（可选，推荐）

Build 和 infer 之间的可选 LLM 辅助步骤：

- **自审查**：两轮 LLM 推理质量评估。产出候选薄弱点和条件先验作为本地附属产物。
- **图构建**：检查原始图，对语义相似节点进行聚类，产出精化的局部规范图和可选的局部参数化。

如果审查发现缺失的前提或引用，agent 会更新源码并重新运行 `gaia build`。

### `gaia infer [path]`

本地置信传播预览。

- **输入**：局部规范图 + 局部参数化覆盖层。
- **输出**：`.gaia/infer/infer_result.json` 下的本地置信预览。
- **功能**：将局部规范图适配为 `FactorGraph`，从本地审查附属产物导出参数化，运行带阻尼的 sum-product BP。
- **范围**：仅限包本地。不查询或修改全局图。

`gaia infer` 链接三个管线函数：

1. `pipeline_build()` —— 重建包
2. `pipeline_review(build, mock=True)` —— 通过 `MockReviewClient` 导出先验和因子参数
3. `pipeline_infer(build, review)` —— 将图适配为因子图，运行 `BeliefPropagation`，输出置信值

BP 算法详情参见 [../bp/inference.md](../bp/inference.md)。因子势函数参见 [../bp/potentials.md](../bp/potentials.md)。

### `gaia publish [path]`

从本地到共享系统的提交交接。

- **输入**：源码 + 原始图 + 局部规范图 + 规范化日志。
- **输出**：将包提交到注册中心（本地 LanceDB 或远程服务器）。
- **功能**：将局部规范图 + 审查输出转换为存储模型，通过 `StorageManager` 摄入。
- **不提交的内容**：作者本地参数化、自审查先验、本地置信预览。
- **模式**：`--git`（基于 git）、`--local`（LanceDB + Kuzu）、`--server`（远程 API，已预留）。

#### `gaia publish --local` 流程

完整的四步本地发布管线：

1. `pipeline_build()` —— 加载并编译
2. `pipeline_review(build, mock=True)` —— 模拟审查（LLM 审查尚未接入 CLI）
3. `pipeline_infer(build, review)` —— 本地 BP
4. `pipeline_publish(build, review, infer, db_path=...)` —— 将 Gaia IR 转换为存储模型，通过 `StorageManager` 三写入 LanceDB + Kuzu

`--db-path` 选项（或 `GAIA_LANCEDB_PATH` 环境变量）控制 LanceDB 的存储位置。

### `gaia search <query>`

在 LanceDB 中对已发布知识进行 BM25 全文搜索。

- 主要方式：通过 LanceDB FTS 索引的 BM25 全文搜索
- 回退方式：针对 CJK/未分词文本的 SQL `LIKE` 过滤
- `--id <knowledge_id>`：直接查找，并从 `belief_history` 获取最新置信值

### `gaia clean [path]`

移除包目录中的 `.gaia/` 构建产物。

## 各阶段产物

| 阶段 | 关键产物 |
|---|---|
| Init | `typst.toml`、`lib.typ`、`_gaia/`、模板 `.typ` 文件 |
| Source | `.typ` 文件、`typst.toml`、`gaia-deps.yml` |
| Build | `raw_graph.json`、`local_canonical_graph.json`、`canonicalization_log.json` |
| Self-review | 审查附属产物（候选薄弱点、条件先验） |
| Infer | `local_parameterization.json`、`infer_result.json`（置信预览） |
| Publish | 提交到注册中心（源码 + 原始图 + 局部规范图 + 日志） |

## 代码路径

| 函数 | 文件 |
|----------|------|
| CLI 应用 + 命令 | `cli/main.py` |
| 管线函数 | `libs/pipeline.py`（`pipeline_build`、`pipeline_review`、`pipeline_infer`、`pipeline_publish`） |
| Typst 加载器 | `libs/lang/typst_loader.py` |
| Gaia IR 编译器 | `libs/graph_ir/typst_compiler.py` |
| 模拟/LLM 审查 | `cli/llm_client.py` |
| BP 引擎 | `libs/inference/bp.py` |
| 存储管理器 | `libs/storage/manager.py` |

## 当前状态

所有命令均可正常工作。`publish --server` 已预留（退出并提示"尚未实现"）。CLI 中审查始终使用 `MockReviewClient`；真正的 LLM 审查仅通过管线脚本可用。

## 目标状态

- 添加 `gaia review` 命令，通过 `ReviewClient` 调用真正的 LLM 审查并保存审查附属文件。
- 将 `publish --server` 接入网关 API 的 `POST /packages/ingest` 端点。
