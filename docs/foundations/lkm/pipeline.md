# 批处理流水线

> **Status:** Current canonical -- target evolution noted

批处理流水线（`scripts/pipeline/run_full_pipeline.py`）编排多篇论文的端到端处理，包含 7 个顺序执行的阶段。它是大规模填充知识图谱的主要路径。

## 7 个阶段

| # | 阶段 | 脚本 | 用途 |
|---|-------|--------|---------|
| 1 | `xml-to-typst` | `scripts/paper_to_typst.py` | 将论文 XML 转换为 Typst 包（可选 `--skip-llm`） |
| 2 | `build-gaia-ir` | `scripts/pipeline/build_graph_ir.py` | 将 Typst 包编译为 Raw Graph + Local Canonical Graph |
| 3 | `local-bp` | `scripts/pipeline/run_local_bp.py` | 对每个包运行本地 BP |
| 4 | `global-canon` | `scripts/pipeline/canonicalize_global.py` | 将本地节点映射到全局规范节点（可选 `--use-embedding`） |
| 5 | `persist` | `scripts/pipeline/persist_to_db.py` | 三写入 LanceDB + 图后端 |
| 6 | `curation` | `scripts/pipeline/run_curation_db.py` | 在全局图上执行 6 步策展流水线 |
| 7 | `global-bp` | `scripts/pipeline/run_global_bp_db.py` | 在完整全局图上运行 BP |

每个阶段作为子进程运行。如果某阶段失败，流水线立即停止。

阶段 1-3 对应 CLI 生命周期（参见 [../cli/lifecycle.md](../cli/lifecycle.md)）。阶段 4-7 是服务端操作（参见 [global-canonicalization.md](global-canonicalization.md)、[storage.md](storage.md)、[curation.md](curation.md)、[global-inference.md](global-inference.md)）。

## 配置

流水线从 TOML 配置文件读取默认值：

- `pipeline.toml` -- 基础配置（papers_dir、output_dir、并发数、规范化设置）
- `pipeline.{env}.toml` -- 环境特定覆盖（当设置 `--env` 或 `GAIA_ENV` 时加载）

配置深度合并：环境文件优先于基础配置。`[storage.env_mapping]` 部分复制环境变量（例如，将 `TEST_GAIA_LANCEDB_URI` 复制到 `GAIA_LANCEDB_URI`）。

## CLI 参数

| 参数 | 默认值 | 描述 |
|----------|---------|-------------|
| `--env` | `GAIA_ENV` | 环境名称（加载 `pipeline.{env}.toml`） |
| `--papers-dir` | 来自配置 | 输入论文目录 |
| `--output-dir` | 来自配置 | 所有产物的输出目录 |
| `--graph-backend` | 来自配置 | `kuzu`、`neo4j` 或 `none` |
| `--use-embedding` | 来自配置 | 在全局规范化中启用基于 embedding 的相似度 |
| `--stage` | -- | 仅运行此单个阶段 |
| `--from-stage` | -- | 从此阶段开始恢复执行 |
| `--concurrency` | 来自配置 | xml-to-typst 阶段的并行度 |
| `--clean` | false | 在 persist 阶段前清空所有数据库数据 |

`--stage` 和 `--from-stage` 互斥。

## 目录结构

流水线将输出组织在 `--output-dir` 下：

```
output/
  typst_packages/       # One subdirectory per paper (stages 1-3)
    paper_name/
      typst.toml
      *.typ
      .gaia/graph/      # Raw graph, local canonical graph
  global_graph/         # Global canonicalization output (stage 4)
  curation_report.json  # Curation results (stage 6)
  global_beliefs.json   # Global BP backup (stage 7)
```

## 代码路径

| 组件 | 文件 |
|-----------|------|
| 编排器 | `scripts/pipeline/run_full_pipeline.py` |
| 配置加载器 | `run_full_pipeline.py:_load_config()` |
| 阶段命令构建器 | `run_full_pipeline.py:build_stage_command()` |
| 基础配置 | `pipeline.toml` |

## 当前状态

可处理约 5 篇论文的批量流程。各阶段作为独立子进程运行，由编排器协调。策展阶段使用真实 LLM 调用和真实 embedding。

## 目标状态

此流水线是临时的批处理编排方案。目标架构将其替换为服务端任务：ingest 触发 review 和 canonicalization 作为异步任务，curation 作为定时后台服务运行。该流水线仍可用于初始数据填充和开发。
