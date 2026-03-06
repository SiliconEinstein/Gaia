# Gaia CLI 设计文档 v2

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-05 |
| 状态 | Draft |
| 基于 | v1 讨论迭代，claim-centric + 本地完整推理 |
| 关联 | `docs/examples/galileo_tied_balls.md`, `docs/examples/einstein_elevator.md` |

---

## 1. 概述

Gaia CLI 是 Gaia 知识超图系统的命令行工具，类比 Cargo / npm，但管理的对象是 **知识包 (knowledge package)** 而非代码。

**核心设计原则：**

- **Claim-centric**：用户的基本操作是"提出主张"（`gaia claim`），指定引用和理由
- **本地完整，远程增强**：本地内嵌完整推理引擎（LanceDB + Kuzu + BP），开箱即用；远程 server 提供 LLM review、精确 prior 估计、大规模图
- **声明式 + 交互式**：复杂推理链用包文件声明，探索式使用用交互命令
- **Git-like 工作流**：init → claim → build → commit → push → review → publish

---

## 2. 核心概念

### 2.1 Claim（主张）

用户操作的基本单元。一个 claim 包含三要素：

| 要素 | 说明 | 对应参数 |
|------|------|---------|
| **结论** | 你主张什么 | 主参数 `"..."` |
| **引用** | 基于什么已有知识 | `--cite <ids>` |
| **理由** | 为什么这个结论成立 | `--why "..."` |

```bash
$ gaia claim "v ∝ W 定律" --cite 1,2 --why "从学说和观察归纳出定量规律"
```

这和写论文一模一样：引用已有知识，加上推理，得出新结论。

### 2.2 Knowledge Package（知识包）

知识包是提交的基本单位。一个包包含：

- **元数据** (`gaia.toml`)：名称、版本、描述、作者、sub-package 顺序与依赖
- **Sub-packages** (`packages/*.yaml`)：按逻辑分组的 claim 集合

### 2.3 本地 vs 远程

本地 CLI 内嵌完整推理引擎，像 git 一样开箱即用，不需要启动任何 server 进程。远程 server 是可选的增强层，提供团队协作和大规模推理。

| | 本地 CLI | 远程 Server (LKM) |
|---|---|---|
| 存储 | LanceDB + Kuzu（内嵌） | 完整后端集群 |
| BP | 有（本地推理引擎） | 有（十亿级规模） |
| Prior | 类型默认值 | LLM 精确估计 |
| 矛盾检测 | 基于引用结构自动检测 | LLM 辅助深度检测 |
| Review | 无（或本地 LLM 可选） | LLM 审查 |
| 适合 | 个人研究、Agent 探索、离线使用 | 团队协作、大规模知识图谱 |

用户不需要手动设置 prior — 本地根据 claim type 自动分配默认值，commit 后立刻跑 BP，即时看到 belief 变化和矛盾传播。

---

## 3. 包目录结构

```
galileo_tied_balls/
├── gaia.toml                              # 包清单
└── packages/
    ├── aristotle_physics.yaml             # Sub-package 1
    ├── galileo1638_tied_balls.yaml        # Sub-package 2
    ├── galileo1638_medium_density.yaml    # Sub-package 3
    ├── galileo1638_vacuum_prediction.yaml # Sub-package 4
    ├── newton1687_principia.yaml          # Sub-package 5
    └── apollo15_1971_feather_drop.yaml    # Sub-package 6
```

### 3.1 `gaia.toml` — 包清单

```toml
[package]
name = "galileo_tied_balls"
version = "1.0.0"
description = "From Aristotle to Apollo 15: overturning 'heavier falls faster'"
authors = ["Galileo Galilei", "Isaac Newton"]

[[packages]]
name = "aristotle_physics"
order = 1
description = "Aristotle's natural motion doctrine and everyday observations"

[[packages]]
name = "galileo1638_tied_balls"
order = 2
description = "The tied-balls paradox: reductio ad absurdum"
depends_on = ["aristotle_physics"]

[[packages]]
name = "galileo1638_medium_density"
order = 3
depends_on = ["aristotle_physics"]

[[packages]]
name = "galileo1638_vacuum_prediction"
order = 4
depends_on = ["galileo1638_tied_balls", "galileo1638_medium_density"]

[[packages]]
name = "newton1687_principia"
order = 5
depends_on = ["aristotle_physics"]

[[packages]]
name = "apollo15_1971_feather_drop"
order = 6
depends_on = ["galileo1638_vacuum_prediction", "newton1687_principia"]

[remote]
registry = "http://localhost:8000"
```

### 3.2 Sub-package YAML — Claim 格式

每个 sub-package 是一组 claim。用户只需提供结论、类型、引用和理由。

**`packages/aristotle_physics.yaml`**

```yaml
claims:
  - id: 5001
    type: observation
    content: "日常观察: 石头比树叶落得快"
    source: "Everyday experience"

  - id: 5002
    type: premise
    content: "亚里士多德自然运动学说: 速度由物体本性（重量）决定"
    source: "Aristotle, Physics IV.8, ~350 BCE"

  - id: 5003
    type: theory
    content: "亚里士多德定律: 下落速度正比于重量 (v ∝ W)"
    cite: [5001, 5002]
    why: "从学说和日常观察归纳出定量规律"
```

**`packages/galileo1638_tied_balls.yaml`**

```yaml
claims:
  - id: 5004
    type: premise
    content: "思想实验设定: 用绳子把重球 H 绑在轻球 L 上"

  - id: 5005
    type: deduction
    content: "推导 A: 轻球拖拽重球 → 组合体 HL 比 H 慢"
    cite: [5003, 5004]
    why: "按 v∝W 定律，L 慢于 H，L 会拖拽 H"

  - id: 5006
    type: deduction
    content: "推导 B: 组合体更重 → 组合体 HL 比 H 快"
    cite: [5003, 5004]
    why: "按 v∝W 定律，HL 总重量 > H，应更快"

  - id: 5007
    type: deduction
    content: "同一物体不可能既比 H 快又比 H 慢 — 矛盾"
    cite: [5005, 5006]
    why: "两个有效推导从同一前提得出互相矛盾的结论"

  - id: 5008
    type: deduction
    content: "亚里士多德定律自相矛盾，必须抛弃"
    cite: [5007, 5003]
    why: "推导都有效 → 错误必在共享前提 v∝W"
```

注意：没有 `prior`、`probability`、`belief`。没有 `edges` 段。用户只写 claim，server 自动推断边类型和矛盾关系。

---

## 4. CLI 命令

### 4.1 核心工作流

| 命令 | 说明 | 类比 |
|------|------|------|
| `gaia init [name]` | 创建新包 | `cargo init` |
| `gaia claim "..." [--cite ids] [--why "..."] [--type T]` | 提出主张 | — |
| `gaia build` | 校验包结构 | `cargo check` |
| `gaia commit -m "msg"` | 提交到本地图 + 自动 BP | `git commit` |
| `gaia push` | 推送到 server | `git push` |
| `gaia review <id>` | 触发 LLM 审查 | — |
| `gaia publish <id>` | 审查通过后入图发布 | `npm publish` |
| `gaia status [id]` | 查看状态 | `git status` |

### 4.2 `gaia claim` 详细

```bash
# 叶子节点（无引用，直接观察/引用文献）
$ gaia claim "石头比树叶落得快" --type observation
  Created claim 5001

# 有引用的主张
$ gaia claim "v ∝ W 定律" \
    --cite 5001,5002 \
    --why "从学说和观察归纳出定量规律" \
    --type theory
  Created claim 5003

# 类型可选，不指定则由 server 在 review 时推断
$ gaia claim "组合体 HL 比 H 慢" --cite 5003,5004 --why "轻球拖拽重球"
  Created claim 5005
```

**claim type 参考：**

| type | 说明 | 例子 |
|------|------|------|
| `observation` | 直接观察/实验数据 | "石头快于树叶" |
| `premise` | 已有理论/学说 | "亚里士多德自然运动学说" |
| `theory` | 归纳/抽象出的理论 | "v ∝ W 定律" |
| `deduction` | 逻辑推导 | "组合体应更慢" |
| `prediction` | 理论预测 | "真空中所有物体等速下落" |
| `experiment` | 实验验证 | "Apollo 15 锤子=羽毛" |

### 4.3 `gaia build` — 结构校验

```bash
$ gaia build
Checking galileo_tied_balls v1.0.0 ...
  ✓ aristotle_physics: 3 claims
  ✓ galileo1638_tied_balls: 5 claims
  ✓ galileo1638_medium_density: 3 claims
  ✓ galileo1638_vacuum_prediction: 3 claims
  ✓ newton1687_principia: 3 claims
  ✓ apollo15_1971_feather_drop: 3 claims
  ✓ 所有引用 (cite) 指向已存在的 claim
  ✓ 依赖拓扑是合法 DAG
  ✓ 无孤立 claim（无引用且未被引用）
Build succeeded: 20 claims across 6 packages.
```

### 4.4 远程工作流

```bash
# 推送到 server
$ gaia push
Pushing galileo_tied_balls v1.0.0 ...
  Pushed → commit abc123 (pending_review)

# 触发审查（server 自动: 推断边类型、检测矛盾、估计 prior、LLM review）
$ gaia review abc123
  Review started.

# 查看进度
$ gaia status abc123
  Status: reviewing... [3/6 packages reviewed]

$ gaia status abc123
  Status: reviewed ✓
  Run `gaia publish abc123` to make it live.

# 入图发布（server 自动: merge + BP）
$ gaia publish abc123
  Publishing...

$ gaia status abc123
  Status: published ✓  BP complete.
```

### 4.5 查询

```bash
gaia show <id>                 # 查看 claim/节点详情
gaia search "query"            # 语义搜索
  --type <string>              # 过滤类型
  --k <int>                    # 返回数量 (default: 10)
gaia subgraph <id>             # 查看子图
  --hops <int>                 # 跳数 (default: 2)
  --direction <in|out|both>    # 方向
```

### 4.6 API 映射

| CLI 命令 | Server API | 说明 |
|----------|-----------|------|
| `gaia push` | `POST /commits` | 提交 commit |
| `gaia review <id>` | `POST /commits/{id}/review` | 触发异步审查 |
| `gaia status <id>` | `GET /commits/{id}` + `GET /jobs/{job_id}` | 查进度 |
| `gaia publish <id>` | `POST /commits/{id}/merge` | 入图 + BP |
| `gaia show <id>` | `GET /nodes/{id}` | 查看节点 |
| `gaia search "..."` | `POST /search/nodes` | 语义搜索 |
| `gaia subgraph <id>` | `GET /nodes/{id}/subgraph/hydrated` | 子图 |

---

## 5. 工作流

### 5.1 纯本地工作流（个人研究 / Agent 探索）

```bash
$ gaia init my_research

$ gaia claim "石头比树叶落得快" --type observation
  Created claim 1

$ gaia claim "亚里士多德自然运动学说" --type premise
  Created claim 2

$ gaia claim "v ∝ W" --cite 1,2 --why "从观察归纳" --type theory
  Created claim 3

$ gaia build
  ✓ 3 claims, all references valid

$ gaia commit -m "aristotle physics"
  Committed 3 claims.
  BP: claim 3 (v∝W) belief=0.70

$ gaia show 3
  "v ∝ W" | type: theory | belief: 0.70
  cited: 1, 2

# 继续添加矛盾性 claim，即时看到 belief 变化
$ gaia claim "推导A: 绑球组合更慢" --cite 3,4 --why "轻球拖拽重球"
$ gaia claim "推导B: 绑球组合更快" --cite 3,4 --why "组合体更重"
$ gaia commit -m "tied balls paradox"
  BP: claim 3 (v∝W) 0.70→0.35 ↓  矛盾回传
```

不需要远程 server，本地即时推理。

### 5.2 本地 + 远程工作流（团队协作）

```
本地                                       远程 Server
────────────────                     ────────────────────
gaia init
    ↓
gaia claim (交互式)
或 编辑 packages/*.yaml
    ↓
gaia build (结构校验)
    ↓
gaia commit (本地图 + 本地 BP)
    ↓ 本地已有 belief 结果
gaia push ──────────────────────→ pending_review
                                       ↓
gaia review <id> ───────────────→ LLM 审查
                                   · LLM 精估 prior
                                   · 深度矛盾检测
                                   · 质量评估
                                       ↓
gaia status <id> ───────────────→ 查询进度
                                       ↓
gaia publish <id> ──────────────→ merge + 大规模 BP
                                       ↓
                                   belief 更新完成
```

---

## 6. Canonical Example: Galileo's Tied Balls

```bash
# ──────────────────────────────────────────────────────
# 初始化
# ──────────────────────────────────────────────────────

$ gaia init galileo_tied_balls
Created package galileo_tied_balls/

# 编辑 gaia.toml 和 packages/*.yaml（见第3节格式）
# ...

# ──────────────────────────────────────────────────────
# 校验 + 提交
# ──────────────────────────────────────────────────────

$ gaia build
Checking galileo_tied_balls v1.0.0 ...
  ✓ aristotle_physics: 3 claims
  ✓ galileo1638_tied_balls: 5 claims
  ✓ galileo1638_medium_density: 3 claims
  ✓ galileo1638_vacuum_prediction: 3 claims
  ✓ newton1687_principia: 3 claims
  ✓ apollo15_1971_feather_drop: 3 claims
  ✓ All cite references valid
  ✓ Dependency DAG valid
Build succeeded: 20 claims across 6 packages.

$ gaia commit -m "Galileo: from Aristotle to Apollo 15"
Committed 20 claims to local graph.
Running local BP...

  Package: aristotle_physics
    5003 (v ∝ W): belief = 0.70

  Package: galileo1638_tied_balls
    5003 (v ∝ W): 0.70 → 0.35 ↓  contradiction backpropagation
    5008 (定律错误): belief = 0.82 ↑

  Package: galileo1638_medium_density
    5003 (v ∝ W): 0.35 → 0.28 ↓

  Package: newton1687_principia
    5017 (a = g): belief = 0.93 ↑
    5003 (v ∝ W): 0.28 → 0.12 ↓  second contradiction

  Package: apollo15_1971_feather_drop
    5003 (v ∝ W): 0.12 → 0.05 ↓  nearly zero
    5012 (真空等速): belief = 0.95 ↑  three lines converge
    5020 (Apollo 15): belief = 0.98 ↑  definitive

BP converged in 12 iterations.

# 纯本地使用到此即可。想推到远程则继续：

# ──────────────────────────────────────────────────────
# （可选）推送 + 审查 + 发布
# ──────────────────────────────────────────────────────

$ gaia push
Pushing galileo_tied_balls v1.0.0 ...
  Pushed → commit abc123

$ gaia review abc123
Review started.

$ gaia status abc123
  reviewed ✓
  Summary:
    · 20 nodes, 15 edges inferred (2 contradictions detected)
    · LLM re-estimated priors (3 adjusted)
    · Review: pass

$ gaia publish abc123
  Published ✓  Server BP complete.

# ──────────────────────────────────────────────────────
# 查询结果
# ──────────────────────────────────────────────────────

$ gaia show 5003
  "亚里士多德定律: v ∝ W"
  type: theory | belief: 0.05
  cited by: 5005, 5006 (deduction)
  contradicted by: 5007, edge to 5017

$ gaia subgraph 5003 --hops 2
  5001 ──→ 5003 ──→ 5005 ──→ 5007 (contradiction)
  5002 ──↗        ──→ 5006 ──↗
                  ↔ 5017 (contradiction)

$ gaia search "矛盾"
  1. edge 5004: [5005, 5006] → contradiction (tied balls paradox)
  2. edge 5011: [5003, 5017] → contradiction (Newton vs Aristotle)
```

---

## 7. 本地 vs 远程职责分工

### 7.1 本地 CLI（内嵌推理引擎）

`gaia commit` 时自动完成：

| 步骤 | 说明 |
|------|------|
| **边类型推断** | 根据 claim type 和 cite 关系推断边类型 |
| **矛盾检测** | 基于引用结构检测矛盾（同一前提推出相反结论） |
| **Prior 分配** | 根据 claim type 分配默认 prior（observation=0.90, premise=0.70, theory=0.70, deduction=由 BP 算, experiment=0.95） |
| **BP 推理** | 本地 Belief Propagation，即时计算 belief |

本地推理对 Agent 探索尤其重要 — Agent 可以快速添加 claim、观察 belief 变化、发现矛盾，无需等待远程。

### 7.2 远程 Server（增强层）

`gaia review` / `gaia publish` 时额外完成：

| 步骤 | 说明 |
|------|------|
| **LLM Prior 精估** | 根据来源可靠性、领域权威性重新估计 prior |
| **深度矛盾检测** | LLM 识别语义层面的隐含矛盾 |
| **质量审查** | LLM 检查推理有效性、引用合理性、新颖性 |
| **大规模 BP** | 在十亿级知识图谱上运行 BP |

---

## 8. 架构

```
                    ┌──────────────────┐
                    │     Gaia CLI     │
                    │  claim/commit/   │
                    │  push/show       │
                    └──────┬───────────┘
                           │
              ┌────────────┼────────────┐
              │ (内嵌)     │            │ (远程, 可选)
              ▼            │            ▼
    ┌──────────────┐       │   ┌──────────────────┐
    │  Local Graph │       │   │  Gaia Server     │
    │  LanceDB+Kuzu│       │   │  (LKM)           │
    └──────┬───────┘       │   └────────┬─────────┘
           │               │            │
           ▼               │            ▼
    ┌──────────────┐       │   ┌──────────────────┐
    │ 本地推理引擎   │       │   │ · LLM Prior 精估  │
    │ · 边类型推断   │       │   │ · 深度矛盾检测     │
    │ · 矛盾检测    │       │   │ · LLM Review     │
    │ · 默认 Prior  │       │   │ · 大规模 BP       │
    │ · BP 推理     │       │   └──────────────────┘
    └──────────────┘       │
                           │
    ┌──────────────┐       │
    │ libs/models  │◄──────┘   CLI 直接 import，无需 HTTP
    │ libs/storage │
    │ inference_   │
    │   engine     │
    └──────────────┘
```

本地模式：CLI 直接 import `libs/` 和 `services/inference_engine/`，内嵌运行，像 git 一样无需启动 server。
远程模式：CLI 通过 HTTP 调用 Gaia Server，获得 LLM review 和大规模 BP 增强。

---

## 9. 配置

### 9.1 全局配置 `~/.gaia/config.toml`

```toml
[user]
name = "Kun Chen"
email = "kun@example.com"

[remote]
default = "http://localhost:8000"
```

### 9.2 项目配置 `gaia.toml`

见第 3.1 节。

---

## 10. 命令速查

```
gaia init [name]                              创建知识包
gaia claim "结论" [--cite ids] [--why "理由"]    提出主张
         [--type T]
gaia build                                    结构校验
gaia commit -m "msg"                          提交到本地图
gaia push                                     推到 server
gaia review <commit_id>                       触发审查
gaia publish <commit_id>                      入图发布
gaia status [commit_id]                       查看状态/进度
gaia show <id>                                查看节点详情
gaia search "query" [--type T] [--k N]        语义搜索
gaia subgraph <id> [--hops N]                 查看子图
```

---

## 11. 与 v1 的主要变化

| v1 | v2 | 理由 |
|----|-----|------|
| `gaia node add` + `gaia edge add` | `gaia claim` | 用户只需表达主张，不需要手动建边 |
| 用户手动设置 `prior` / `probability` | 本地按类型自动分配，远程 LLM 精估 | 降低用户认知负担 |
| `gaia propagate` (单独命令) | `gaia commit` 自动触发 BP | 减少步骤 |
| `gaia test` (belief 断言) | 删除，校验合并到 `build` | build 做结构校验即可 |
| `gaia publish` (推到 server) | `gaia push` | 更符合 git 语义 |
| `gaia merge` (入图) | `gaia publish` | publish = 正式发布到知识图谱 |
| YAML 中 `nodes:` + `edges:` | `claims:` | 统一为 claim-centric 格式 |
| 本地无推理 | 本地完整 BP | Agent 需要即时推理反馈 |
| 必须连接 server | 纯本地可用，远程可选 | 像 git 一样开箱即用 |
