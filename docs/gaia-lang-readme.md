# Gaia Language (v3) & CLI 使用指南

Gaia 是一个大规模知识推理引擎（Large Knowledge Model），使用 **Typst** 作为知识建模语言，通过 **Factor Graph + Belief Propagation** 对知识的可信度进行概率推理。

## 目录

- [概念模型](#概念模型)
- [快速开始](#快速开始)
- [Typst 语言 API](#typst-语言-api)
- [CLI 命令](#cli-命令)
- [Pipeline 架构](#pipeline-架构)
- [完整示例：伽利略落体论证](#完整示例伽利略落体论证)

---

## 概念模型

Gaia 的核心是一个 **知识超图**（Knowledge Hypergraph）：

```
Knowledge Node（知识节点）
  ├── observation  — 经验事实，无需证明（prior = 1.0）
  ├── setting      — 定义/假设/背景条件（prior = 1.0）
  ├── claim        — 待证命题（prior = 0.5，可由推理提升）
  ├── question     — 开放问题（prior = 0.5）
  ├── contradiction — 矛盾关系
  └── equivalence   — 等价关系

Factor Node（推理因子）
  ├── infer         — A₁, A₂, ... → B（前提推结论，noisy-AND）
  ├── contradiction — A ↔ B 互斥
  └── equivalence   — A ≡ B 等价
```

**推理流程：** 作者用 Typst 声明知识节点和推理关系 → LLM 审查推理质量并赋予条件概率 → Belief Propagation 在整个图上传播信念 → 每个节点获得后验信念值。

---

## 快速开始

### 1. 创建新 package

```bash
gaia init my_research
cd my_research
```

生成的目录结构：

```
my_research/
  typst.toml          # 包元数据
  gaia.typ            # runtime bridge
  lib.typ             # 入口文件
  motivation.typ      # 模板 module
  _gaia/              # Gaia Typst runtime（自动 vendor）
    v2.typ
    module.typ
    declarations.typ
    tactics.typ
```

### 2. 编写知识

编辑 `.typ` 文件，声明知识节点和推理：

```typst
// reasoning.typ
#import "gaia.typ": *

#module("reasoning", title: "核心论证")

#observation("experiment_result")[
  实验数据显示 X 与 Y 呈正相关（r = 0.87, p < 0.01）。
]

#claim("causal_link")[
  X 是 Y 的主要成因。
][
  #premise("experiment_result")

  基于实验数据 @experiment-result，相关性强且统计显著...
]
```

在 `lib.typ` 中 include 新 module：

```typst
#include "reasoning.typ"
```

### 3. 构建

```bash
gaia build .
```

输出 Graph IR 到 `.gaia/graph/`，Markdown 到 `.gaia/build/package.md`。

### 4. 发布到本地数据库

```bash
gaia publish . --local
```

运行完整 pipeline（build → review → infer → publish），将知识写入 LanceDB。

### 5. 搜索已发布的知识

```bash
gaia search "实验"
gaia search --id "my_research/causal_link"
```

---

## Typst 语言 API

### Package 声明

每个 package 的 `lib.typ` 必须包含以下结构：

```typst
#import "gaia.typ": *      // 导入 Gaia runtime
#show: gaia-style           // 应用文档样式

#package("package_name",
  title: "包标题",
  author: "作者",
  version: "1.0.0",
  modules: ("motivation", "reasoning"),  // module 列表
  export: ("main_conclusion",),          // 导出的知识节点
)

#include "motivation.typ"
#include "reasoning.typ"

#export-graph()             // 必须：输出知识图谱元数据
```

### Module 声明

每个 `.typ` 文件代表一个 module：

```typst
#import "gaia.typ": *

#module("module_name", title: "可选标题")

// ... 知识声明 ...
```

### 知识节点声明

| 函数 | 用途 | 默认 prior |
|------|------|-----------|
| `#observation("name")[内容]` | 经验事实 | 1.0 |
| `#setting("name")[内容]` | 背景假设 | 1.0 |
| `#question("name")[内容]` | 开放问题 | 0.5 |
| `#claim("name")[内容]` | 无证明命题 | 0.5 |
| `#claim("name")[内容][证明]` | 有证明命题 | 0.5 |

### 推理关系

**前提声明**（只能在 claim 的证明块中使用）：

```typst
#claim("conclusion")[
  结论陈述。
][
  #premise("premise_1")    // 声明前提
  #premise("premise_2")

  基于 @premise-1 和 @premise-2，推导出...
]
```

每个 `#premise()` 声明一条 factor graph 中的边。多个前提构成 **noisy-AND**：所有前提都可信时，结论才可信。

### 约束关系

```typst
// 矛盾：A 与 B 不能同时为真
#claim_relation("contradiction_name",
  type: "contradiction",
  between: ("claim_a", "claim_b"),
)[矛盾说明][
  // 可选：矛盾的证明
]

// 等价：A 与 B 等价
#claim_relation("equiv_name",
  type: "equivalence",
  between: ("claim_a", "claim_b"),
)[等价说明]
```

### 跨 Module 引用

```typst
#use("other_module.knowledge_name")   // 声明对其他 module 知识的依赖
```

引用后可在 `#premise()` 中使用该知识作为前提。

### 交叉引用（文档内）

知识名中的下划线自动转为连字符用于引用：

```typst
#observation("my_fact")[事实内容]

// 在文本中引用：
如 @my-fact 所示...
```

---

## CLI 命令

### `gaia build`

构建知识包，生成 Graph IR 和文档。

```bash
gaia build [PATH] [--format md|json|typst|all] [--proof-state]
```

| 选项 | 说明 |
|------|------|
| `--format md` | 输出 Markdown（默认） |
| `--format json` | 输出 graph.json |
| `--format all` | 输出所有格式 |
| `--proof-state` | 生成证明覆盖报告 |

输出目录：
- `.gaia/build/` — package.md, graph.json, graph_data.json
- `.gaia/graph/` — raw_graph.json, local_canonical_graph.json, canonicalization_log.json

### `gaia publish`

发布知识包到存储后端。

```bash
gaia publish [PATH] --local [--db-path PATH]
gaia publish [PATH] --git
```

| 选项 | 说明 |
|------|------|
| `--local` | 运行完整 pipeline 并写入 LanceDB + Kuzu |
| `--git` | git add + commit + push |
| `--db-path` | LanceDB 路径（默认 `$GAIA_LANCEDB_PATH` 或 `./data/lancedb/gaia`） |

`--local` 执行的完整流程：build → review(mock) → infer(BP) → 写入存储。

### `gaia search`

搜索已发布的知识。

```bash
gaia search "查询文本" [--limit 10] [--db-path PATH]
gaia search --id "package/knowledge_name"
```

使用 BM25 全文搜索，支持 CJK 文本回退。

### `gaia init`

创建新的知识包。

```bash
gaia init my_package
```

### `gaia clean`

删除构建产物。

```bash
gaia clean [PATH]    # 删除 .gaia/ 目录
```

---

## Pipeline 架构

```
.typ 源文件
  │  typst.query("<gaia-graph>")
  ↓
graph_data dict (nodes, factors, constraints)
  │  typst_compiler.compile_typst_to_raw_graph()
  ↓
RawGraph (deterministic IDs, source refs)
  │  build_utils.build_singleton_local_graph()
  ↓
LocalCanonicalGraph (去重, 规范化)
  │  pipeline_review() — LLM 或 mock 审查
  ↓
ReviewOutput (node_priors π, factor_params p)
  │  pipeline_infer() — 构建 factor graph + BP
  ↓
InferResult (beliefs per node)
  │  pipeline_publish() — 转换 + 写入存储
  ↓
LanceDB + Kuzu (Knowledge, Chain, Module, Package, Beliefs)
```

### Python API

```python
from libs.pipeline import pipeline_build, pipeline_review, pipeline_infer, pipeline_publish

# 1. Build
build = await pipeline_build(Path("my_package"))

# 2. Review（mock 或真实 LLM）
review = await pipeline_review(build, mock=True)
# review = await pipeline_review(build, mock=False, model="gpt-5-mini")

# 3. Infer（Belief Propagation）
infer = await pipeline_infer(build, review)
print(infer.beliefs)
# {"galileo.vacuum_prediction": 0.587, "aristotle.heavier_falls_faster": 0.133, ...}

# 4. Publish
result = await pipeline_publish(build, review, infer, db_path="/tmp/db")
print(result.stats)
# {"knowledge_items": 13, "chains": 5, "factors": 5, ...}
```

---

## 完整示例：伽利略落体论证

这个例子展示了如何用 Gaia Language 建模一个经典的科学论证。

### 包结构

```
galileo_falling_bodies/
  typst.toml
  lib.typ
  motivation.typ     — 研究问题
  setting.typ        — 思想实验环境
  aristotle.typ      — 亚里士多德的主张
  galileo.typ        — 伽利略的反驳
  follow_up.typ      — 后续问题
```

### motivation.typ — 提出问题

```typst
#import "gaia.typ": *

#module("motivation", title: "研究动机")

#question("main_question")[
  下落的速率是否真正取决于物体的重量？
]
```

### setting.typ — 定义环境

```typst
#module("setting", title: "背景与假设")

#setting("thought_experiment_env")[
  想象一个重球 H 和一个轻球 L 从同一高度落下。
]

#setting("vacuum_env")[
  一个理想化的无空气阻力环境。
]
```

### aristotle.typ — 旧理论

```typst
#module("aristotle", title: "亚里士多德的主张")

#observation("everyday_observation")[
  日常生活中，石头比羽毛下落更快。
]

#claim("heavier_falls_faster")[
  物体下落的速度与其重量成正比——重者下落更快。
]
```

### galileo.typ — 反驳论证

```typst
#module("galileo", title: "伽利略的论证")

#use("aristotle.heavier_falls_faster")
#use("setting.thought_experiment_env")

#observation("inclined_plane_observation")[
  斜面实验显示不同重量的物体下落时间几乎相同。
]

// 从同一前提推出矛盾的两个结论
#claim("composite_is_slower")[
  绑球复合体 HL 下落慢于 H。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")
  轻球拖慢重球...
]

#claim("composite_is_faster")[
  绑球复合体 HL 下落快于 H。
][
  #premise("heavier_falls_faster")
  #premise("thought_experiment_env")
  复合体更重，所以更快...
]

// 声明矛盾
#claim_relation("tied_balls_contradiction",
  type: "contradiction",
  between: ("composite_is_slower", "composite_is_faster"),
)[两个预测互相矛盾，说明前提有误。]

// 最终结论
#claim("vacuum_prediction")[
  在真空中，不同重量的物体以相同速率下落。
][
  #premise("tied_balls_contradiction")
  #premise("inclined_plane_observation")

  绑球矛盾 + 斜面实验 → 旧理论错误 → 真空中等速下落。
]
```

### BP 推理结果

```
aristotle.everyday_observation:    0.999  (观察，高信念)
aristotle.heavier_falls_faster:    0.133  (被矛盾大幅降低)
galileo.vacuum_prediction:         0.588  (多条证据支撑)
galileo.tied_balls_contradiction:  0.391  (矛盾有效)
motivation.main_question:          0.500  (问题，无信息先验)
setting.thought_experiment_env:    0.999  (设定，高信念)
```

亚里士多德的"重者更快"从 0.5 降到 0.133 — 因为它导出了自相矛盾。伽利略的真空预测从 0.5 升到 0.588 — 被多条独立证据支撑。
