# Validation — 结构校验契约

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本文档定义 Gaia IR 的结构校验边界。它回答“什么样的 IR 是合法的”，而不是“某个 backend 如何运行它”。

## 目的

Gaia IR 的 validation 用来阻止 contract-invalid 的图进入后续阶段。

它主要覆盖三类问题：

- schema 是否完整
- 引用与层级是否自洽
- 图是否满足 Gaia IR 的结构不变量

validation 的职责是**验证结构合法性**。  
它不负责：

- 参数值如何选择
- BP 是否收敛
- 某个 backend 的运行时诊断

这些属于相邻层。

## 1. 校验分层

建议把校验分成 4 层：

1. **对象级校验**
   单个 `Knowledge` / `Operator` / `Strategy` / `FormalExpr` 是否自洽
2. **图级校验**
   一个 `LocalCanonicalGraph` / `GlobalCanonicalGraph` 内部引用是否闭合、scope 是否一致
3. **层级校验**
   local 与 global 的字段约束是否满足
4. **相邻层完整性校验**
   例如 parameterization completeness、lowering preconditions

本文件主要定义前 3 层。第 4 层只做边界说明。

## 2. Knowledge 校验

对每个 `Knowledge`，至少应检查：

1. `id` 前缀与 graph scope 一致
   - local: `lcn_`
   - global: `gcn_`
2. `type` 属于允许集合
   - `claim`
   - `setting`
   - `question`
3. `content_hash` 若存在，必须与 `type + content + sorted(parameters)` 的标准计算一致
4. global `Knowledge` 若从 `representative_lcn` 同步 `content_hash`，则其值必须与当前代表内容一致
5. 若某处把它当作可取真值命题引用，则其 `type` 必须是 `claim`
6. 含 `parameters` 的 claim 仍然是 claim，不是独立类型
7. helper claim 仍然是 `claim`，不能引入新的 Knowledge primitive
8. 结构型 helper claim **禁止**携带独立的 `PriorRecord`——它们不引入新的中间命题或新的前提，其值由 Operator 确定性决定（见 [04-helper-claims.md §6](04-helper-claims.md#6-与-parameterization-的关系)）

## 3. Operator 校验

对每个 `Operator`，至少应检查：

1. `operator_id` 前缀与 graph scope 一致
   - local: `lco_`
   - global: `gco_`
2. `variables` 中所有 ID 都必须引用同 graph 中存在的 Knowledge
3. `variables` 中的 Knowledge 必须全部是 `claim`
4. `conclusion` 必须引用同 graph 中存在的 `claim`
5. `conclusion` 不得出现在 `variables` 中——`variables` 只放输入，`conclusion` 独立承载输出
6. Operator 分为两类（见 [02-gaia-ir.md §2.4](02-gaia-ir.md#24-不变量)）：
   - **Directed（`implication`、`conjunction`）**：`conclusion` 是输出 claim
   - **Relation（`equivalence`、`contradiction`、`complement`、`disjunction`）**：`conclusion` 是结构型 helper claim
7. 关系型 Operator 的 `conclusion` 不允许被作者借来手写任意主观结论
9. 若 `metadata.canonical_name` 缺失或未采用推荐 functor 形式，当前更适合作为 warning / lint，而不是 hard error

helper claim 的命名纪律见 [04-helper-claims.md](04-helper-claims.md)。

## 4. Strategy 校验

对每个 `Strategy`，至少应检查：

1. `strategy_id` 前缀与 graph scope 一致
   - local: `lcs_`
   - global: `gcs_`
2. `premises` 中的 Knowledge 必须全部是 `claim`
3. `conclusion` 若非空，必须引用 `claim`
4. `background` 可引用任意允许类型
5. `type` 必须属于允许集合
6. 三种形态互斥：
   - 基本 Strategy：无 `sub_strategies`，无 `formal_expr`
   - `CompositeStrategy`：必须有非空 `sub_strategies`
   - `FormalStrategy`：必须有 `formal_expr`
7. `sub_strategies` 与 `formal_expr` 不得同时出现
8. `sub_strategies` 中的每个值都必须引用同 graph 中存在的 `strategy_id`
9. `sub_strategies` 引用关系必须构成 DAG（无环）
10. `noisy_and` 不应用来压平命名策略的整体语义

## 5. FormalExpr 校验

对每个 `FormalExpr`，至少应检查：

1. 只包含 `Operator`
2. 所有内部 Operator 满足各自的 Operator 校验规则
3. 内部 Operator 引用关系必须构成 DAG（无环）
4. 其引用到的中间 claim 必须在同 graph 中显式存在
5. 私有中间节点（不出现在任何 Strategy 的 `premises`/`conclusion` 中）**禁止**被外部 Strategy 引用——违反时报 error（见 [04-helper-claims.md §3](04-helper-claims.md#3-formalexpr-内部-claim-的封装)）
6. **引用闭合性**：FormalExpr 内每个 Operator 的 `variables` 和 `conclusion` 所引用的 claim，必须属于以下三类之一——否则报 error：
   - 该 FormalStrategy 的 `premises`（接口输入）
   - 该 FormalStrategy 的 `conclusion`（接口输出）
   - 同一 FormalExpr 内另一个 Operator 的 `conclusion`（内部中间节点）

## 6. Graph 校验

对每个 graph，至少应检查：

1. `scope` 与所有对象 ID 前缀一致
2. 图内所有引用都闭合
3. 不允许引用跨 graph 不存在的本地对象
4. `ir_hash` 若定义，则必须与 canonical serialization 一致
5. 同一 graph 内不应出现重复 ID

identity 与 hashing 的细节见 [03-identity-and-hashing.md](03-identity-and-hashing.md)。

## 7. Local / Global 层级校验

### 7.1 LocalCanonicalGraph

至少应检查：

1. `steps` 允许存在
2. local 内容字段允许完整保留
3. local 对象一律使用 `lcn_ / lcs_ / lco_`

### 7.2 GlobalCanonicalGraph

至少应检查：

1. `steps` 不应存在于 global Strategy 上
2. global 对象一律使用 `gcn_ / gcs_ / gco_`
3. global graph 只保留结构，不复制 local `steps`

## 8. 与相邻层的边界

以下内容**不是 Gaia IR core validation**，但通常会在相邻层一起检查：

- parameterization completeness
- lowering preconditions
- backend runtime diagnostics
- BP convergence

这些分别见：

- [06-parameterization.md](06-parameterization.md)
- [07-lowering.md](07-lowering.md)
- [../bp/inference.md](../bp/inference.md)

## 9. 推荐输出形式

一个 validator 至少应能输出：

- `valid: bool`
- `errors: list[...]`
- `warnings: list[...]`

其中：

- **error** 表示 contract-invalid，必须阻止后续流程
- **warning** 表示 contract-valid 但存在风险、兼容性问题或未来可能收紧的行为

## 10. 当前仍待细化的点

- canonical serialization 的标准化顺序与 `ir_hash` 精确定义
- helper claim 的标准命名是否需要更强约束
- `strategy_id` / `operator_id` 的规范生成算法是否写成强约束
