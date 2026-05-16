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
- 跨 package 的同题判断、重复计数审查或 registry 侧对齐结论

这些属于相邻层。

## 1. 校验分层

建议把校验分成 3 层：

1. **对象级校验**
   单个 `Knowledge` / `Operator` / `Strategy` / `FormalExpr` 是否自洽
2. **图级校验**
   一个 `LocalCanonicalGraph` 内部引用是否闭合、scope 是否一致
3. **相邻层完整性校验**
   例如 parameterization completeness、lowering preconditions

本文件主要定义前 2 层。第 3 层只做边界说明。

## 2. Knowledge 校验

对每个 `Knowledge`，至少应检查：

1. `id` 必须为有效 QID 格式 `{namespace}:{package_name}::{label}`，label 字符集允许 `[A-Za-z_][A-Za-z0-9_]*`（详见 [03-identity-and-hashing.md §2.1](03-identity-and-hashing.md#21-knowledge-qid)）
2. `type` 属于 `gaia.engine.ir.KnowledgeType` 允许集合：
   - `claim`（唯一携带 prior + belief 的类型）
   - `note`（v0.5 推荐替代 `setting` 的非概率背景说明）
   - `composition`（结构组合；必须带 `template_name` / `template_version` / `sub_knowledge` / `conclusion`）
   - `setting`（legacy 非概率背景）
   - `question`（待研究方向）
   - `context`（legacy 非概率范围限定）
3. `content_hash` 由 Knowledge model 构造时保证（Pydantic model_validator）；graph-level validator 不重复检查；hash 公式见 [03-identity-and-hashing.md](03-identity-and-hashing.md) §3
4. 若某处把它当作可取真值命题引用（如 Operator `variables` / `conclusion` 或 Strategy `premises` / `conclusion`），则其 `type` 必须是 `claim`
5. 含 `parameters` 的 claim 仍然是 claim，不是独立类型
6. helper claim 仍然是 `claim`，不能引入新的 Knowledge primitive
7. 结构型 helper claim **禁止**携带独立的 `PriorRecord`——它们不引入新的中间命题或新的前提，其值由 Operator 确定性决定（见 [04-helper-claims.md](04-helper-claims.md)）
8. `composition` 的 `sub_knowledge` 中每个 ID 必须引用同 graph 中存在的 `Knowledge`；其 `conclusion` 必须引用同 graph 中存在的 `claim`
9. `label` 在同一 `LocalCanonicalGraph` 内必须唯一
10. `LocalCanonicalGraph.namespace` / `package_name` 约束自动生成的本地 QID；显式写入的 foreign QID 允许作为 external reference 出现在 graph 中
11. graph-level closure 的对象是"显式出现在 graph 中的节点集合"，因此 imported external occurrence 若被引用，也必须作为 `Knowledge` 显式存在于该 graph 中

## 3. Operator 校验

对每个 `Operator`，至少应检查：

1. **顶层 Operator** 必须设置 `operator_id`（`lco_` 前缀）和 `scope`，且 `scope` 必须与所属 `LocalCanonicalGraph.scope` 一致；**嵌入在 `FormalStrategy.formal_expr.operators[]` 内的 Operator** 是表达式片段，可省略 `operator_id` 与 `scope`，由宿主 FormalStrategy 拥有（实现见 `gaia.engine.ir.validator._validate_operators`）
2. `variables` 中所有 ID 都必须引用同 graph 中存在的 Knowledge
3. `variables` 中的 Knowledge 必须全部是 `claim`
4. `conclusion` 必须引用同 graph 中存在的 `claim`
5. `conclusion` 不得出现在 `variables` 中——`variables` 只放输入，`conclusion` 独立承载输出
6. Operator 分为三类（见 [02-gaia-ir.md §2.4](02-gaia-ir.md)）：
   - **Directed（`implication`）**：`conclusion` 是结构型 implication helper claim（如 `implies(A,B)` 型）
   - **Expression（`negation`、`conjunction`、`disjunction`）**：`conclusion` 是结构型计算结果 helper claim（如合取输出 `M = A ∧ B`）
   - **Relation（`equivalence`、`contradiction`、`complement`）**：`conclusion` 是结构型 warrant helper claim
7. 关系型 Operator 的 `conclusion` 不允许被作者借来手写任意主观结论
8. 若 `metadata.canonical_name` 缺失或未采用推荐 functor 形式，当前更适合作为 warning / lint，而不是 hard error

这里的 “同 graph 中存在” 指的是 **引用闭合**，不是 **ownership 相同**。  
也就是说，Operator 可以连接 imported claim，只要这些 imported claim 已被显式放入 graph。

helper claim 的命名纪律见 [04-helper-claims.md](04-helper-claims.md)。

## 4. Strategy 校验

对每个 `Strategy`，至少应检查：

1. `strategy_id` 必须使用 `lcs_` 前缀
2. `premises` 中的 Knowledge 必须全部是 `claim`
3. `conclusion` 若非空，必须引用 `claim`
4. `background` 可引用任意允许类型
5. `type` 必须属于允许集合（与 `gaia/engine/ir/strategy.py::StrategyType` 同步，共 14 个）：`infer` | `associate` | `noisy_and`（deprecated → 编译时自动转 `support`，发 `DeprecationWarning`，仍接受） | `deduction` | `reductio`（deferred） | `elimination` | `mathematical_induction` | `case_analysis` | `abduction` | `analogy` | `extrapolation` | `support` | `compare` | `induction`
6. 三种形态互斥：
   - 基本 Strategy：无 `sub_strategies`，无 `formal_expr`
   - `CompositeStrategy`：必须有非空 `sub_strategies`
   - `FormalStrategy`：必须有 `formal_expr`
7. `sub_strategies` 与 `formal_expr` 不得同时出现
8. `sub_strategies` 中的每个值都必须引用同 graph 中存在的 `strategy_id`
9. `sub_strategies` 引用关系必须构成 DAG（无环）
10. `noisy_and` 不应用来压平命名策略的整体语义

与 Operator 一样，Strategy 的 `premises` / `conclusion` / `background` 只检查图内闭合和类型约束，不检查这些 Knowledge 是否都属于当前 graph owner。

## 5. Compose 验证

对每个 `Compose`（实现见 `gaia.engine.ir.validator._validate_one_compose` / `_validate_compose_dag`），至少应检查：

1. `compose_id` 必须以 `lcm_` 前缀开头
2. `inputs / background / warrants` 中的所有 ID 必须引用同 graph 中存在的 `Knowledge`
3. `conclusion` 必须引用同 graph 中存在的 `Knowledge`，且其 `type` 必须是 `claim`
4. `actions` 中的每个 ID 必须引用同 graph 中存在的 `Knowledge`、`Operator`（`lco_`）、`Strategy`（`lcs_`）或其他 `Compose`（`lcm_`）；其中 Operator 与 Strategy 仅当其 ID 已显式赋值时才能被 Compose 引用
5. `actions` 中**不得包含 `compose.compose_id` 自身**（不允许自引用）
6. 多个 Compose 之间通过 `actions` 形成的引用关系必须构成 **DAG**——`gaia.engine.ir.validator._validate_compose_dag` 会沿这些边做循环检测，发现环时给出 cycle 路径

## 6. FormalExpr 校验

对每个 `FormalExpr`，至少应检查：

1. 只包含 `Operator`
2. 所有内部 Operator 满足各自的 Operator 校验规则
3. 内部 Operator 引用关系必须构成 DAG（无环）
4. 其引用到的中间 claim 必须在同 graph 中显式存在
5. 私有中间节点（不出现在任何 Strategy 的 `premises`/`conclusion` 中）**禁止**被外部 Strategy 引用——违反时报 error（见 [04-helper-claims.md](04-helper-claims.md)）
6. **引用闭合性**：FormalExpr 内每个 Operator 的 `variables` 和 `conclusion` 所引用的 claim，必须属于以下三类之一——否则报 error：
   - 该 FormalStrategy 的 `premises`（接口输入）
   - 该 FormalStrategy 的 `conclusion`（接口输出）
   - 同一 FormalExpr 内另一个 Operator 的 `conclusion`（内部中间节点）

## 7. Graph 校验

对每个 graph，至少应检查：

1. `scope` 与所有对象 ID 格式一致
2. 图内所有引用都闭合
3. 不允许引用未在当前 graph 中显式物化的对象；external reference 若参与引用，也必须先作为 `Knowledge` 出现在当前 graph 中
4. `ir_hash` 若定义，则必须与 canonical serialization 一致
5. 同一 graph 内不应出现重复 ID
6. `namespace` 必须属于允许集合（`reg` | `paper`）

identity 与 hashing 的细节见 [03-identity-and-hashing.md](03-identity-and-hashing.md)。

## 8. LocalCanonicalGraph 校验

至少应检查：

1. `steps` 允许存在
2. 内容字段允许完整保留
3. Knowledge 使用 QID 格式；Strategy 使用 `lcs_`；顶层 Operator 使用 `lco_`；Compose 使用 `lcm_`
4. `gaia._meta.IR_SCHEMA` 在与 LKM 等下游交换 IR 时通过 `check_ir_compat` 校验前缀（详见 [06-parameterization.md](06-parameterization.md) "与 IR schema 版本的关系" 段）；schema 形状漂移时 pre-push 钩子 `scripts/check_ir_schema_bump.py` 强制要求 bump

## 9. 与相邻层的边界

以下内容**不是 Gaia IR core validation**，但通常会在相邻层一起检查：

- parameterization completeness
- lowering preconditions
- backend runtime diagnostics
- BP convergence

这些分别见：

- [06-parameterization.md](06-parameterization.md)
- [07-lowering.md](07-lowering.md)
- [../bp/inference.md](../bp/inference.md)

## 10. 推荐输出形式

一个 validator 至少应能输出：

- `valid: bool`
- `errors: list[...]`
- `warnings: list[...]`

其中：

- **error** 表示 contract-invalid，必须阻止后续流程
- **warning** 表示 contract-valid 但存在风险、兼容性问题或未来可能收紧的行为

## 11. 当前仍待细化的点

- canonical serialization 的标准化顺序与 `ir_hash` 精确定义
- helper claim 的标准命名是否需要更强约束
- `strategy_id` / `operator_id` 的规范生成算法是否写成强约束
