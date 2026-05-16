# Identity And Hashing — 身份与哈希

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本文档定义 Gaia IR 中对象身份、内容指纹与图哈希的边界。它回答“哪些值标识对象本身，哪些值只是帮助匹配或完整性校验”。

## 目的

Gaia IR 里至少有三类容易混淆的“标识”：

- **对象身份**：`Knowledge.id`、`Strategy.strategy_id`、`Operator.operator_id`
- **内容指纹**：`Knowledge.content_hash`
- **图哈希**：`LocalCanonicalGraph.ir_hash`

它们的职责不同，不能混用。

## 1. 三类标识

| 名称 | 作用 | 作用域 | 是否跨包稳定 |
|------|------|--------|--------------|
| `Knowledge.id` | 标识一个具体 Knowledge 对象 | QID | 否（含 package_name） |
| `Knowledge.content_hash` | 标识 Knowledge 的内容指纹 | local | 是 |
| `Strategy.strategy_id` | 标识一个 Strategy（hash-based） | local | 否 |
| `Operator.operator_id` | 标识一个顶层 Operator | local | 否 |
| `Compose.compose_id` | 标识一个 Compose 工作流 | local | 否 |
| `LocalCanonicalGraph.ir_hash` | 标识整个 local graph 的 canonical serialization | local graph | 不适用 |

## 2. Knowledge 身份

### 2.1 Knowledge QID

`Knowledge.id` 使用 **QID**（Qualified Node ID）格式，是 **name-addressed** identity：

```text
{namespace}:{package_name}::{label}
```

对于 QID 中的三部分：

- **namespace**：知识来源命名空间（`reg` = 注册表包，`paper` = 提取的论文）
- **package_name**：包名（`reg` 由 registry 保证唯一，`paper` 由数据库 metadata ID 保证唯一）
- **label**：QID 自身携带的人类可读句柄。对本地声明，它通常就是包内标签；对 imported external reference，则应保留外部 QID 中已有的 label

示例：`github:galileo_falling_bodies::vacuum_prediction`、`paper:{metadata_id}::cmb_power_spectrum`

**字符集约束（与 `gaia.engine.ir.knowledge._QID_RE` 严格一致）：**

- `namespace`：以小写字母开头，后续为小写字母、数字或下划线（`[a-z][a-z0-9_]*`）
- `package_name`：以小写字母或数字开头，后续为小写字母、数字、下划线或连字符（`[a-z0-9][a-z0-9_\-]*`）
- `label`：以**字母**或下划线开头，后续为字母、数字或下划线（**`[A-Za-z_][A-Za-z0-9_]*`**，**允许大小写**）。自动生成的 label 以 `__` 开头

**风格建议（非合约）**：新包推荐使用 `snake_case`（全小写 + 下划线）label，便于 grep 与跨实现稳定排序。大小写仅作为合约层兜底允许的字符集存在；如果未来要收紧到全小写，是单独的代码 PR，不是文档变更。

对 **本地声明** 且未显式指定 `id` 的 Knowledge，`LocalCanonicalGraph` 会用自己的 `(namespace, package_name)` 自动生成 QID。对 **外部引用** 的 Knowledge，则允许显式保留 foreign QID。

如果实现希望在当前 graph 中额外保存一个更顺手的本地句柄，应通过 `Knowledge.label` 这样的 graph-local 字段表达，而不是改写 imported object 的 QID。

### 2.2 Ownership vs Reference

`LocalCanonicalGraph.namespace` / `package_name` 描述的是 **graph owner**，不是“图中所有 QID 的共同前缀”。

因此一个 local graph 中可以同时出现：

- 当前 package 自己声明的 Knowledge QID
- 来自外部 package 的 foreign QID

Gaia IR 对二者的最小区分是：

- 本地声明节点：若缺少 `id`，可由 graph owner 自动分配 QID
- imported external occurrence：必须显式保留其外部身份，不因被引用而重命名为新的本地对象

这就是为什么 QID 既承担 identity，又不能被 graph owner 强行重写。

因此：

- 同包、同 label → 相同 QID（即使内容因版本更新而变化）
- 不同包、同 label → 不同 QID（不同 `package_name`）
- 同包、label 改名 → 不同 QID（breaking change，所有引用方需要更新）

QID 是 name-addressed 身份，不是 content-addressed。内容变化不影响 QID；label 变化才会。

## 3. Knowledge 内容指纹

`Knowledge.content_hash` 是跨包稳定的内容指纹。**其权威定义在 `gaia.engine.ir.knowledge._compute_content_hash`**：

```text
content_hash = SHA-256(type + "|" + format + "|" + content + "|" + sorted((name, type) for p in parameters))
```

字符串字段以 ASCII pipe `|` 分隔；参数列表序列化为按 `(name, type)` 字典序排序的元组列表。哈希取 SHA-256 hex 的前 64 位。

**不进入哈希的字段**：`id`、`label`、`title`、`module`、`declaration_index`、`exported`、`metadata`、`provenance`、`template_*` / `sub_knowledge` / `conclusion`（即叙事层与 composition 专用字段）；`package_id` 也明确不进入。

> **Backwards compatibility**：在引入 `format` 字段之前，老版本 IR 的 hash payload 是 `type|content|sorted_params`（不含 `format`）。当前 `Knowledge` model 在校验时如果给定 `content_hash` 不匹配新公式，但匹配 legacy 公式，且 `format` 字段没有被显式传入（仍取默认 `"markdown"`），则接受该输入并以新公式覆盖 `content_hash`；其他情况报 `content_hash must match the derived content fingerprint`。新写入的 Knowledge 总是带 `format` 字段并使用新公式。

因此：

- 不同包中同内容的 local Knowledge 拥有相同的 `content_hash`
- `content_hash` 不是对象主键，不能替代 `id`

### 3.1 典型用途

- **本地去重与匹配**
  编译时检测包内是否有内容完全一致的 Knowledge 节点
- **跨包内容比对**
  不同包中同内容的 Knowledge 共享同一 `content_hash`，可用于发现语义等价节点

### 3.2 不应如何使用

- 不能把 `content_hash` 当作对象 `id`
- 不能把两个 `content_hash` 相同的节点自动视为"同一条推理链"

`content_hash` 只说明"内容完全一致"，不说明它在图中的结构角色完全一致。

## 4. Strategy / Operator / Compose 的身份

当前 contract 下：

- `Strategy` 使用 `strategy_id`（hash-based，**`lcs_` 前缀**）
- `Operator` 使用 `operator_id`（**`lco_` 前缀**），但**只对顶层 Operator 强制**——嵌入在 `FormalStrategy.formal_expr` 内的 Operator 可以省略 `operator_id` 与 `scope`，它们由宿主 FormalStrategy 拥有
- `Compose` 使用 `compose_id`（**`lcm_` 前缀**）

它们没有独立的 `content_hash` 概念。Strategy / Operator / Compose 的身份来自图结构角色，而不是一段可独立去重的内容文本。

**注意**：Strategy / Operator / Compose 中对 Knowledge 的引用（`premises`、`conclusion`、`variables`、`inputs`、`background`、`warrants`）使用 QID。Compose 的 `actions` 列表可以引用 QID（Knowledge）或 `lco_` / `lcs_` / `lcm_` ID（Operator / Strategy / Compose）。

### 4.1 Strategy ID 计算

`strategy_id` 的 hash 输入包含**接口信息和内部结构摘要**，确保不同结构的同接口策略不会 ID 碰撞：

```text
strategy_id = lcs_{SHA-256(scope + type + sorted(premises) + conclusion + structure_hash)[:16]}
```

其中 `structure_hash` 按形态决定：

| 形态 | structure_hash |
|------|---------------|
| 叶子 Strategy | `””` （空字符串） |
| CompositeStrategy | `SHA-256(sorted(sub_strategies))` |
| FormalStrategy | `SHA-256(canonical(formal_expr))` |

`canonical(formal_expr)` 是对 FormalExpr 内 Operator 列表的确定性序列化（按 operator 字段稳定排序后 JSON dump，参见 `gaia.engine.ir.graphs._canonicalize_strategy_dump`）。

这意味着：同一组 premises/conclusion/type，如果内部结构不同（如 leaf vs FormalStrategy），会产生不同的 `strategy_id`。

## 5. 图哈希

`LocalCanonicalGraph.ir_hash` 是对整个 local graph 的 canonical serialization 计算出的确定性哈希（实现见 `gaia.engine.ir.graphs._canonical_json` + `LocalCanonicalGraph._compute_hash`）。

它的作用是：

- 编译完整性校验
- 重编译后的一致性验证

`ir_hash` 覆盖的是**当前 graph 提交的完整闭包**，其中包括：

- 本地声明的节点
- imported external occurrences
- 它们参与的 `Operator` / `Strategy` / `Compose` 引用关系
- `Compose.{compose_id, name, version, sorted(inputs), sorted(background), actions, sorted(warrants), conclusion, metadata}`

因此，external references 不是 graph hash 之外的"隐式上下文"；一旦进入 IR，它们就是 canonical serialization 的组成部分。

> **IR schema 版本与 ir_hash 的区别**：`ir_hash` 是 *某一份 graph* 的内容指纹；而 IR **schema** 版本（`gaia._meta.IR_SCHEMA = "ir-vN+<hash>"`，由 `IR_SCHEMA_VERSION` 与所有 IR Pydantic model 的 JSON schema 派生）反映 *contract* 形状。LKM / 下游消费者在 ingest 时通过 `gaia._meta.check_ir_compat` 比对 `ir-vN` 前缀；当 schema 形状漂移时，pre-push 钩子 `scripts/check_ir_schema_bump.py` 会要求 bump `IR_SCHEMA_VERSION` 与 `IR_SCHEMA_SNAPSHOT_HASH`。

它**不是**：

- 任一单个 Knowledge 的身份
- 任一单个 Knowledge 的内容指纹

## 6. 三者如何配合

一个最常见的场景：

1. 作者在包 A 中写出一个 claim，label 为 `vacuum_prediction` → QID `github:galileo_falling_bodies::vacuum_prediction`
2. 作者在包 B 中写出同样内容的 claim，label 也为 `vacuum_prediction` → QID `github:newton_principia::vacuum_prediction`
3. 两者 QID 不同，因为 `package_name` 不同
4. 两者 `content_hash` 相同，因为内容一致
5. 下游系统可以用 `content_hash` 发现这两个节点代表相同内容

另一个常见场景：

1. 包 C 在自己的 `LocalCanonicalGraph` 中显式引用 `github:galileo_falling_bodies::vacuum_prediction`
2. 这个 foreign QID 仍然保持 Galileo 包中的对象身份
3. 包 C 可以围绕它新增本地 Strategy / Operator
4. 但包 C 并没有因为“把它写进自己的 graph”就铸造一个新的本地 claim identity

这正是”对象身份”和”内容指纹”必须分离的原因。QID 是 name-addressed（”我叫什么”），`content_hash` 是 content-addressed（”我长什么样”），两者不能混用。

## 7. Validation 要点

validator 至少应检查：

1. `Knowledge.id` 是否为有效 QID 格式（`{namespace}:{package_name}::{label}`），label 字符集允许 `[A-Za-z_][A-Za-z0-9_]*`
2. `content_hash` 若存在，是否与 `_compute_content_hash(type, content, parameters, format)` 派生值一致；如果 `format` 字段未显式给出，且给定 `content_hash` 匹配 legacy 公式（不含 `format`），则视为 backwards-compatible 输入
3. `ir_hash` 若定义，是否与 canonical serialization 一致
4. graph owner 只约束自动分配的本地 QID；foreign QID 作为 external occurrence 是合法输入

这些检查的细分边界见 [08-validation.md](08-validation.md)。

## 8. 与其他文档的分工

- [02-gaia-ir.md](02-gaia-ir.md)：定义对象字段本身
- [05-canonicalization.md](05-canonicalization.md)：定义 `content_hash` 的角色、等价/独立证据的 IR 表达、FormalExpr 中间 Knowledge 创建规则
- [08-validation.md](08-validation.md)：定义应如何校验这些字段
- [01-overview.md](01-overview.md)：给出高层总览
