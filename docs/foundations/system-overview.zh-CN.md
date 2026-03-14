# Gaia 系统概览

本文档描述 Gaia 作为 CLI 优先、服务器增强的大规模知识模型平台的整体架构和交互流程。

关于产品定位原理，请参阅 [product-scope.md](product-scope.md)。

## 三个产品层

```
┌─────────────────────────────────────────────────────┐
│  研究代理（AI 代理，主要用户）                          │
│  ↦ bash + JSON                                      │
├─────────────────────────────────────────────────────┤
│  Gaia CLI (gaia-cli)                                │
│  本地完整、零配置                                      │
│  LanceDB + Kuzu（嵌入式）+ 本地 BP                    │
├──────────────┬──────────────────────────────────────┤
│   git/GitHub │  gaia publish --server               │
│   (版本控制)  │  (知识整合)                            │
├──────────────┴──────────────────────────────────────┤
│  Gaia Server — 大规模知识模型（LKM）                   │
│  Neo4j + LanceDB + ByteHouse + GPU BP               │
│  知识整合 · 全局搜索 · Peer Review · Registry · 大尺度 BP │
└─────────────────────────────────────────────────────┘
```

### Gaia CLI

主要产品界面。AI 代理和研究人员使用 CLI 创建、构建、预览和发布知识包。

关键特性：

- **代理优先** —— AI 代理是主要用户，通过 bash 调用 CLI 并解析 JSON 输出
- **本地完整** —— 嵌入式 LanceDB + Kuzu + BP 引擎，完全离线，零服务器依赖
- **1 个包 = 1 个 git 仓库** —— 可直接托管在 GitHub 上
- **Gaia 不封装 git** —— 版本控制完全委托给 git

目标核心流水线：

> **注意：** 当前基础基线遵循 [`review/publish-pipeline.md`](review/publish-pipeline.md)：核心 CLI 命令是 `gaia build`、`gaia infer` 和 `gaia publish`；自审查、图构建和反驳是代理技能。`main` 上发布的 `gaia review` 命令是自审查边车的本地兼容桥梁，而非长期核心审查边界。

| 命令 | 用途 |
|-----|------|
| `gaia init [name]` | 初始化知识包 |
| `gaia build` | 确定性验证/降低包源到 `.gaia/build/` 和 `.gaia/graph/` 工件 |
| `gaia review [PATH]` | 当前发布的 `.gaia/reviews/` 下本地自审查边车的兼容路径 |
| `gaia infer` | 从本地图 IR + 本地审查边车派生本地参数化，然后运行本地 BP |
| `gaia publish` | 发布到 git 或本地数据库（LanceDB + Kuzu） |
| `gaia show <name>` | 显示声明 + 连接的链 |
| `gaia search "query"` | 在本地 LanceDB 中搜索已发布节点 |
| `gaia clean` | 移除构建工件（`.gaia/` 目录） |

关于 CLI 架构详情，请参阅 [cli/boundaries.md](cli/boundaries.md)。

### Git / GitHub

版本控制和协作层。Gaia 将所有版本控制委托给 git，不重新实现自己的 VCS。

- 每个知识包是一个 git 仓库
- 协作通过标准 git 工作流（分支、PR）发生
- 服务器集成使用注册表仓库上的 GitHub webhook

### Gaia Server（大规模知识模型）

可选的注册表和计算后端。提供四个增强服务：

| 服务 | 用途 |
|-----|------|
| **知识整合** | 将批准的包内容合并到全局知识图谱 |
| **全局搜索** | 跨包向量 + BM25 + 拓扑搜索 |
| **同行审查和注册表整合** | 服务器端搜索、审查、规范绑定和编辑决策 |
| **大规模 BP** | GPU 集群上的十亿节点信念传播 |

服务器类似于 Julia 的 General Registry 或 crates.io —— 它只读消费包并提供集中服务。

## 主要交互路径：Git + Server Webhook

主要交互流程，类似于 Julia Pkg Registry：

```
代理（本地）              Git / GitHub             Gaia Server
─────────────           ──────────────           ───────────

gaia init
（编写 YAML 模块）
gaia build
代理自审查/图构建
gaia infer   （可选本地预览）

git add + commit
git push ──────────→  PR 到注册表仓库
                      webhook 通知 ─────────→  自动同行审查 + 搜索 + 身份匹配
                                                 │
                                                 ├─ 通过 → 合并到 LKM
                                                 │         PR 评论：✅
                                                 │
                                                 └─ 失败 → PR 评论：❌
                                                           + 同行审查/编辑报告

代理读取结果 ←── PR 评论
├─ 通过：完成
└─ 失败：根据报告修改
         → push → 再次触发审查
```

此流程的关键特性：

- **服务器从不修改包** —— 它是只读消费者
- **同行审查结果作为 PR 评论出现** —— 标准 GitHub 协作模型
- **代理自主** —— 代理可以读取同行审查发现并自我纠正，无需人工干预
- **完全异步** —— push 触发 webhook，代理轮询或监听结果

## 知识包格式

每个包是一个具有以下结构的 git 仓库：

```
galileo_tied_balls/              # = 1 个 git 仓库 = 1 个知识包
├── package.yaml                 # 清单（名称、版本、模块列表）
├── gaia.lock                    # （推迟）跨包依赖锁定
├── aristotle_physics.yaml       # 每模块 YAML —— 知识对象 + 链
├── thought_experiment.yaml
├── ...
└── .gaia/                       # 本地工件（git 忽略）
    ├── build/                   # 用于 LLM 审查的每模块 Markdown
    ├── graph/                   # 原始/本地规范图 IR 工件
    ├── reviews/                 # 本地自审查边车（main 上的兼容路径）
    ├── inference/               # 本地参数化 + 信念预览工件
    └── ...
```

包含知识对象的模块 YAML，包括 `chain_expr` 推理：

```yaml
type: reasoning_module
name: reasoning

knowledge:
  - type: ref
    name: heavier_falls_fast
    target: aristotle.heavier_falls_faster

  - type: setting
    name: thought_experiment_env
    content: "考虑静空气中的绑体思想实验。"

  - type: claim
    name: combined_slower
    content: "绑在一起的对应该比单独的重物体下落得更慢。"
    prior: 0.3

  - type: infer_action
    name: tied_bodies_analysis
    params:
      - name: premise
        type: claim
      - name: env
        type: setting
    return_type: claim
    content: "在给定前提和环境下分析绑体场景。"

  - type: chain_expr
    name: tied_bodies_contradiction
    edge_type: deduction
    steps:
      - step: 1
        ref: heavier_falls_fast
      - step: 2
        apply: tied_bodies_analysis
        args:
          - ref: heavier_falls_fast
            dependency: direct
          - ref: thought_experiment_env
            dependency: indirect
        prior: 0.85
      - step: 3
        ref: combined_slower
```

- **直接依赖（`args[].dependency: direct`）：** 语义角色 `premise`。如果这是错的，结论无法成立。跨包边界需要导出的知识。
- **间接依赖（`args[].dependency: indirect`）：** 语义角色 `context`。提供背景而非承重 BP 边。跨包边界，非导出的外部知识仅作上下文。

关于语言规范，请参阅 [language/gaia-language-spec.md](language/gaia-language-spec.md)。

## 技术栈

| 组件 | CLI（本地） | 服务器 |
|-----|----------|--------|
| 图存储 | Kuzu（嵌入式） | Neo4j |
| 内容存储 | LanceDB（嵌入式） | LanceDB（分布式） |
| 向量搜索 | LanceDB | ByteHouse（计划中） |
| BP 引擎 | 本地（单机） | GPU 集群 |
| LLM 审查 | 用户选择的模型通过 API 密钥/代理技能 | 服务器管理的同行审查 |

CLI 和服务器共享相同的核心库（`libs/`）和推理引擎（`libs/inference/`）。`GraphStore` ABC 抽象了图后端差异。

## 长期仓库结构

| 仓库 | 内容 | 类比 |
|-----|------|------|
| **gaia-core** | 共享模型、BP 算法、存储 ABC、序列化 | Rust stdlib |
| **gaia-cli** | CLI + 嵌入式 LanceDB/Kuzu + 本地 BP | cargo |
| **gaia-server** | FastAPI 注册表 + Neo4j + 分布式存储 + LLM 对齐/审查 | crates.io |

当前单体仓库映射：

- `libs/` → 未来的 gaia-core
- `cli/` → 未来的 gaia-cli
- `services/` + `frontend/` → 未来的 gaia-server

## 推迟的设计决策

以下内容明确推迟，将在后续基础阶段解决：

- 审查输出格式（确切的字段和评分模式）
- 直接发布契约（不带 git 的 `gaia publish --server`）
- `observation` 和 `assumption` 工件类型（领域模型的 V2）