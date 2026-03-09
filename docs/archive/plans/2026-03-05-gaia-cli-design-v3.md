# Gaia CLI & Knowledge Package 统一设计文档 v3

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-06 |
| 状态 | Approved (brainstorm) |
| 基于 | v2 + 6 section brainstorm + review 系统讨论 |
| 关联 | `docs/examples/galileo_tied_balls.md`, `docs/examples/einstein_elevator.md`, `docs/plans/2026-03-06-review-system-design.md` |

---

## 1. Architecture — 四个组件

```
┌─────────────────┐     ┌──────────┐     ┌──────────────┐     ┌───────────────────┐
│  Research Agent  │ ←→  │ Gaia CLI │ ←→  │     Git      │ ←→  │     GitHub        │
│  (AI 科研助手)   │     │  (local) │     │ (版本控制)    │     │ (package 托管)    │
└─────────────────┘     └────┬─────┘     └──────────────┘     └────────┬──────────┘
                             │                                         │
                             │ gaia publish --server                   │ webhook / 定时拉取
                             ▼                                         ▼
                     ┌───────────────────────────────────────────────────────┐
                     │                    Gaia Server (LKM)                  │
                     │  LLM Review · Prior 精估 · 全局 BP · 跨包矛盾检测      │
                     │  知识输出: 论文 · 百科 · 综述 · 科普 · 教材 · FAQ        │
                     └───────────────────────────────────────────────────────┘
```

**职责分离：**

| 组件 | 职责 | 不做什么 |
|------|------|---------|
| **Gaia CLI** | claim、build、review、本地 BP、查询 | 版本控制、远程托管 |
| **Git** | 版本控制、分支、历史 | 知识语义、推理 |
| **GitHub** | 代码托管、PR、collaboration | 知识推理、review |
| **Gaia Server** | LLM review、prior 精估、全局 BP、知识输出 | 修改包内容（只读消费者） |

**设计原则：**

- **Agent-first** — AI agent 是主要用户，通过 bash 调用 CLI，解析 JSON 输出
- **本地完整，远程增强** — 本地内嵌 LanceDB + Kuzu + BP，开箱即用；远程可选
- **1 package = 1 git repo** — 可直接 host 到 GitHub
- **Gaia 不包装 git** — 版本控制完全交给 git，Gaia 只管知识操作

---

## 2. Package Structure — 知识包格式

### 2.1 目录结构

```
galileo_tied_balls/           # = 1 git repo
├── gaia.toml                 # 包清单 + 远程配置
├── gaia.lock                 # 依赖锁定（自动生成）
└── claims/
    ├── 001_aristotle_physics.yaml
    ├── 002_tied_balls.yaml
    ├── 003_medium_density.yaml
    ├── 004_vacuum_prediction.yaml
    ├── 005_newton_principia.yaml
    └── 006_apollo15_feather_drop.yaml
```

### 2.2 `gaia.toml`

```toml
[package]
name = "galileo_tied_balls"
version = "1.0.0"
description = "From Aristotle to Apollo 15: overturning 'heavier falls faster'"
authors = ["Galileo Galilei", "Isaac Newton"]

[remote]
mode = "server"                # "server" | "github" | "both"
server_url = "https://gaia.example.com"
registry = "github.com/gaia-registry/packages"

[related]
newton_mechanics = { repo = "github.com/user/newton_mechanics", note = "经典力学基础" }
```

### 2.3 Claim YAML 格式

```yaml
# claims/002_tied_balls.yaml
claims:
  - id: 5004
    type: axiom
    content: "思想实验设定: 用绳子把重球 H 绑在轻球 L 上"

  - id: 5005
    type: deduction
    content: "推导 A: 轻球拖拽重球 → 组合体 HL 比 H 慢"
    premise: [5003, 5004]           # 强引用：前提错则结论错，参与 BP
    why: "按 v∝W 定律，L 慢于 H，L 会拖拽 H"

  - id: 5006
    type: deduction
    content: "推导 B: 组合体更重 → 组合体 HL 比 H 快"
    premise: [5003, 5004]           # 强引用
    why: "按 v∝W 定律，HL 总重量 > H，应更快"

  - id: 5007
    type: deduction
    content: "同一物体不可能既比 H 快又比 H 慢 — 矛盾"
    premise: [5005, 5006]           # 强引用
    context: []                     # 弱引用：背景知识，折入 prior
    why: "两个有效推导从同一前提得出互相矛盾的结论"
```

### 2.4 强引用（premise）与弱引用（context）

```yaml
  - id: 6009
    content: "光在引力场弯曲"
    premise: [6008, 6005]               # 强引用：错则结论错，参与 BP
    context: [6003]                     # 弱引用：背景知识，折入 prior
    why: "等效原理 + Maxwell 电磁理论 → 光必须沿弯曲路径传播"
```

| 类型 | 字段 | 数学处理 | BP 参与 |
|------|------|---------|--------|
| 强引用 | `premise` | hyperedge tail，P(C\|premises) | 是 |
| 弱引用 | `context` | 折入 claim prior | 否 |
| 无关 | — | 删除 | 否 |

**判断标准：** 如果这个 premise 是错的，conclusion 还能成立吗？不能 → `premise`，能 → `context`。

### 2.5 跨包引用

强引用和弱引用均支持跨包格式 `pkg:claim_id@commit`：

```yaml
  - id: 5012
    content: "真空中所有物体等速下落"
    premise:
      - 5008                           # 本包内强引用
      - galileo:5011@a1b2c3            # 跨包强引用
    context:
      - newton:F_eq@b2c3d4             # 跨包弱引用
    why: "空气阻力是混淆因素，去除后速度与质量无关"
```

### 2.6 `gaia.lock`（自动生成）

```toml
# gaia build 时自动从 premise: 字段解析生成
[packages.galileo]
repo = "github.com/user/galileo_tied_balls"
commit = "a1b2c3d4e5f6"
claims = [5011, 5008]             # 本包实际引用的 claim IDs

[packages.newton_mechanics]
repo = "github.com/user/newton_mechanics"
commit = "b2c3d4e5f6a7"
claims = []                        # 弱引用，无具体 claim
```

### 2.7 不可变性规则

- **已发布的 claim 不能修改/删除** — 像论文一样，一旦 publish 就是永久记录
- **修正方式** — 新 claim + contradiction 边指向旧 claim
- **Lock file 锁定 commit hash** — 保证可复现，不依赖 semver
- **版本号在包级别** — semver 可用但不强制，安全性来自 immutability + lock

---

## 3. CLI Commands — 命令集

### 3.1 核心命令

```
gaia init [name]              # 初始化 knowledge package
gaia claim "结论" --why "推理" --premise id1,id2 [--context id3]
                              # 添加一条命题（自动创建 node + edge）
gaia build                    # 结构校验 + 本地 BP（快，离线）
gaia review [id...]           # 调大模型评审（慢，需 API key）
gaia show <id>                # 查看命题详情（belief, 引用链）
gaia search "query"           # 语义搜索（向量 + BM25）
gaia subgraph <id>            # 查看以某命题为中心的子图
gaia contradictions           # 列出所有矛盾对
gaia stats                    # 包统计（节点数、边数、belief 分布）
gaia publish                  # 发布到远程（唯一的远程命令）
```

### 3.2 `gaia claim` 详解

```bash
# 叶子命题（无引用，直接观察/引用文献）
$ gaia claim "石头比树叶落得快" --type observation
  Created claim 5001

# 有引用的命题
$ gaia claim "v ∝ W 定律" \
    --premise 5001,5002 \
    --why "从学说和观察归纳出定量规律" \
    --type theory
  Created claim 5003

# 矛盾声明
$ gaia claim "v∝W 自相矛盾" --type contradiction --premise 5005,5006
  Created claim 5007

# 带弱引用（背景知识）
$ gaia claim "光在引力场弯曲" \
    --premise 6008,6005 --context 6003 \
    --why "等效原理 + Maxwell → 光沿弯曲路径传播"
  Created claim 6009
```

**claim type 参考：**

| type | 说明 | 例子 |
|------|------|------|
| `observation` | 直接观察/实验数据 | "石头快于树叶" |
| `axiom` | 已有理论/学说/公理 | "亚里士多德自然运动学说" |
| `theory` | 归纳/抽象出的理论 | "v ∝ W 定律" |
| `deduction` | 逻辑推导 | "组合体应更慢" |
| `prediction` | 理论预测 | "真空中所有物体等速下落" |
| `experiment` | 实验验证 | "Apollo 15 锤子=羽毛" |
| `contradiction` | 矛盾声明 | "两个推导互相矛盾" |

### 3.3 设计要点

1. **`claim` 是唯一的写入命令** — 同时创建 node + edge，Agent 不需要理解图结构
2. **`build` = 校验 + BP** — 快速、离线。检查 YAML 格式、引用完整性，跑本地 BP
3. **`review` = 大模型评审** — 慢、需 API key。可指定 claim ID 或全包。内部并发调 API，逐条流式输出
4. **无 `commit`/`push`** — 版本控制完全交给 git
5. **`--premise` 支持跨包引用** — 格式 `pkg:claim_id@commit`
6. **所有命令支持 `--json` 输出** — Agent 解析 JSON，人类看默认 pretty-print
7. **`search` 在本地运行** — 使用嵌入式 LanceDB

---

## 4. Workflows — 工作流

### 4.1 纯本地（Agent 日常使用）

```bash
gaia init galileo_tied_balls
gaia claim "越重的物体下落越快" --why "亚里士多德经验观察" --premise aristotle:physics
gaia claim "重球绑轻球，整体应更慢" --why "轻球拖累重球" --premise 1
gaia claim "重球绑轻球，整体应更快" --why "总重量更大" --premise 1
gaia claim "v∝W 自相矛盾" --type contradiction --premise 2,3
gaia build              # 本地 BP → belief 变化摘要
gaia contradictions     # 查看矛盾列表
gaia show 4             # 查看矛盾详情
git add . && git commit -m "tied_balls experiment"
```

### 4.2 发布到远程

```bash
# 模式 A: GitHub（国际用户，Julia 模式）
gaia publish --git       # git push + 自动 PR 到 registry repo

# 模式 B: 直连 Server（国内用户）
gaia publish             # 调用 Server API

# 模式 C: 两者都做
gaia publish --all       # 同时推送
```

无参数时按 `gaia.toml` 中 `[remote] mode` 走默认路径。`--git` / `--server` 可临时覆盖。

### 4.3 Server 远程流程

```
gaia publish
  → POST /commits（提交数据）
  → Server 异步: LLM review + prior 估算 + 全局 BP
  → 返回 review 结果
```

- GitHub 模式: registry repo 更新 → Server webhook/定时拉取 → clone 包 → 索引
- Server 模式: `gaia publish` 直接推送

### 4.4 工作流要点

1. **Local 完全自足** — Agent 只用 `claim` + `build` + 查询，不需要网络
2. **Git 是版本控制** — Gaia 不碰 `commit`/`push`/`branch`
3. **`publish` 是唯一的远程命令** — 支持 git / server / both 三种目标
4. **Server 增值** — LLM review、prior 估算、跨包矛盾检测、全局 BP

---

## 5. Gaia Server（Large Knowledge Model）

### 5.1 核心职责

| 能力 | 说明 |
|------|------|
| **LLM Review** | 审查命题质量、推理逻辑、引用合理性 |
| **Prior 估算** | 基于领域知识为命题分配先验概率 |
| **全局 BP** | 十亿级超图上的 belief propagation，跨所有包 |
| **跨包矛盾检测** | 发现不同包之间的命题冲突 |
| **语义搜索** | 全量向量索引，比本地单包搜索范围大得多 |
| **知识输出** | 基于超图生成论文、百科、综述、科普、教材、FAQ |

### 5.2 数据获取方式

```
GitHub 模式:
  registry repo 更新 → Server webhook/定时拉取 → clone 包 → 索引

Server 模式:
  gaia publish → POST /commits → Server 直接接收数据
```

### 5.3 Server API（复用现有）

| CLI 命令 | Server API | 说明 |
|----------|-----------|------|
| `gaia publish` | `POST /commits` | 提交数据 |
| — | `POST /commits/{id}/review` | 触发 LLM review（自动） |
| — | `POST /commits/{id}/merge` | 合并到全局超图（自动） |
| `gaia search "..."` | `POST /search/nodes` | 全局语义搜索 |
| `gaia show <id>` | `GET /nodes/{id}` | 查看节点 |
| `gaia subgraph <id>` | `GET /nodes/{id}/subgraph/hydrated` | 子图 |
| `gaia contradictions` | `GET /contradictions` | 跨包矛盾列表 |

### 5.4 设计要点

1. **Server 是只读消费者** — 索引包，不修改包内容。包的权威来源是 git repo
2. **Review 非阻塞** — publish 提交后可异步完成
3. **现有 API 基本够用** — 当前 FastAPI 后端已实现核心接口
4. **本地 ≠ 弱化版 Server** — 本地有完整 BP，只是范围限于单包；Server 的优势是全局视野

---

## 6. Cross-Package References — 跨包引用与依赖

### 6.1 强引用（claim 级别，BP 传播）

```yaml
premise:
  - 5008                           # 本包内
  - galileo:5011@a1b2c3            # 跨包: pkg:claim_id@commit
```

- 出现在 claim 的 `premise:` 字段中
- `gaia build` 解析后写入 `gaia.lock`
- Server 全局 BP 时，跨包引用参与概率传播

### 6.2 弱引用（claim 级别 + 包级别）

**Claim 级别** — `context` 字段，折入 claim prior，不参与 BP：

```yaml
  - id: 6009
    content: "光在引力场弯曲"
    premise: [6008, 6005]
    context: [6003]                    # 弱引用：Maxwell 方程作为背景
```

**包级别** — `gaia.toml` 的 `[related]`，仅供 Server 发现相关包：

```toml
# gaia.toml
[related]
newton_mechanics = { repo = "github.com/user/newton_mechanics", note = "经典力学基础" }
```

- `context` 支持跨包格式 `pkg:claim_id@commit`
- `[related]` 无需精确到 claim，仅用于包发现

### 6.3 Lock File

```toml
# gaia.lock（gaia build 自动生成/更新）
[packages.galileo]
repo = "github.com/user/galileo_tied_balls"
commit = "a1b2c3d4e5f6"
claims = [5011, 5008]

[packages.newton_mechanics]
repo = "github.com/user/newton_mechanics"
commit = "b2c3d4e5f6a7"
claims = []                        # 弱引用
```

### 6.4 依赖规则

1. **`premise:` 中的跨包引用** → `gaia build` 自动解析，写入 `gaia.lock`
2. **Lock file 锁定 commit hash** — 保证可复现，不依赖 semver
3. **命题不可变** — 已发布的 claim 不能修改/删除，修正通过新 claim + contradiction
4. **`gaia build` 检查引用完整性** — 被引用的 claim 必须存在于对应 commit 中
5. **版本号在包级别** — `gaia.toml` 中 `version = "1.2.0"`，semver 可用但不强制

---

## 7. Review System — 推理质量评审

> 详细设计见 `docs/plans/2026-03-06-review-system-design.md`

### 7.1 Review 的核心目标

评估一条推理链的条件概率 **P(conclusion | premises)**：假设所有强引用（`premise`）都成立，这步推理有多可靠？

### 7.2 Review Skill（公开协议）

Review 是一个版本化的 prompt（skill），定义标准化的输入输出：

**输入：**
```yaml
claim:
  content: "同一物体不可能既比 H 快又比 H 慢 — 矛盾"
  type: deduction
  why: "两个有效推导从同一前提得出互相矛盾的结论"
  premise:                         # 强引用，展开为完整内容
    - { id: 5005, content: "推导 A: HL 比 H 慢" }
    - { id: 5006, content: "推导 B: HL 比 H 快" }
  context: []                      # 弱引用（本例无）
```

**输出：**
```yaml
score: 0.95                        # P(conclusion | premises)
justification: "纯逻辑演绎，无跳步"
confirmed_premises: [5005, 5006]   # 确认的强引用 → 参与 BP
downgraded_premises: []            # 应降级为 context
upgraded_context: []               # 应升级为 premise
irrelevant: []                     # 建议删除
suggested_premise: []              # 从 why 中提取的隐含强依赖
suggested_context: []              # 可能相关的引文，建议作为弱引用
```

**评估标准：**

1. **相关性** — 每个强引用是否真的是强依赖（错了结论就不成立）？
2. **逻辑有效性** — 推理是否有效？有无跳步？
3. **充分性** — 前提是否足够？是否缺少隐含前提？
4. **推理类型匹配** — 声称的 type 是否与实际推理一致？

### 7.3 三种 Review 场景

| 场景 | 触发方式 | 执行者 | 结果存储 |
|------|---------|--------|---------|
| **本地** | `gaia review [id...]` | 用户自选模型 | 仅本地，用于本地 BP |
| **GitHub 模式** | PR 到 registry repo | Server（webhook 触发） | Server DB + GitHub PR 评论 |
| **Server 直连** | `gaia publish` | Server | Server DB |

本地 `gaia review` 与 `gaia build` 分离：`build` 快速离线（校验 + BP），`review` 调大模型（慢，需 API key）。支持指定 claim ID 或全包 review，内部并发调 API，逐条流式输出。

### 7.4 GitHub Review Bot 流程

```
用户 PR 到 registry repo
  → Server webhook 触发
  → Server clone 包，用自己的 model 跑 review skill
  → Server 在 PR 下评论 review 结果
  → 通过 → auto-merge；不通过 → request changes
```

**关键设计：发布与评审分离。** GitHub 是发布平台（类似 arXiv），Server 是独立审稿方（类似期刊）。用户没有动机也没有机会篡改 review 结果。

### 7.5 用户激励

```
用 gaia 格式发布到 GitHub
  → 自动获得免费 AI peer review
  → Review 结果公开，增加可信度
  → 被 Server 索引，进入全局知识图谱
  → 被更多人 cite，扩大影响力
```

---

## 8. Canonical Example: Galileo Workflow (updated)

```bash
# 初始化
$ gaia init galileo_tied_balls

# 编辑 claims/*.yaml（见 Section 2.3 格式）
# ...

# 校验 + 本地推理
$ gaia build
  ✓ 20 claims across 6 files
  ✓ All premise references valid
  ✓ Dependency DAG valid
  BP results:
    5003 (v∝W): 0.70 → 0.05 ↓  (2 contradictions)
    5012 (真空等速): 0.95 ↑
    5020 (Apollo 15): 0.98 ↑

# 查看矛盾
$ gaia contradictions
  1. claims 5005 ↔ 5006 (tied balls paradox)
  2. claims 5003 ↔ 5017 (Newton F=ma vs Aristotle v∝W)

# Git 版本控制
$ git add . && git commit -m "galileo tied balls"
$ git push origin main

# 发布到远程
$ gaia publish
  Published to server. Review started...
  6004 → Newton 0.87″: belief=0.10 ↓↓
  6014 → GR 1.75″: belief=0.95 ↑↑
```

---

## 9. 技术选型

| 层面 | 选择 | 理由 |
|------|------|------|
| CLI 语言 | Python 3.12+（MVP），后迁 Rust | 复用现有 libs/，快速迭代 |
| 本地存储 | LanceDB (嵌入式) | 向量搜索 + BM25，零配置 |
| 本地图 | Kuzu (嵌入式) | Cypher 支持，零配置 |
| 本地推理 | 复用 `services/inference_engine/` | BP 已实现 |
| Agent 接口 | bash + `--json` flag | Agent 通过 subprocess 调用 |
| 远程 Server | 现有 FastAPI 后端 | API 已实现 |
| 包托管 | GitHub (git repo) | 免费、成熟、国际化 |
| Registry | Julia 模式 (registry = git repo) | 可演进到 Cargo 模式 |

---

## 10. 与 v2 的主要变化

| v2 | v3 | 理由 |
|----|-----|------|
| `gaia commit` + `gaia push` | 删除，用 git | Gaia 不包装 git |
| `gaia push` + `gaia review` + `gaia publish` | 统一为 `gaia publish` | 一个远程命令 |
| 远程只有 server 模式 | GitHub + Server + Both | 国际/国内双轨 |
| 无跨包引用格式 | `pkg:claim_id@commit` | 强引用支持 BP 传播 |
| 无 lock file | `gaia.lock` 自动生成 | 可复现性 |
| 无弱引用 | `[related]` in gaia.toml | 包发现 |
| 无不可变性规则 | claim 一经发布不可修改 | 知识可靠性 |
| cite 不分强弱 | `premise`（强）+ `context`（弱） | 强引用参与 BP，弱引用折入 prior |
| 无 review 系统 | Review Skill 公开协议 + Server bot | 透明、可复现的推理质量评审 |
| Server 做所有 review | 发布与评审分离（GitHub=arXiv, Server=期刊） | 解决激励问题 |
