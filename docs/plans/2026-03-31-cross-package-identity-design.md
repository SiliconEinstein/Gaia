# Cross-Package Identity Design — 跨包身份与引用体系

> **Status:** Target design
>
> **Issue:** #272
>
> **Date:** 2026-03-31

## 1. 问题

当前 Gaia IR 中 Knowledge 节点的身份链是断裂的：

```
Typst label: <vacuum_prediction>               ← 人类可读
     ↓ compile
raw_node_id: raw_a7c3b2...                     ← content-hash，名字丢了
     ↓ canonicalize
local_canonical_id: lcn_f8d1e9...              ← hash of hash
     ↓ storage
knowledge_id: "package/vacuum_prediction"      ← 名字从 source_ref 恢复
```

IR 层完全依赖 content hash 做身份标识，human-readable label 只作为 metadata 携带。当 LKM 需要解析跨包引用时，必须反向查 metadata 才能找到对应 lcn_id。这很脆弱且不符合跨包引用的本质需求。

## 2. 第一性原理

### 2.1 Name-addressed vs Content-addressed

知识节点的身份有两种模型：

- **Content-addressed**：你是什么内容，你就是谁。同样的内容 = 同一个节点。
- **Name-addressed**：作者给了名字，名字就是身份。内容可以变（version），身份不变。

跨包引用天然需要 name-addressed identity — 你不可能让包 A 去 hash 包 B 的内容来构造引用。

因此 **`(package_name, label)` 作为 stable identity** 是正确方向。Content hash 降级为内容指纹，用于去重和变更检测，不再承担身份标识职责。

### 2.2 版本不在引用中

引用是逻辑关系，版本是部署决策。类似 Go 的 `import "github.com/foo/bar"` 不含版本，`go.mod` 锁版本。

`ext:` 引用不含 version，版本解析由 `gaia-deps.yml` 负责。

### 2.3 Module 不参与身份

Label 在 package 内唯一（编译期/提取期强制保证），module 是组织结构，不参与 identity。

## 3. 设计

### 3.1 Qualified Node ID (QID)

引入 QID 作为 Knowledge 节点的 IR 层全局唯一标识：

```
{namespace}:{package_name}::{label}
```

**分隔符选择 `::`**：避免与 DOI 中的 `/` 冲突（如 `10.1038/s41586-023-06330-y`）。

**命名空间（namespace）**：

| Namespace | 来源 | 唯一性保证 | 示例 |
|-----------|------|------------|------|
| `reg` | 注册表包（Gaia Lang 编写） | GitHub repo / registry 唯一 | `reg:galileo_falling_bodies::vacuum_prediction` |
| `paper` | 提取的论文（XML pipeline） | 数据库 metadata ID | `paper:{metadata_id}::cmb_power_spectrum` |

Paper namespace 的具体 ID 格式（DOI、arXiv ID、内部 metadata ID）由 data infra 层决定，IR 层只关心 `paper:{id}` 是全局唯一的。

### 3.2 各实体的 ID 方案

| 实体 | ID 方案 | 格式 | 理由 |
|------|---------|------|------|
| **Knowledge** | QID（人类可读） | `{ns}:{pkg}::{label}` | 跨包引用需要稳定可读标识 |
| **Strategy** | Hash-based | `lcs_` / `gcs_` 前缀 | 包内推理结构，无跨包引用需求 |
| **Operator** | Hash-based | `lco_` / `gco_` 前缀 | FormalExpr 派生结构，无命名需求 |

Knowledge 是唯一需要 QID 的实体。Strategy 和 Operator 保持现有 hash-based 方案不变。

### 3.3 IR 层统一使用 QID

编译到 IR 后，所有 Knowledge 节点统一使用 QID，不区分 local/external：

```
reg:galileo_falling_bodies::vacuum_prediction   ← 本包定义的节点
reg:newton_principia::universal_gravitation      ← 引用的外部节点
```

两者格式一致。区别在于：本包节点有完整的 content 和 metadata；外部节点只有 QID 引用（content 在对方包中）。

`ext:` 前缀变为 **Gaia Lang 层面的语法糖**，编译后不再出现在 IR 中。

### 3.4 Content Hash 保留

Content hash 保持现有定义，不含 package_id：

```
content_hash = SHA-256(type + content + sorted(parameters))
```

用途不变：去重、canonicalization 快速路径、变更检测。

Content hash **不是**身份标识，不能替代 QID。

### 3.5 跨包引用格式（Gaia Lang 层）

在 Gaia Lang `.typ` 源文件中，跨包引用通过 `gaia-deps.yml` 声明：

```yaml
# gaia-deps.yml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
```

在 `.typ` 文件中使用 `ext:` 语法引用（编译时解析为 QID）。

### 3.6 提取论文的 Label 生成与锁定

| 策略 | 说明 |
|------|------|
| **生成方式** | Content slug（如 `ybco_superconducts_90k`），collision 时加后缀 `_2` |
| **锁定机制** | 首次提取后生成 `labels.lock.yml`，记录 `content_hash → label` 映射 |
| **后续提取** | 先读 lock 文件，已有映射保持不变，仅新增节点生成新 label |
| **包内唯一性** | 提取时强制保证，与 Gaia Lang 编译期检查一致 |

Label 一旦生成即锁定，不随提取逻辑变化而变化。

## 4. Schema 变更

### 4.1 Knowledge

```diff
 Knowledge:
-    id:                     str              # lcn_ 或 gcn_ 前缀
+    id:                     str              # QID 格式：{ns}:{pkg}::{label}（local）
+                                             # 或 gcn_ 前缀（global，注册中心分配）
     type:                   str              # claim | setting | question
     content_hash:           str | None       # SHA-256(type + content + sorted(parameters))
+    label:                  str              # 包内唯一的人类可读标签
+    package_name:           str              # 所属包名
+    namespace:              str              # reg | paper
     ...
```

`label`、`package_name`、`namespace` 三个字段联合构成 QID，也可由 `id` 解析得到。冗余存储是为了查询便利。

### 4.2 LocalCanonicalGraph

```diff
 LocalCanonicalGraph:
     package:                str
     version:                str
+    namespace:              str              # reg | paper
     knowledge:              list[Knowledge]
     strategies:             list[Strategy]   # ID 方案不变
     operators:              list[Operator]   # ID 方案不变
     ir_hash:                str
```

### 4.3 Strategy / Operator

无变更。保持 hash-based `lcs_`/`gcs_`/`lco_`/`gco_` 方案。

Strategy 和 Operator 中对 Knowledge 的引用（premises、conclusion 等）从 `lcn_` ID 改为 QID。

## 5. 全栈 Identity 流

```
Gaia Lang (.typ)
  #claim("vacuum_prediction")[在真空中...]
     ↓ compile（Gaia Lang → Gaia IR）
Gaia IR (LocalCanonicalGraph)
  Knowledge {
    id: "reg:galileo_falling_bodies::vacuum_prediction",
    label: "vacuum_prediction",
    package_name: "galileo_falling_bodies",
    namespace: "reg",
    content_hash: "a7c3b2...",
    ...
  }
     ↓ canonicalize（local → global）
Global Graph
  Knowledge {
    id: "gcn_f8d1e9...",           ← 注册中心分配，稳定不变
    content_hash: "a7c3b2...",
    local_members: [
      {qid: "reg:galileo_falling_bodies::vacuum_prediction", ...},
      {qid: "paper:10.1038/abc::vacuum_prediction", ...},
    ],
    ...
  }
     ↓ lower（Gaia IR → FactorGraph）
FactorGraph
  Variable {
    node_id: int,
    registry_ref: "reg:galileo_falling_bodies::vacuum_prediction",
    ...
  }
```

## 6. 跨包引用解析流程

当 LKM 需要解析包 B 中对包 A 知识的引用：

1. 包 B 的 IR 中，Strategy 的 premise 包含 QID `reg:galileo_falling_bodies::vacuum_prediction`
2. LKM 通过 QID 直接查找对应的 Knowledge 节点（或其 global canonical 映射）
3. 无需反向查 metadata 或遍历 hash — QID 是确定性的一级索引

## 7. 约束与不变量

1. **包内 label 唯一**：编译期（Gaia Lang）/ 提取期（XML pipeline）强制保证
2. **QID 全局唯一**：由 `namespace + package_name` 的唯一性 + 包内 label 唯一性联合保证
3. **Label 不可变**：同一 `(package, label)` 在不同版本间保持不变；label rename = breaking change，所有引用方需要更新
4. **Content hash 独立于 package**：不含 package_id，用于跨包内容去重
5. **版本不在 QID 中**：版本解析由 `gaia-deps.yml` 负责
6. **Strategy/Operator 不受影响**：保持 hash-based ID，但其对 Knowledge 的引用改为 QID
