# Gaia CLI 设计文档

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-05 |
| 状态 | Draft |
| 关联 | `docs/examples/galileo_tied_balls.md`, `docs/examples/einstein_elevator.md` |

---

## 1. 概述

Gaia CLI 是 Gaia 知识超图系统的命令行包管理工具，类比 Cargo (Rust) / npm (Node.js)，但管理的对象是 **知识包 (knowledge package)** 而非代码。知识包由命题节点 (Node)、推理超边 (HyperEdge) 和元数据组成，入图后通过 Belief Propagation (BP) 自动更新置信度。

**设计原则：**

- **声明式包文件 + 交互式命令**：复杂推理链用包文件声明（可复现、可版本化），探索/查询用交互命令
- **本地优先，远程可选**：本地图即开即用（LanceDB + Kuzu），通过 `publish` 推送到远程 registry
- **完整暴露 commit → review → merge 三步流程**：远程提交保留 server 端完整审查链路
- **BP 是一等公民**：propagate、belief 查询、contradiction 管理都有专用命令

---

## 2. 核心概念

### 2.1 Knowledge Package

知识包是 Gaia 中知识的分发单元，等价于 Cargo 中的 crate。一个包包含：

- **元数据** (`gaia.toml`)：名称、版本、描述、作者、sub-package 顺序与依赖
- **Sub-packages**：按时序或逻辑分组的节点+边集合（`packages/*.yaml`）
- **Belief 断言** (`beliefs.yaml`, 可选)：每个 sub-package 执行后的期望 belief 区间，用于验证

### 2.2 Registry

远程知识图谱服务（即 Gaia FastAPI 后端）。包通过 `gaia publish` 提交到 registry，经过 review → merge 流程后入图。类比 npm registry / crates.io。

### 2.3 本地图

本地嵌入式存储（LanceDB + Kuzu），无需启动服务即可操作。`gaia commit` 直接写入本地图，`gaia propagate` 在本地运行 BP。

### 2.4 Staging Area

交互式 `gaia node add` / `gaia edge add` 命令会将操作暂存到 staging area，类似 `git add`。通过 `gaia commit` 或 `gaia publish` 将暂存操作提交。

---

## 3. 包目录结构

```
galileo_tied_balls/
├── gaia.toml                              # 包清单
├── packages/
│   ├── aristotle_physics.yaml             # Sub-package 1: 已有知识
│   ├── galileo1638_tied_balls.yaml        # Sub-package 2: 绑球悖论
│   ├── galileo1638_medium_density.yaml    # Sub-package 3: 空气阻力
│   ├── galileo1638_vacuum_prediction.yaml # Sub-package 4: 真空预测
│   ├── newton1687_principia.yaml          # Sub-package 5: 牛顿力学
│   └── apollo15_1971_feather_drop.yaml    # Sub-package 6: 月球实验
└── beliefs.yaml                           # 可选: 期望 belief 断言
```

### 3.1 `gaia.toml` — 包清单

```toml
[package]
name = "galileo_tied_balls"
version = "1.0.0"
description = "From Aristotle to Apollo 15: overturning 'heavier falls faster' across 2300 years"
authors = ["Galileo Galilei", "Isaac Newton"]

# Sub-packages 按 order 顺序提交，depends_on 声明前置依赖
[[packages]]
name = "aristotle_physics"
order = 1
description = "Aristotle's natural motion doctrine and everyday observations"
depends_on = []

[[packages]]
name = "galileo1638_tied_balls"
order = 2
description = "The tied-balls paradox: reductio ad absurdum of Aristotle's law"
depends_on = ["aristotle_physics"]

[[packages]]
name = "galileo1638_medium_density"
order = 3
description = "Medium density observations: air resistance as confounding variable"
depends_on = ["aristotle_physics"]

[[packages]]
name = "galileo1638_vacuum_prediction"
order = 4
description = "Vacuum prediction + inclined plane partial confirmation"
depends_on = ["galileo1638_tied_balls", "galileo1638_medium_density"]

[[packages]]
name = "newton1687_principia"
order = 5
description = "F=ma + F=mg → a=g: theoretical derivation independent of Galileo"
depends_on = ["aristotle_physics"]

[[packages]]
name = "apollo15_1971_feather_drop"
order = 6
description = "Definitive lunar experiment: hammer and feather fall together"
depends_on = ["galileo1638_vacuum_prediction", "newton1687_principia"]

[dependencies]
# 外部包依赖（类似 Cargo 的 crate 依赖）
# newtonian_mechanics = "^1.0"

[remote]
registry = "http://localhost:8000"
```

### 3.2 Sub-package YAML 格式

每个 sub-package 文件声明该步骤引入的节点和边。

**`packages/aristotle_physics.yaml`**

```yaml
nodes:
  - id: 5001
    type: paper-extract
    subtype: premise
    title: "Aristotle's natural motion doctrine"
    content: >
      亚里士多德自然运动学说: 每个物体都有其自然位置，
      土性物体向下运动，速度由其本性（重量）决定。
    prior: 0.70
    keywords: [Aristotle, natural-motion, falling-bodies]
    metadata:
      source: "Aristotle, Physics IV.8, 215a-216a (~350 BCE)"

  - id: 5002
    type: paper-extract
    subtype: premise
    title: "Everyday observation: stone falls faster than leaf"
    content: "日常观察: 石头比树叶落得快。越重的物体在日常经验中看起来确实下落越快。"
    prior: 0.90
    keywords: [observation, falling-bodies, everyday-experience]

  - id: 5003
    type: paper-extract
    subtype: conclusion
    title: "Aristotle's law of falling bodies"
    content: "亚里士多德定律: 下落速度正比于重量 (v ∝ W)。越重的物体比越轻的下落越快。"
    prior: 0.70
    keywords: [Aristotle, law, v-proportional-W]

edges:
  - id: 5001
    type: abstraction
    tail: [5001, 5002]
    head: [5003]
    probability: 0.85
    reasoning:
      - title: "Generalization from doctrine and observation"
        content: >
          Aristotle generalizes from the doctrine of natural motion (node 5001)
          and everyday observation (node 5002) to the universal law v ∝ W (node 5003).
```

**`packages/galileo1638_tied_balls.yaml`**（含矛盾边示例）

```yaml
nodes:
  - id: 5004
    type: conjecture
    subtype: premise
    title: "Tied balls setup"
    content: "思想实验设定: 用绳子把重球 H 绑在轻球 L 上，考虑组合体 HL"
    prior: 0.99

  - id: 5005
    type: deduction
    subtype: conclusion
    title: "Deduction A: combined falls slower"
    content: "推导 A: 轻球拖拽重球 → 组合体 HL 下落比 H 慢"
    prior: 0.90

  - id: 5006
    type: deduction
    subtype: conclusion
    title: "Deduction B: combined falls faster"
    content: "推导 B: 组合体更重 → 组合体 HL 下落比 H 快"
    prior: 0.90

  - id: 5007
    type: deduction
    subtype: conclusion
    title: "Contradiction in Aristotle's law"
    content: "矛盾：同一物体不可能既比 H 快又比 H 慢。亚里士多德定律自相矛盾。"
    prior: 0.95

  - id: 5008
    type: deduction
    subtype: conclusion
    title: "Galileo's rejection of Aristotle"
    content: "结论: 亚里士多德定律自相矛盾，必须抛弃。速度不可能正比于重量。"
    prior: 0.85

edges:
  - id: 5002
    type: deduction
    tail: [5003, 5004]
    head: [5005]
    probability: 0.95
    reasoning:
      - title: "Light ball drags heavy ball"
        content: "按亚里士多德定律: L 慢于 H → L 拖拽 H → 组合体比 H 慢"

  - id: 5003
    type: deduction
    tail: [5003, 5004]
    head: [5006]
    probability: 0.95
    reasoning:
      - title: "Combined is heavier"
        content: "按亚里士多德定律: HL 总重量 > H → 组合体比 H 快"

  # ★ 矛盾边: head 为空
  - id: 5004
    type: contradiction
    tail: [5005, 5006]
    head: []
    reasoning:
      - title: "Mutually exclusive predictions"
        content: "同一前提同一物体，两个有效推导得出矛盾结论"

  - id: 5005
    type: deduction
    tail: [5007, 5003]
    head: [5008]
    probability: 0.90
    reasoning:
      - title: "Error must lie in shared premise"
        content: "两条推导都有效 → 错误必在共享前提 → 亚里士多德定律必须被抛弃"
```

### 3.3 `beliefs.yaml` — Belief 断言

用于验证 BP 结果是否符合预期，类似单元测试。

```yaml
after_package:
  aristotle_physics:
    5003: [0.6, 0.8]

  galileo1638_tied_balls:
    5003: [0.2, 0.5]      # Aristotle's law drops
    5008: [0.7, 1.0]      # Galileo's rejection rises

  newton1687_principia:
    5017: [0.85, 0.98]    # a = g high confidence
    5003: [0.05, 0.25]    # Aristotle further suppressed

  apollo15_1971_feather_drop:
    5020: [0.9, 1.0]      # Lunar experiment confirmed
    5003: [0.01, 0.15]    # Aristotle nearly zero

final:
  5003: [0.01, 0.15]
  5012: [0.85, 1.0]
  5017: [0.85, 1.0]
  5020: [0.9, 1.0]
```

---

## 4. CLI 命令参考

### 4.1 包生命周期

| 命令 | 说明 | 类比 |
|------|------|------|
| `gaia init [name]` | 创建新包（生成 `gaia.toml` + `packages/`） | `cargo init` |
| `gaia build` | 校验包结构（节点引用、类型、依赖拓扑） | `cargo build` / `cargo check` |
| `gaia commit -m "msg"` | 提交到本地图（校验 + 合并，跳过 review） | `git commit` |
| `gaia propagate` | 在本地图上运行 Belief Propagation | — (Gaia 独有) |
| `gaia test` | 运行 `beliefs.yaml` 断言 | `cargo test` |

### 4.2 远程发布（commit → review → merge）

| 命令 | 说明 | API 映射 |
|------|------|----------|
| `gaia publish` | 提交到远程 registry | `POST /commits` |
| `gaia review <commit_id>` | 触发异步 LLM 审查 | `POST /commits/{id}/review` |
| `gaia review --status <id>` | 查看审查状态 | `GET /commits/{id}/review` |
| `gaia review --result <id>` | 查看审查详情 | `GET /commits/{id}/review/result` |
| `gaia review --cancel <id>` | 取消审查 | `DELETE /commits/{id}/review` |
| `gaia merge <commit_id>` | 审查通过后合并到图 | `POST /commits/{id}/merge` |

`gaia publish` 按 sub-package 顺序依次提交，每个 sub-package 作为一个 commit。返回所有 commit_id。

### 4.3 交互式操作

```bash
# --- 节点 ---
gaia node add "content" [options]
  --prior <float>              # 先验概率 (default: 1.0)
  --type <string>              # paper-extract | deduction | conjecture | abstraction
  --subtype <string>           # premise | conclusion | ...
  --title <string>             # 节点标题
  --keywords <k1,k2,...>       # 关键词列表
# → 输出: Created node <id>

gaia node show <id>            # 查看节点详情
gaia node list [--type T] [--min-belief 0.5] [--page 1] [--size 20]
gaia node modify <id> [--prior 0.8] [--status deleted]

# --- 边 ---
gaia edge add --tail <ids> --head <ids> [options]
  --type <string>              # deduction | abstraction | induction | contradiction
  --probability <float>        # 边概率
  --reasoning <json>           # 推理步骤 (JSON 数组)
# → 输出: Created edge <id>

# 矛盾边简写
gaia edge add --tail 5005,5006 --type contradiction
# head 默认为空

gaia edge show <id>
gaia edge list [--type T] [--page 1]
gaia edge modify <id> [--probability 0.9]
```

交互式添加的节点/边会暂存到 staging area，通过 `gaia commit` 或 `gaia publish` 提交。

```bash
gaia status                    # 查看 staging area 中待提交的操作
gaia reset                     # 清空 staging area
```

### 4.4 查询与探索

```bash
gaia search "query"            # 搜索节点 (POST /search/nodes)
  --edges                      # 搜索边 (POST /search/hyperedges)
  --k <int>                    # 返回数量 (default: 10)
  --type <string>              # 过滤类型
  --min-belief <float>         # 最低 belief 过滤

gaia belief <node_id>          # 查询节点当前 belief
gaia belief <id1> <id2> ...    # 批量查询

gaia subgraph <node_id>        # 获取子图 (GET /nodes/{id}/subgraph)
  --hops <int>                 # 跳数 (default: 2)
  --direction <in|out|both>    # 方向
  --max-nodes <int>            # 最大节点数

gaia contradictions            # 列出所有矛盾边 (GET /contradictions)
gaia stats                     # 图统计 (GET /stats)
```

### 4.5 远程管理

```bash
gaia remote add <url>          # 配置 registry URL
gaia remote list               # 列出已配置的 remote
gaia remote remove <name>      # 移除 remote
gaia login                     # 认证到 registry
gaia pull <package_name>       # 从 registry 拉取包到本地
```

---

## 5. 工作流

### 5.1 声明式工作流（构建知识包）

```
                    本地                              远程 Registry
              ──────────────                    ─────────────────────
              gaia init
                  ↓
              编辑 packages/*.yaml
                  ↓
              gaia build (校验)
                  ↓
         ┌──────────────────┐
         │  gaia commit      │─── 本地图 ──→ gaia propagate ──→ gaia test
         │  (本地快速路径)    │                (本地 BP)          (belief 断言)
         └──────────────────┘
                  ↓
              gaia publish ────────────────→ pending_review
                                                  ↓
              gaia review <id> ────────────→ LLM 审查 (异步)
              gaia review --status <id> ───→ 查询状态
                                                  ↓
              gaia merge <id> ─────────────→ merged + remote BP
                                                  ↓
                                              belief 更新结果返回
```

### 5.2 交互式工作流（探索式添加）

```bash
# 1. 添加节点
$ gaia node add "光的微粒说: 光是有质量的粒子" --prior 0.70 --type paper-extract
Created node 2

$ gaia node add "牛顿框架下光的引力偏折角 = 0.87 角秒" --prior 0.70 --type paper-extract
Created node 3

# 2. 添加边
$ gaia edge add --tail 1,2 --head 3 --type deduction --probability 0.60
Created edge 1

# 3. 查看暂存
$ gaia status
Staged operations:
  + node 2: "光的微粒说: 光是有质量的粒子"
  + node 3: "牛顿框架下光的引力偏折角 = 0.87 角秒"
  + edge 1: [1, 2] → [3] (deduction)

# 4. 提交到本地
$ gaia commit -m "Newtonian prior knowledge"
Committed 2 nodes, 1 edge to local graph.

# 5. 运行 BP
$ gaia propagate
Running belief propagation...
  node_2: belief 0.70
  node_3: belief 0.62

# 6. 发布到远程
$ gaia publish
Publishing to http://localhost:8000 ...
  Submitted commit abc123 (pending_review)
```

### 5.3 混合工作流

声明式和交互式可以混合使用。包文件提供基础结构，交互命令用于补充和调整。

```bash
# 从包文件提交主体知识
gaia build && gaia commit -m "Galileo tied balls packages 1-4"

# 交互式添加一条新的矛盾边
gaia edge add --tail 5003,5017 --type contradiction
gaia commit -m "Add Newton vs Aristotle contradiction"

# 运行 BP 观察变化
gaia propagate
gaia belief 5003 5017
```

---

## 6. Canonical Example: Galileo's Tied Balls

以下展示用 Gaia CLI 完整构建伽利略绑球悖论推理链的过程。

```bash
# ──────────────────────────────────────────────────────
# 初始化知识包
# ──────────────────────────────────────────────────────

$ gaia init galileo_tied_balls
Created package galileo_tied_balls/
  gaia.toml
  packages/

$ cd galileo_tied_balls

# 编辑 gaia.toml 和 packages/*.yaml（见第3节格式定义）
# ...

# ──────────────────────────────────────────────────────
# 校验
# ──────────────────────────────────────────────────────

$ gaia build
Checking galileo_tied_balls v1.0.0 ...
  ✓ aristotle_physics: 3 nodes, 1 edge
  ✓ galileo1638_tied_balls: 5 nodes, 4 edges (1 contradiction)
  ✓ galileo1638_medium_density: 3 nodes, 1 edge
  ✓ galileo1638_vacuum_prediction: 3 nodes, 3 edges
  ✓ newton1687_principia: 3 nodes, 3 edges (1 contradiction)
  ✓ apollo15_1971_feather_drop: 3 nodes, 3 edges
  ✓ Dependency graph is a valid DAG
  ✓ All node references resolve
Build succeeded: 20 nodes, 15 edges across 6 packages.

# ──────────────────────────────────────────────────────
# 本地提交 + BP（按 sub-package 顺序）
# ──────────────────────────────────────────────────────

$ gaia commit -m "Galileo's tied balls: complete reasoning chain"
Committing 6 packages in dependency order...
  [1/6] aristotle_physics: 3 nodes, 1 edge ✓
  [2/6] galileo1638_tied_balls: 5 nodes, 4 edges ✓
  [3/6] galileo1638_medium_density: 3 nodes, 1 edge ✓
  [4/6] galileo1638_vacuum_prediction: 3 nodes, 3 edges ✓
  [5/6] newton1687_principia: 3 nodes, 3 edges ✓
  [6/6] apollo15_1971_feather_drop: 3 nodes, 3 edges ✓
Committed to local graph.

$ gaia propagate
Running belief propagation...

  Package: aristotle_physics
    node_5003 (v ∝ W): belief = 0.70

  Package: galileo1638_tied_balls
    node_5003 (v ∝ W): 0.70 → 0.35 ↓  contradiction backpropagation
    node_5008 (定律错误): 0.00 → 0.82 ↑

  Package: galileo1638_medium_density
    node_5003 (v ∝ W): 0.35 → 0.28 ↓  alternative explanation

  Package: galileo1638_vacuum_prediction
    node_5012 (真空等速): 0.00 → 0.78 ↑  logic + partial experiment

  Package: newton1687_principia
    node_5017 (a = g): 0.00 → 0.93 ↑  high-confidence derivation
    node_5003 (v ∝ W): 0.28 → 0.12 ↓  second contradiction line

  Package: apollo15_1971_feather_drop
    node_5003 (v ∝ W): 0.12 → 0.05 ↓  nearly zero
    node_5012 (真空等速): 0.78 → 0.95 ↑  three evidence lines converge
    node_5017 (a = g): 0.93 → 0.96 ↑  theory + experiment confirmed
    node_5020 (月球实验): 0.00 → 0.98 ↑  definitive observation

BP converged in 12 iterations.

# ──────────────────────────────────────────────────────
# 验证 belief 断言
# ──────────────────────────────────────────────────────

$ gaia test
Running belief assertions from beliefs.yaml ...
  ✓ after aristotle_physics: 5003 = 0.70 ∈ [0.6, 0.8]
  ✓ after galileo1638_tied_balls: 5003 = 0.35 ∈ [0.2, 0.5]
  ✓ after galileo1638_tied_balls: 5008 = 0.82 ∈ [0.7, 1.0]
  ✓ after newton1687_principia: 5017 = 0.93 ∈ [0.85, 0.98]
  ✓ after newton1687_principia: 5003 = 0.12 ∈ [0.05, 0.25]
  ✓ after apollo15_1971_feather_drop: 5020 = 0.98 ∈ [0.9, 1.0]
  ✓ final: 5003 = 0.05 ∈ [0.01, 0.15]
  ✓ final: 5012 = 0.95 ∈ [0.85, 1.0]
All 8 assertions passed.

# ──────────────────────────────────────────────────────
# 发布到远程 Registry
# ──────────────────────────────────────────────────────

$ gaia publish
Publishing galileo_tied_balls v1.0.0 to http://localhost:8000 ...
  [1/6] aristotle_physics → commit abc001 (pending_review)
  [2/6] galileo1638_tied_balls → commit abc002 (pending_review)
  [3/6] galileo1638_medium_density → commit abc003 (pending_review)
  [4/6] galileo1638_vacuum_prediction → commit abc004 (pending_review)
  [5/6] newton1687_principia → commit abc005 (pending_review)
  [6/6] apollo15_1971_feather_drop → commit abc006 (pending_review)

Published 6 commits. Run `gaia review <id>` to start review.

$ gaia review abc001
Starting review for commit abc001 ...
  Review job started (job_id: j001)
  Use `gaia review --status abc001` to check progress.

$ gaia review --status abc001
Commit abc001: reviewed ✓ (reasoning_valid: pass, novelty: pass)

$ gaia merge abc001
Merging commit abc001 ...
  3 nodes written to graph
  1 edge written to graph
  Belief propagation triggered
  node_5003: belief = 0.70
Merge complete.

# 重复 review + merge 剩余 5 个 commits ...
```

---

## 7. Canonical Example: Einstein's Elevator

以下展示用交互式命令 + 包文件混合构建爱因斯坦电梯推理链的过程。

```bash
# ──────────────────────────────────────────────────────
# 已有知识 — 已发布的 packages（来自其他包或手动添加）
# ──────────────────────────────────────────────────────

$ gaia node show 1
node_1 "万有引力: F=Gm₁m₂/r², 作用在有质量的物体上"
  type: paper-extract | prior: 0.95 | belief: 0.95

$ gaia node show 3
node_3 "牛顿框架下光的引力偏折角 = 0.87 角秒"
  type: paper-extract | prior: 0.70 | belief: 0.70
  ← edge [1, 2] → [3] (deduction)

# ──────────────────────────────────────────────────────
# Package: einstein1907_equivalence_principle
# ──────────────────────────────────────────────────────

$ gaia node add "封闭电梯在太空中匀加速上升" --type deduction --prior 1.0
Created node E1

$ gaia edge add --tail E1 --head E2 --type deduction --probability 0.90 \
    --reasoning '[{"title":"惯性原理","content":"物体保持惯性，电梯地板加速迎上来"}]'
  ? 加速电梯中释放物体会怎样?
Created node E2: "电梯中释放的物体会'落'向地板"

$ gaia edge add --tail E2,node_5 --head E3 --type deduction
Created node E3: "电梯中的力学实验与引力场中完全不可区分"

$ gaia edge add --tail E3 --head E4 --type deduction
  ? 等效性是否应推广到所有物理现象?
Created node E4: "等效原理：任何物理实验都无法区分匀加速和引力场"

$ gaia commit -m "Einstein 1907: equivalence principle"
$ gaia propagate
  # 此时没有矛盾产生，已有知识 belief 不变

# ──────────────────────────────────────────────────────
# Package: einstein1915_general_relativity
# （使用包文件 + 交互式矛盾边混合）
# ──────────────────────────────────────────────────────

# 从包文件加载主体节点和边
$ gaia build packages/einstein1915_general_relativity.yaml
$ gaia commit -m "Einstein 1915: general relativity"

# 交互式添加关键矛盾边
$ gaia edge add --tail E12,node_3 --type contradiction
  # E12 "GR 预测 1.75 角秒" vs node_3 "牛顿预测 0.87 角秒"
Created edge [CONTRADICTION]: E12 ↔ node_3

$ gaia commit -m "Contradiction: GR 1.75 vs Newton 0.87"

$ gaia propagate
  node_3 (牛顿 0.87°): 0.70 → 0.55 ↓  quantitative contradiction
  E12 (GR 1.75°): belief = 0.72        new theory, no experiment yet

# ──────────────────────────────────────────────────────
# Package: eddington1919_solar_eclipse
# ──────────────────────────────────────────────────────

$ gaia node add "1919年5月29日日全食，Sobral 和 Príncipe 岛同时观测" \
    --type paper-extract --prior 0.95
Created node Ed1

$ gaia edge add --tail Ed1 --head Ed2 --type deduction
Created node Ed2: "观测到恒星光偏折 1.61' ± 0.30'"

$ gaia edge add --tail Ed2,E12 --head Ed3 --type deduction
Created node Ed3: "观测值与 GR 预测 1.75' 在误差范围内一致"

# 观测 vs 牛顿: 实验排除
$ gaia edge add --tail Ed2,node_3 --type contradiction
Created node Ed4: "观测值与牛顿预测 0.87' 不一致（偏差超过 2σ）"

$ gaia commit -m "Eddington 1919: solar eclipse observation"

$ gaia propagate
  E12 (GR 1.75°): 0.72 → 0.91 ↑  experimentally confirmed
  E11 (引力=时空弯曲): 0.60 → 0.87 ↑  downstream rises
  node_3 (牛顿 0.87°): 0.55 → 0.21 ↓  experimentally refuted
  node_1 (牛顿万有引力): 0.95 → 0.72 ↓  still valuable, no longer complete

# ──────────────────────────────────────────────────────
# 关键观察
# ──────────────────────────────────────────────────────
# 全程只有添加 node 和 edge，没有删除，没有覆盖。
# 矛盾通过 contradiction edge 建模，BP 根据证据强度自动分配 belief。
# 牛顿力学不是被"推翻"——belief 下降但仍然存在，作为近似理论仍有价值。
```

---

## 8. 数据模型映射

CLI 操作与后端数据模型的对应关系：

| CLI 概念 | 后端模型 | 说明 |
|----------|----------|------|
| `gaia node add` | `NewNode` | 内嵌在 `AddEdgeOp.tail` / `.head` 中 |
| `gaia node modify` | `ModifyNodeOp` | `node_id` + `changes` |
| `gaia edge add` | `AddEdgeOp` | `tail: list[NewNode\|NodeRef]`, `head: list[NewNode\|NodeRef]` |
| `gaia edge add --type contradiction` | `AddEdgeOp` (type="contradiction") | `head` 为空 |
| `gaia edge modify` | `ModifyEdgeOp` | `edge_id` + `changes` |
| `gaia commit` | 本地 `CommitRequest` | `message` + `operations` |
| `gaia publish` | `POST /commits` | 远程 `CommitRequest` |
| `gaia review` | `POST/GET /commits/{id}/review` | 异步 LLM 审查 |
| `gaia merge` | `POST /commits/{id}/merge` | `force: bool` |
| `gaia propagate` | 推断引擎 BP | 本地或远程 |
| `gaia search` | `POST /search/nodes` | `text` + `filters` |
| `gaia subgraph` | `GET /nodes/{id}/subgraph` | `hops`, `direction`, `max_nodes` |
| `gaia belief` | `GET /nodes/{id}` → `.belief` | 读取节点 belief 字段 |

### 关键实现细节

**交互式 `node add` 与 `AddEdgeOp` 的映射**：后端没有独立的 "add node" 操作——节点总是通过 `AddEdgeOp` 的 `tail`/`head` 中的 `NewNode` 入图。CLI 的 `gaia node add` 在底层会将节点暂存到 staging area，在 `commit`/`publish` 时自动组装成 `AddEdgeOp`。独立添加的节点（无边关联）需要创建一个特殊的 "identity" 边或等待后续边的添加。

**矛盾边**：`type: contradiction` 的边 `head` 为空列表 `[]`，`probability` 为 `null`。CLI 简写 `gaia edge add --tail a,b --type contradiction` 自动设置这些默认值。

---

## 9. 配置

### 9.1 全局配置 `~/.gaia/config.toml`

```toml
[user]
name = "Kun Chen"
email = "kun@example.com"

[registry]
default = "http://localhost:8000"
# token 存储在 ~/.gaia/credentials（不入 git）

[local]
db_path = "~/.gaia/graph"           # 默认本地图路径
# 可被项目级 gaia.toml 中的 [local] 覆盖
```

### 9.2 项目配置 `gaia.toml`

见第 3.1 节。项目级配置覆盖全局配置。

---

## 10. 技术选型

| 组件 | 选型 | 理由 |
|------|------|------|
| CLI 框架 | Python `click` 或 `typer` | 与 Gaia 后端同语言，复用 `libs/models.py` |
| 本地存储 | LanceDB + Kuzu | 嵌入式，零配置 (参见 kuzu-plan.md) |
| 远程通信 | `httpx` (async) | 调用 FastAPI 后端 REST API |
| 包文件格式 | TOML (manifest) + YAML (内容) | TOML 简洁适合元数据，YAML 适合内容丰富的节点/边 |
| 本地 BP | 复用 `services/inference_engine/` | 直接导入，本地运行 |

### 目录结构

```
cli/
├── __init__.py
├── main.py                 # CLI 入口 (click/typer app)
├── commands/
│   ├── init.py             # gaia init
│   ├── build.py            # gaia build
│   ├── commit.py           # gaia commit
│   ├── publish.py          # gaia publish
│   ├── review.py           # gaia review
│   ├── merge.py            # gaia merge
│   ├── propagate.py        # gaia propagate
│   ├── test.py             # gaia test
│   ├── node.py             # gaia node add/show/list/modify
│   ├── edge.py             # gaia edge add/show/list/modify
│   ├── search.py           # gaia search
│   ├── remote.py           # gaia remote add/list/remove
│   └── pull.py             # gaia pull
├── staging.py              # Staging area 管理
├── local_graph.py          # 本地图操作 (LanceDB + Kuzu)
├── registry_client.py      # 远程 API 客户端
├── package_loader.py       # 解析 gaia.toml + packages/*.yaml
└── config.py               # 配置管理
```

---

## 11. 与现有系统的关系

```
                    ┌──────────────┐
                    │   Gaia CLI   │
                    │  (gaia ...)  │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              │ (local)    │            │ (remote)
              ▼            │            ▼
    ┌──────────────┐       │   ┌──────────────────┐
    │  Local Graph │       │   │  FastAPI Gateway  │
    │ LanceDB+Kuzu │       │   │  (REST API)       │
    └──────────────┘       │   └────────┬─────────┘
              ▲            │            │
              │            │            ▼
    ┌──────────────┐       │   ┌──────────────────┐
    │ libs/models  │◄──────┘   │ services/         │
    │ libs/storage │           │  commit_engine    │
    │ inference_   │           │  search_engine    │
    │   engine     │           │  inference_engine │
    └──────────────┘           └──────────────────┘

本地模式: CLI → libs/ (直接调用)
远程模式: CLI → httpx → FastAPI Gateway → services/
```

CLI 复用 `libs/models.py` 中的 Pydantic 模型进行本地校验和序列化，复用 `libs/storage/` 进行本地图操作，复用 `services/inference_engine/` 进行本地 BP。远程模式通过 HTTP 调用 FastAPI 后端。
