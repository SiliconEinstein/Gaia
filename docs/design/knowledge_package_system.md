# Gaia 作为知识包管理器：与 Cargo/Julia Pkg 的系统类比

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [version_dependency_environment.md](version_dependency_environment.md), [text_structuring_service.md](text_structuring_service.md), [agent_verifiable_memory.md](agent_verifiable_memory.md), [theoretical_foundations.md](theoretical_foundations.md) §7 — Horn Clause 共同基础 |
| 状态 | Wishlist |

---

## 目录

1. [核心论点](#1-核心论点)
2. [为什么类比成立：论文就是 Package](#2-为什么类比成立论文就是-package)
3. [逐层对照：Cargo vs Gaia](#3-逐层对照cargo-vs-gaia)
4. [逐层对照：Julia Pkg vs Gaia](#4-逐层对照julia-pkg-vs-gaia)
5. [什么可以直接复用](#5-什么可以直接复用)
6. [什么必须重新设计](#6-什么必须重新设计)
7. [Knowledge Package 的完整定义](#7-knowledge-package-的完整定义)
8. [依赖模型](#8-依赖模型)
9. [Registry 协议](#9-registry-协议)
10. [CLI 对照](#10-cli-对照)
11. [从第一性原理看：为什么不能完全照搬](#11-从第一性原理看为什么不能完全照搬)
12. [Gaia 独有的能力](#12-gaia-独有的能力)
13. [实施策略](#13-实施策略)

---

## 1. 核心论点

Gaia 本质上是一个**知识的包管理器**。它和 Cargo/Julia Pkg 的关系不是"类似"或"可以借鉴"，而是**同构**——在抽象掉数据类型之后，它们解决的是同一个问题：

```
Cargo:  管理代码包的版本、依赖、发布、隔离环境
Gaia:   管理知识包的版本、依赖、发布、隔离环境
```

本质差异不是算法层面的（SAT vs BP），而是**依赖语义**的：Cargo 的依赖是硬接口调用（类型必须匹配，版本必须排他），Gaia 的依赖是软知识引用（节点不可变，引用永不断，多版本可共存）。这意味着 Gaia 在 package 层**不需要 SAT resolver**——BP 本身就是 resolver。详见 [theoretical_foundations.md](theoretical_foundations.md) §7.5。

这不是一个松散的比喻。下面逐层对照说明。

---

## 2. 为什么类比成立：论文就是 Package

之前曾经认为"知识图谱没有天然的包边界"。这是错的。

### 2.1 天然的包边界

| 知识来源 | Package | 类比 Cargo |
|---------|---------|-----------|
| 一篇论文 | 该论文提取的命题 + 推理链 | 一个 crate |
| 教科书一章 | 该章节的知识结构 | 一个 library crate |
| 一次实验 | 观测数据 + 结论 | 一个 binary crate |
| 一个理论 | 公理 + 推导 + 定理 | 一个 framework crate |
| 一个人的研究贡献 | 新增的推理链 | 一个 application crate |

论文有明确的边界（标题、作者、DOI）、有内部结构（前提 → 推理 → 结论）、有对外依赖（引用其他论文）。这和 crate 的结构完全对应。

### 2.2 跨包引用 = 跨 Crate 依赖

一篇论文引用另一篇论文的结论作为自己的前提——这就是 cross-crate dependency：

```rust
// Cargo: my-crate 依赖 serde 的 Serialize trait
use serde::Serialize;
```

```
// Gaia: my-research 依赖 bednorz-1986 的超导结论
tail: [ref("bednorz-mueller-1986::la-ba-cu-o-is-superconductor")]
```

### 2.3 学术引用 = 依赖声明

```
论文 A 的 References 章节:
  [1] Bednorz & Müller, 1986
  [2] BCS Theory, 1957
  [3] Anderson, RVB Theory, 1987

等价于:

# Gaia.toml
[dependencies]
bednorz-mueller-1986 = ">=1.0"
bcs-theory = ">=1.0"
anderson-rvb-1987 = ">=1.0"
```

学术引用一直就是一个依赖管理系统，只是没有形式化。Gaia 把它形式化了。

---

## 3. 逐层对照：Cargo vs Gaia

### 3.1 完整映射表

| Cargo 概念 | 实现 | Gaia 对应 | 实现 | 能否复用 |
|-----------|------|----------|------|---------|
| **crate** | 一个目录 + Cargo.toml | **Knowledge Package** | 一个命题子图 + Gaia.toml | 概念复用 |
| **crate version** | semver (1.2.3) | **Package version** | semver (1.2.3) | **直接复用** |
| **Cargo.toml** | TOML 配置 | **Gaia.toml** | TOML 配置 | **格式几乎相同** |
| **Cargo.lock** | TOML 锁文件 | **Gaia.lock** | TOML 锁文件 | **格式几乎相同** |
| **src/ 代码** | .rs 源文件 | **nodes + edges** | 命题 + 推理链 | 概念复用 |
| **pub fn / pub struct** | 公开 API | **exported nodes** | 包对外暴露的结论节点 | 概念复用 |
| **use dep::item** | 引用依赖 | **ref("pkg::node")** | 引用其他包的节点 | 概念复用 |
| **crates.io** | HTTP registry | **Gaia Server** | HTTP registry | **协议可借鉴** |
| **cargo publish** | 上传 .crate 文件 | **gaia submit** | 提交 package 到 server | 概念复用 |
| **cargo add** | 添加依赖 | **gaia add** | 添加知识包依赖 | **CLI 体验相同** |
| **cargo build** | 编译代码 | **gaia propagate** | 运行 BP | 概念复用 |
| **cargo test** | 运行测试 | **gaia experiment** | 运行思想实验 | 概念复用 |
| **cargo update** | 更新依赖 | **gaia update** | 更新包版本 | **CLI 体验相同** |
| **cargo outdated** | 检测过期依赖 | **gaia outdated** | 检测过期依赖 | **CLI 体验相同** |
| **cargo tree** | 依赖树 | **gaia graph** | 推理链可视化 | 概念复用 |
| **SAT resolver** | 布尔约束求解 | **不需要** | 节点不可变，引用永不断，BP 即 resolver | **不适用** |
| **text merge** | 行级文本合并 | **BP-based merge** | 概率信念合并 | **不能复用** |
| **features** | 条件编译 | — | 无直接对应 | — |

### 3.2 Cargo.toml vs Gaia.toml 逐字段对比

```toml
# ─── Cargo.toml ───
[package]
name = "my-project"
version = "0.1.0"
edition = "2021"
description = "A tool for ..."
license = "MIT"

[dependencies]
serde = "1.0"
tokio = { version = "1", features = ["full"] }

[dev-dependencies]
criterion = "0.5"
```

```toml
# ─── Gaia.toml ───
[package]
name = "my-superconductivity-research"
version = "0.1.0"
source = "original-research"            # 无 edition 概念
description = "High-Tc superconductivity mechanism analysis"
authors = ["Alice <alice@lab.edu>"]

[dependencies]
bednorz-mueller-1986 = ">=1.0"
bcs-theory = { version = ">=2.0", min_belief = 0.5 }   # Gaia 特有：min_belief 过滤

# 无 dev-dependencies 概念（思想实验不需要额外依赖）
```

差异点：
- Gaia 没有 `edition`（没有语言版本问题）
- Gaia 依赖可以附加 `min_belief` 过滤（只拉 belief 高于阈值的节点）
- Gaia 没有 `features`（没有条件编译概念）
- Gaia 没有 `dev-dependencies`（experiment 用的是同样的知识）

### 3.3 Cargo.lock vs Gaia.lock 对比

```toml
# ─── Cargo.lock ───
[[package]]
name = "serde"
version = "1.0.197"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "3fb1c873e1b9b056a4dc4c0c198b24c3ffa059243875571"

[[package]]
name = "tokio"
version = "1.37.0"
source = "registry+https://github.com/rust-lang/crates.io-index"
checksum = "1adbebffeca75fcfd058afa480fb8ea51c5a"
dependencies = ["pin-project-lite"]
```

```toml
# ─── Gaia.lock ───
[[package]]
name = "bednorz-mueller-1986"
version = "1.0.3"
source = "registry+https://gaia.example.com"
content_hash = "sha256:a1b2c3d4e5f6..."
nodes = 12
edges = 8

[[package]]
name = "bcs-theory"
version = "2.1.0"
source = "registry+https://gaia.example.com"
content_hash = "sha256:f6e5d4c3b2a1..."
nodes = 45
edges = 31
dependencies = ["quantum-mechanics-basics"]
```

结构几乎一致。Gaia.lock 额外记录 `nodes`/`edges` 数量（用于估算本地存储需求），以及 `content_hash`（用于验证包完整性）。

---

## 4. 逐层对照：Julia Pkg vs Gaia

Julia Pkg 在某些方面比 Cargo 更接近 Gaia，特别是环境管理。

| Julia Pkg 概念 | Gaia 对应 | 说明 |
|---------------|----------|------|
| **Project.toml** | **Gaia.toml** | 依赖声明 |
| **Manifest.toml** | **Gaia.lock** | 精确锁定 |
| **General registry** | **Gaia Server** | 中央包仓库 |
| **Pkg.add()** | **gaia add** | 添加依赖 |
| **Pkg.develop()** | **gaia init --local** | 本地开发 |
| **Pkg.register()** | **gaia submit** | 发布到 registry |
| **Environment** | **Gaia Environment** | 隔离工作空间 |
| **Environment stack** | **Environment stack** | 嵌套环境 |
| **Pkg.activate()** | **gaia env activate** | 切换环境 |
| **Pkg.instantiate()** | **gaia pull** | 下载依赖到本地 |

### Julia 环境栈的直接应用

Julia 的环境栈模型对 Gaia 特别有价值：

```julia
# Julia: 三层环境栈
Base (stdlib)
  → Project environment (Project.toml)
    → Temp environment (临时实验)
```

```
# Gaia: 三层环境栈
Server main (共享知识)
  → Local workspace (Gaia.toml)
    → Thought experiment (临时假设)
```

Julia 读取一个包时逐层向上查找（temp → project → base）。Gaia 读取一个节点的 belief 时也逐层查找（experiment override → workspace override → server value）。这是完全相同的机制。

---

## 5. 什么可以直接复用

### 5.1 可以照搬的

| 层面 | 具体内容 | 来源 |
|------|---------|------|
| **CLI 工作流** | init, add, update, outdated, publish 的用户体验 | Cargo |
| **Manifest 格式** | TOML，`[package]` + `[dependencies]` 结构 | Cargo |
| **Lockfile 格式** | TOML，`[[package]]` 列表 | Cargo |
| **Semver** | 版本号格式 + 兼容性规则 | Cargo / Julia |
| **环境栈** | base → project → temp 的逐层叠加 | Julia |
| **Registry index** | 包名 → 版本列表 → 元数据的索引结构 | Cargo / Julia |
| **内容寻址** | SHA256 hash 验证包完整性 | Cargo (checksum) |
| **Offline mirror** | 本地缓存 registry 内容 | Cargo / Julia |

### 5.2 可以借鉴设计但需要适配的

| 层面 | Cargo/Julia 的做法 | Gaia 的适配 |
|------|-------------------|------------|
| **依赖解析** | SAT solver（硬接口约束） | 不需要 SAT——节点不可变消除了接口断裂，BP 处理 belief 冲突 |
| **Merge** | 不涉及（registry 不做 merge） | BP-based merge（概率冲突解决） |
| **版本兼容性判断** | semver 规则（纯语法） | embedding distance + LLM（语义判断） |
| **发布审核** | crates.io 做基本检查 | commit review（LLM 深度审核） |
| **包的内部结构** | .rs 源文件 + 模块树 | nodes + edges + 推理链拓扑 |

### 5.3 完全不能复用的

| 层面 | 为什么 |
|------|-------|
| **编译/构建** | Gaia 没有编译步骤，对应物是 BP |
| **类型系统** | Gaia 的"类型"是 node type/edge type，语义完全不同 |
| **Features / 条件编译** | 知识图谱没有条件分支概念 |
| **Proc macros** | 无对应物 |
| **Build scripts** | 无对应物 |

---

## 6. 什么必须重新设计

### 6.1 依赖解析：Gaia 不需要 SAT

Cargo 需要 SAT solver 是因为**代码有硬接口**——函数签名改了，调用方编译失败，同一编译单元只能有一个版本。钻石依赖冲突必须用 CDCL 回溯搜索来找全局兼容的版本集。

Gaia 的情况根本不同：

```
Cargo:
  crate B v1.0: pub fn process(x: u32)
  crate B v2.0: pub fn process(x: String)  ← 签名变了，调用方断了
  → 必须 SAT 求解，选择唯一兼容版本

Gaia:
  KP_B v1.0: 导出 node_42 "X材料300K超导"
  KP_B v2.0: node_42 仍然存在（不可变），
             新增 node_99 + retraction edge
  → node_42 的引用永远不断，belief 通过 BP 自然更新
  → 不需要 SAT，不会"报错"
```

**节点不可变**消除了接口断裂。**BP**消除了版本排他性。Gaia 在 package 层只需要轻量的 registry lookup + 偏好排序 + staleness 检测，不需要 PubGrub 级别的约束求解。

详见 [theoretical_foundations.md](theoretical_foundations.md) §7.5。

### 6.2 Merge：文本合并 → 信念合并

Cargo 不做 merge（registry 上每个版本都是独立的）。Git 做 merge 但是行级文本合并。

Gaia 的 merge 是独有的：

```
Branch A: 新增 edge [42, 17] → [99] (p=0.8) — 支持证据
Branch B: 新增 edge [55] → [99] (p=0.3, contradiction) — 反对证据

Git merge: 报冲突，让人选
Gaia merge: 两条边都合并进图，跑 BP
           → node 99 belief = 综合支持和反对后的概率
```

这是 Gaia 的核心差异化能力——概率推断自动量化分歧。

### 6.3 包内搜索

Cargo：你知道要用 `serde::Serialize`，直接 `use` 就行。

Gaia：你不一定知道包里有什么节点。需要搜索：

```bash
gaia search --in bednorz-mueller-1986 "superconductivity temperature"
```

这在 Cargo 里没有对应物。Gaia 的包不是你手写的代码（你知道里面有什么），而是提取的知识（你需要搜索才能发现）。

---

## 7. Knowledge Package 的完整定义

### 7.1 结构

```
bednorz-mueller-1986/
├── Gaia.toml                    # 包元数据 + 依赖
├── nodes.json                   # 包内的所有命题
├── edges.json                   # 包内的所有推理链
└── exports.json                 # 对外暴露的结论节点
```

### 7.2 Gaia.toml 完整示例

```toml
[package]
name = "bednorz-mueller-1986"
version = "1.0.0"
description = "Discovery of high-Tc superconductivity in La-Ba-Cu-O"
source_type = "paper"
source_id = "doi:10.1007/BF01303701"
authors = ["J.G. Bednorz", "K.A. Müller"]
created_by = "text-structuring-service"    # 或 "manual"

[dependencies]
bcs-theory = ">=1.0"
perovskite-structure = ">=1.0"

[exports]
# 这个包对外暴露的结论——其他包可以引用
nodes = [
    "la-ba-cu-o-is-superconductor",       # 核心结论
    "transition-temperature-35k",          # 关键数据点
]
```

### 7.3 Nodes 和 Edges

```json
// nodes.json
[
    {
        "local_id": "layered-perovskite",
        "content": "La₂₋ₓBaₓCuO₄ 具有层状钙钛矿结构",
        "type": "paper-extract",
        "prior": 0.9
    },
    {
        "local_id": "ba-doping-holes",
        "content": "Ba 掺杂 x=0.15 时引入空穴载流子",
        "type": "paper-extract",
        "prior": 0.85
    },
    {
        "local_id": "resistivity-drop",
        "content": "电阻率在 35K 以下急剧下降",
        "type": "paper-extract",
        "prior": 0.95
    },
    {
        "local_id": "la-ba-cu-o-is-superconductor",
        "content": "La₂₋ₓBaₓCuO₄ 在 x=0.15 时是高温超导体",
        "type": "paper-extract",
        "prior": 0.85
    }
]

// edges.json
[
    {
        "tail": ["layered-perovskite", "ba-doping-holes", "resistivity-drop"],
        "head": ["la-ba-cu-o-is-superconductor"],
        "type": "paper-extract",
        "probability": 0.88,
        "reasoning": ["层状结构 + 空穴掺杂 + 电阻突降 → 超导相变"],
        "question": "铜氧化物能不能实现高温超导？"
    }
]
```

### 7.4 包内 ID vs 全局 ID

包内使用 `local_id`（字符串），发布到 registry 时分配全局 `int` ID。

```
包内引用: "la-ba-cu-o-is-superconductor"
全局引用: bednorz-mueller-1986::la-ba-cu-o-is-superconductor → node_42
```

类似 Rust 的 crate-local name vs fully qualified path。

### 7.5 版本语义

| | 含义 | 举例 |
|---|---|---|
| **patch** (1.0.x) | 措辞修正，不改变逻辑 | 修正提取中的 typo |
| **minor** (1.x.0) | 补充细节，兼容已有推理 | 从同一篇论文多提取了几个命题 |
| **major** (x.0.0) | 实质性改变 | 论文 retraction，或对结论的重新解读 |

和 Cargo 的 semver 语义完全一致。

---

## 8. 依赖模型

### 8.1 声明依赖

```toml
# 我的研究依赖这些已发布的知识包
[dependencies]
bednorz-mueller-1986 = ">=1.0"          # 宽松：任何 1.x 兼容版本
bcs-theory = "=2.1.0"                    # 严格：精确版本
anderson-rvb-1987 = { version = ">=1.0", min_belief = 0.6 }  # 只要 belief > 0.6 的节点
```

### 8.2 引用其他包的节点

```json
// 在 edges.json 中引用其他包的节点
{
    "tail": [
        "ref:bednorz-mueller-1986::la-ba-cu-o-is-superconductor",
        "ref:bcs-theory::electron-phonon-coupling",
        "my-local-observation"
    ],
    "head": ["my-new-conclusion"],
    "type": "join",
    "probability": 0.7,
    "reasoning": ["结合 Bednorz 的超导发现和 BCS 的电声耦合理论..."]
}
```

`ref:package::node` 语法引用外部包的导出节点。发布时 resolver 检查这些引用是否存在。

### 8.3 依赖解析

Cargo 的解析：用 SAT solver（PubGrub）找一组满足所有版本约束的精确版本，冲突时报错。

Gaia 的解析**不需要 SAT**，因为节点不可变、引用永不断、多版本可共存：

```
Step 1: 版本偏好解析（轻量，非 SAT）
  bednorz-mueller-1986 >=1.0 → 偏好最新版 1.0.3
  bcs-theory =2.1.0 → 选择 2.1.0
  无版本冲突问题——多版本天然共存

Step 2: Belief Propagation
  把所有包的节点和边合并进图
  跑 BP 计算全局一致的 belief
  新旧版本的矛盾通过 contradiction/retraction edge 自动处理
```

Step 1 只需要简单的 registry lookup + 偏好排序（类似 `pip`），不需要 PubGrub 级别的回溯搜索。Step 2 是 Gaia 的核心——BP 既是推理引擎，也是冲突解析器。

### 8.4 循环依赖

Cargo 禁止循环依赖。Gaia 不禁止——两个包可以互相引用节点，因为：

- 循环依赖在 Cargo 中会导致无限编译。在 Gaia 中只是一个图中有环——loopy BP 专门处理这个。
- 知识天然有互相支持的关系：A 的结论支持 B，B 的结论也支持 A。
- 但版本解析仍然需要 DAG（Package A v1.0 和 Package B v2.0 各自独立发布），只是发布后引用关系可以有环。

---

## 9. Registry 协议

### 9.1 Cargo Registry 协议

Cargo 的 registry 协议非常简洁：

```
GET /api/v1/crates/{name}              → 包的所有版本
GET /api/v1/crates/{name}/{version}    → 特定版本的元数据
GET /api/v1/crates/{name}/{version}/download → 下载 .crate 文件
PUT /api/v1/crates/new                 → 发布新版本
```

### 9.2 Gaia Registry 协议

可以借鉴同样的结构，增加 Gaia 特有的功能：

```
# 和 Cargo 一样的
GET  /api/v1/packages/{name}                    → 包的所有版本
GET  /api/v1/packages/{name}/{version}          → 特定版本的元数据
GET  /api/v1/packages/{name}/{version}/download → 下载包（nodes + edges）
POST /api/v1/packages/new                       → 发布新版本（经 review）

# Gaia 特有的
POST /api/v1/packages/{name}/{version}/search   → 在包内搜索节点
GET  /api/v1/packages/{name}/{version}/exports  → 查看导出节点
GET  /api/v1/packages/{name}/{version}/beliefs  → 查看包内节点的当前 belief
POST /api/v1/search                             → 跨所有包搜索（按 question / keyword / vector）
```

核心的 CRUD 几乎和 Cargo 一样。Gaia 额外需要搜索能力（因为用户不一定知道包里有什么节点）。

### 9.3 发布流程

```
Cargo:   cargo publish → crates.io 做基本检查 → 立即上线

Gaia:    gaia submit → Gaia Server 做 review（LLM 审核逻辑蕴含、去重检查）
                     → review 通过 → merge 进图 → BP 更新 belief
                     → 包正式上线
```

Gaia 的发布有审核环节——这是 Cargo 没有的。但从用户体验看，`gaia submit` 和 `cargo publish` 的感觉是一样的。

---

## 10. CLI 对照

### 10.1 命令对照表

| Cargo | Gaia | 语义 |
|-------|------|------|
| `cargo new my-project` | `gaia init my-research` | 创建新项目 |
| `cargo add serde` | `gaia add bednorz-mueller-1986` | 添加依赖 |
| `cargo build` | `gaia propagate` | "编译" = 运行 BP |
| `cargo test` | `gaia experiment` | 测试 = 思想实验 |
| `cargo publish` | `gaia submit` | 发布到 registry |
| `cargo update` | `gaia update` | 更新依赖版本 |
| `cargo outdated` | `gaia outdated` | 检查过期依赖 |
| `cargo tree` | `gaia graph` | 查看依赖图 |
| `cargo search` | `gaia search` | 搜索 registry |
| `cargo install` | `gaia pull` | 拉取包到本地 |
| `cargo doc` | `gaia explain` | 查看文档 / belief 解释 |
| `cargo bench` | — | 无对应（BP 不需要性能测试） |
| `cargo fmt` | — | 无对应（知识不需要格式化） |
| `cargo clippy` | `gaia review` | Lint = 知识审核 |

### 10.2 典型工作流对比

**Cargo 开发者的一天：**

```bash
cargo new my-lib && cd my-lib     # 创建项目
cargo add serde tokio             # 添加依赖
# 写代码...
cargo build                       # 编译
cargo test                        # 测试
cargo publish                     # 发布
```

**Gaia 研究者的一天：**

```bash
gaia init my-research && cd my-research       # 创建项目
gaia add bednorz-mueller-1986 bcs-theory      # 添加知识依赖
# 在本地添加命题和推理...
gaia propagate                                # 运行 BP
gaia experiment "假设 RVB 理论成立"             # 思想实验
gaia submit                                   # 发布到 registry
```

体验几乎一样。

---

## 11. 从第一性原理看：为什么不能完全照搬

> **理论基础：** Gaia 和 Cargo 的结构相似性源于共同的 Horn clause 逻辑骨架。可复用的部分恰好是只依赖 Horn clause 结构的特性；不可复用的部分是各自的扩展方向（离散约束 vs 概率传播）。详见 [theoretical_foundations.md](theoretical_foundations.md) §7。

尽管类比高度成立，有三个根本性差异阻止了完全照搬：

### 11.1 包的内部是代码 vs 图

Cargo 的包内部是源代码（文本文件，树形模块结构）。Gaia 的包内部是命题和推理链（图结构）。

这意味着：
- Cargo 可以按文件/模块组织。Gaia 按节点和边组织。
- Cargo 的"公开 API"是 `pub` 标注的函数/类型。Gaia 的"公开 API"是 `exports` 中列出的节点。
- Cargo 不需要包内搜索（你写的代码你知道）。Gaia 需要（提取的知识你不一定记得）。

### 11.2 依赖的语义不同

```
Cargo: A depends on B 的意思是"A 的代码调用了 B 的函数"
       B 改了接口签名 → A 编译失败
       同一编译单元只能有一个 B 的版本 → 必须 SAT 求解

Gaia:  A depends on B 的意思是"A 的推理引用了 B 的结论"
       B 更新了结论 → 旧节点不可变，引用永不断
       多版本可共存 → 不需要 SAT，BP 自然处理 belief 变化
```

Cargo 的依赖是硬性的（没有就编译不过，版本冲突必须解决）。Gaia 的依赖是软性的（belief 随依赖的可信度连续变化，系统永远不会"失败"）。

**这一差异的根源是节点不可变性。** 在 Cargo 中，函数签名可以变化，导致接口断裂。在 Gaia 中，节点一旦提交就是 content-addressed 的，其内容和 hash 永远不变。"更新"不是修改旧节点，而是创建新节点并通过 retraction/contradiction edge 与旧节点建立关系。因此引用永远不会断裂，SAT 的前提条件（版本排他性）不成立。

### 11.3 "编译"是全局的

```
Cargo: cargo build 只编译你的 crate + 直接依赖
       包之间编译是独立的

Gaia:  gaia propagate 运行 BP 在整个图上
       一个包内的 belief 变化可能影响另一个包的 belief
       "编译"不是独立的
```

这意味着 Gaia 的"编译"（BP）不能像 Cargo 那样增量进行——不能只编译一个包而不考虑其他包。但可以通过 regional BP 做近似。

---

## 12. Gaia 独有的能力

这些是 Cargo/Julia 完全没有的，Gaia 需要从零设计的：

### 12.1 BP-based merge

两个 branch 的知识可以自动合并，冲突通过概率推断解决。Cargo 永远不会把两个 crate 的代码合并。

### 12.2 Belief 传播

一个包的更新自动影响所有依赖它的包的 belief。Cargo 中一个 crate 更新不会改变依赖它的 crate 的行为（除非重新编译）。

### 12.3 Contradiction 处理

两个包可以包含矛盾的结论。Gaia 不报错——BP 自动降低冲突方的 belief。在 Cargo 中，两个 crate 的 API 冲突是编译错误。

### 12.4 Verification 反馈

验证结论 → 更新 edge probability → BP 传播 → belief 全局更新。类似"运行测试后自动改代码的 probability"，这在 Cargo 中没有对应。

### 12.5 Question-driven 搜索

通过 question 字段搜索推理链，找到"回答这个问题的知识包"。Cargo 的搜索只能按包名和关键词。

---

## 13. 实施策略

### 13.1 先做什么

从 Cargo 模型中最直接可复用的部分开始：

| 优先级 | 任务 | 复用来源 |
|--------|------|---------|
| P0 | Knowledge Package 数据格式（Gaia.toml, nodes.json, edges.json） | Cargo.toml 结构 |
| P0 | Semver 版本管理 | 直接用 Python semver 库 |
| P1 | Gaia.lock 生成与解析 | Cargo.lock 格式 |
| P1 | `gaia init` / `gaia add` CLI | Cargo CLI 体验 |
| P2 | Registry API（publish, download, search） | Cargo registry 协议 |
| P2 | 版本偏好解析 + staleness 检测 | 简单 lookup，不需要 SAT/PubGrub |
| P3 | 环境栈 | Julia Pkg 设计 |

### 13.2 后做什么

Gaia 独有的部分需要从零设计，不急于实现：

| 优先级 | 任务 | 说明 |
|--------|------|------|
| P3 | BP-based merge | 需要先有完整的 BP 引擎 |
| P3 | 跨包 belief 传播 | 需要先有完整的 BP 引擎 |
| P4 | Verification → version bump | 依赖 verification_providers 的实现 |
| P4 | Question-driven 包搜索 | 依赖 question 字段的实现 |

### 13.3 原则

**能抄就抄，不能抄的才创新。**

Cargo 和 Julia Pkg 是经过数百万用户验证的设计。凡是可以复用的（文件格式、CLI 体验、Registry 协议、semver 规则），都应该直接复用。只在 Gaia 的核心差异点（BP、概率推断、belief 传播、知识搜索）上创新。
