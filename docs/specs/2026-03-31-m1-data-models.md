# M1 — LKM 数据模型 Spec

> **Status:** Draft
> **Date:** 2026-03-31
> **实现文件:** `gaia_lkm/models/`

## 概述

M1 定义 LKM 自有的 Pydantic v2 models。这些 models 是 LKM 内部存储格式，与上游 `gaia.gaia_ir.*` 完全独立——后者是 ingest 时的输入，不是 LKM 存储格式。

本 spec 是 M2（storage schema）、M3（Pipeline A lowering 输出）、M5（integrate）的基础契约。

## 上游参考

- `Gaia/docs/foundations/gaia-ir/02-gaia-ir.md`：Knowledge、Strategy、Operator schema 权威来源
- `Gaia/docs/foundations/gaia-ir/03-identity-and-hashing.md`：content_hash 计算规则
- `Gaia/docs/foundations/gaia-ir/05-canonicalization.md §5`：CanonicalBinding 字段定义
- `Gaia/docs/foundations/gaia-ir/06-parameterization.md`：PriorRecord / StrategyParamRecord schema
- `Gaia/gaia/gaia_ir/knowledge.py`：Parameter、LocalCanonicalRef、content_hash 实现参考
- `Gaia/gaia/gaia_ir/strategy.py`：Step 结构参考
- `Gaia/gaia/gaia_ir/binding.py`：CanonicalBinding 结构参考
- `Gaia/gaia/gaia_ir/parameterization.py`：PriorRecord、StrategyParamRecord 实现参考

---

## 辅助类型

这三个辅助类型直接对齐上游定义，在 LKM 内复用语义（但独立实现，不 import 上游）。

### Parameter

全称 claim 的量化变量。封闭 claim 的 `parameters=[]`。

```python
class Parameter(BaseModel):
    name: str   # 变量名，如 "x"
    type: str   # 变量类型约束，如 "material"
```

### Step

推理过程的单步描述，**仅存在于 local 层**。

```python
class Step(BaseModel):
    reasoning: str               # 自然语言推理描述
    premises:  list[str] | None  # 此步的 premise IDs（可选）
    conclusion: str | None       # 此步的 conclusion ID（可选）
```

### LocalCanonicalRef

对 local variable node 的引用，用于 GlobalVariableNode 的 `representative_lcn` 和 `local_members`。

```python
class LocalCanonicalRef(BaseModel):
    local_id:   str   # QID，如 "reg:galileo::ybco_90k"
    package_id: str
    version:    str
```

**命名说明**：上游 `gaia_ir/knowledge.py` 中对应字段名为 `local_canonical_id`，LKM 重命名为 `local_id`（更简洁，与 `CanonicalBinding.local_id` 保持一致）。语义完全一致。

---

## 核心 Models

### LocalVariableNode

存入 `local_variable_nodes` 表。对应上游 `Knowledge`（local 层）。

```python
class LocalVariableNode(BaseModel):
    id:           str                          # QID: {namespace}:{package_name}::{label}
    type:         Literal["claim", "setting", "question"]
    visibility:   Literal["public", "private"] # 见下方 visibility 规则
    content:      str                          # 唯一的内容存储位置
    content_hash: str                          # SHA-256(type+content+sorted(params))，不含 package_id
    parameters:   list[Parameter]              # 封闭 claim 为 []
    source_package: str                        # 来源包 ID
    metadata:     dict | None = None           # 可选：refs、schema 分类等
```

**Visibility 规则**（对齐 `gaia-ir/04-helper-claims.md`）：

| visibility | 来源 | canonicalization | PriorRecord | 暴露给查询 |
|------------|------|-----------------|-------------|-----------|
| `public`   | Knowledge(claim/setting/question) | 参与 | 可有（仅 claim） | 是 |
| `private`  | FormalStrategy/FormalExpr 的内部中间节点 | 不参与 | 禁止 | 否 |

**QID 格式**（对齐 `gaia-ir/03-identity-and-hashing.md §2.1`）：

```
{namespace}:{package_name}::{label}
```

- `namespace`: `reg`（注册表包）或 `paper`（提取的论文）
- `package_name`: 在各自 namespace 内唯一（reg 由 registry 强制，paper 由数据库 metadata ID 保证）
- `label`: 包内唯一的人类可读标签

---

### LocalFactorNode

存入 `local_factor_nodes` 表。对应上游 `Strategy`（叶子和 formal，不含 CompositeStrategy 展开后的叶子）或 `Operator`，以 `factor_type` 区分。

**设计决策**：LKM 将上游的 `Strategy` 和 `Operator` 统一为 `LocalFactorNode`，以 `factor_type` 区分。这是存储层的简化——二者在图中都是连接 variable nodes 的 hyperedge，差别只是是否需要概率参数。

```python
class LocalFactorNode(BaseModel):
    id:             str                       # 本地唯一 ID，格式: "lfac_{sha256[:16]}"
    factor_type:    Literal["strategy", "operator"]
    subtype:        str                       # 见下方 subtype 枚举
    premises:       list[str]                 # premise variable IDs（QID 格式）
                                              # operator 类型对应上游 Operator.variables
    conclusion:     str                       # conclusion variable ID（QID 格式）
    background:     list[str] | None = None   # 上下文 Knowledge IDs（仅 strategy 有）
                                              # 对应上游 Strategy.background（setting/question）
                                              # 不参与概率推理，仅作上下文依赖
    steps:          list[Step] | None = None  # 推理步骤（仅 strategy 有；global 层不存）
    source_package: str                       # 来源包 ID
    metadata:       dict | None = None
```

**operator 类型的字段映射**：

| LKM 字段 | Gaia IR 对应 | 说明 |
|---------|------------|------|
| `premises` | `Operator.variables` | 输入 Knowledge IDs（有序） |
| `conclusion` | `Operator.conclusion` | 结果 claim（含 helper claim） |
| `background` | 无 | operator 无 background，始终为 None |
| `steps` | 无 | operator 无推理步骤，始终为 None |

**strategy 类型的字段映射**：

| LKM 字段 | Gaia IR 对应 | 说明 |
|---------|------------|------|
| `premises` | `Strategy.premises` | 概率推理的前提（必须是 claim） |
| `conclusion` | `Strategy.conclusion` | 推理结论（必须是 claim） |
| `background` | `Strategy.background` | 上下文依赖（任意类型，不进入 BP） |
| `steps` | `Strategy.steps` | 推理步骤（local 层保留） |

**subtype 枚举**（严格对齐 `gaia-ir/02-gaia-ir.md §2.2` 和 §3.3）：

| factor_type | subtype | 上游对应 | 需要 FactorParamRecord |
|-------------|---------|---------|----------------------|
| `strategy` | `infer` | Strategy(type=infer) | 是（2^k 参数） |
| `strategy` | `noisy_and` | Strategy(type=noisy_and) | 是（1 个参数 p） |
| `strategy` | `deduction` | FormalStrategy(type=deduction) | 否 |
| `strategy` | `abduction` | FormalStrategy(type=abduction) | 否 |
| `strategy` | `induction` | FormalStrategy(type=induction) | 否 |
| `strategy` | `analogy` | FormalStrategy(type=analogy) | 否 |
| `strategy` | `extrapolation` | FormalStrategy(type=extrapolation) | 否 |
| `strategy` | `reductio` | FormalStrategy(type=reductio) | 否 |
| `strategy` | `elimination` | FormalStrategy(type=elimination) | 否 |
| `strategy` | `mathematical_induction` | FormalStrategy(type=mathematical_induction) | 否 |
| `strategy` | `case_analysis` | FormalStrategy(type=case_analysis) | 否 |
| `operator` | `implication` | Operator(operator=implication) | 否 |
| `operator` | `equivalence` | Operator(operator=equivalence) | 否 |
| `operator` | `contradiction` | Operator(operator=contradiction) | 否 |
| `operator` | `complement` | Operator(operator=complement) | 否 |
| `operator` | `conjunction` | Operator(operator=conjunction) | 否 |
| `operator` | `disjunction` | Operator(operator=disjunction) | 否 |
| `operator` | `instantiation` | （lowering 产生，用于全称 claim 实例化） | 否 |

**注意**：CompositeStrategy 在 lowering 时展开为 leaf strategies，不直接出现在 LocalFactorNode 中。FormalStrategy 展开为 operators + private variable nodes。

---

### GlobalVariableNode

存入 `global_variable_nodes` 表。对应上游 `Knowledge`（global 层），**不存 content**。

```python
class GlobalVariableNode(BaseModel):
    id:                  str                       # gcn_id，如 "gcn_abc123"
    type:                Literal["claim", "setting", "question"]
    visibility:          Literal["public", "private"]
    content_hash:        str                       # 从 representative_lcn 同步的 denormalized 指纹
    parameters:          list[Parameter]
    representative_lcn:  LocalCanonicalRef         # 代表性 local node（content 从此获取）
    local_members:       list[LocalCanonicalRef]   # 所有绑定到此的 local nodes
    metadata:            dict | None = None
```

**三种 type 均进入 global graph**：

`claim`、`setting`、`question` 三种 Knowledge 类型均参与 global graph（`type` 字段为三选一）。差异在于：

| type | PriorRecord | 参与 BP 推理 | 参与 canonicalization | 参与子图查询 |
|------|-------------|-------------|----------------------|------------|
| `claim` | 是（visibility=public） | 是 | 是 | 是 |
| `setting` | 否 | 否（background 依赖，不作 premises/conclusion） | 是 | 是 |
| `question` | 否 | 否（background 依赖，不作 premises/conclusion） | 是 | 是 |

`setting` 和 `question` 存入 global graph 的原因：消费端构建子图时需要完整上下文（Strategy.background 引用的节点必须在 global graph 中可解析）。

**content 访问路径**：
```
global_variable_nodes[gcn_id].representative_lcn.local_id
  → local_variable_nodes[local_id].content
```
两次主键查询，不 join。

**gcn_id 生成**：

```python
import uuid

def new_gcn_id() -> str:
    """生成新的 global canonical node ID。UUID-based，与内容无关，分配一次不再重算。"""
    return f"gcn_{uuid.uuid4().hex[:16]}"
```

**gcn_id 规则**：
- `create_new` 时调用 `new_gcn_id()` 一次生成，永不重算
- 不等于 content_hash（content 变化不影响 ID）
- representative_lcn 更换时 gcn_id 不变
- 格式：`gcn_` + 16 位十六进制（来自 UUID4，全局唯一）

---

### GlobalFactorNode

存入 `global_factor_nodes` 表。对应上游 `Strategy`/`Operator`（global 层），**不存 steps**。

```python
class GlobalFactorNode(BaseModel):
    id:                str                       # 全局唯一 ID，格式: "gfac_{sha256[:16]}"
    factor_type:       Literal["strategy", "operator"]
    subtype:           str                       # 同 LocalFactorNode.subtype 枚举
    premises:          list[str]                 # premise global variable IDs（gcn_id）
    conclusion:        str                       # conclusion global variable ID（gcn_id）
    representative_lfn: str                      # 代表性 local factor ID（lfac_ 前缀）；create_new 时设置，不再更新
    source_package:    str                       # 最初创建此 factor 的来源包
    metadata:          dict | None = None
```

**命名说明**：上游使用 `gcs_` 前缀（strategy-specific）；LKM 使用 `gfac_` 前缀（factor 统一命名，覆盖 strategy 和 operator）。语义一致，命名更一致。

**representative_lfn 用途**：integrate 时首次 `create_new` 时设置，指向第一个产生该 global factor 的 local factor。**仅作 steps 访问的便捷指针**，完整的多包溯源信息在 `CanonicalBinding`（`binding_type=factor`）中。

**steps 访问路径**（如需要）：
```
global_factor_nodes[gfac_id].representative_lfn
  → local_factor_nodes[lfn_id].steps
```

**多包溯源**（如需要）：
```
canonical_bindings WHERE global_id = gfac_xxx AND binding_type = "factor"
  → 所有贡献此 global factor 的 local factors（跨包）
```

---

### CanonicalBinding

存入 `canonical_bindings` 表。`local → global` 的一等实体，覆盖 variable 和 factor 两种绑定。每次 integrate 时写入，不可变。

```python
class CanonicalBinding(BaseModel):
    local_id:     str              # variable QID 或 local factor ID（lfac_ 前缀）
    global_id:    str              # gcn_id 或 gfac_id
    binding_type: Literal["variable", "factor"]  # 区分两种 binding
    package_id:   str
    version:      str
    decision:     Literal["match_existing", "create_new", "equivalent_candidate"]
    reason:       str              # 如 "content_hash exact match" / "structure exact match"
```

**与上游的关系**（`gaia-ir/05-canonicalization.md §5`）：
上游 `CanonicalBinding` 覆盖 Knowledge（variable）和 Strategy/Operator（factor）两类；字段 `local_canonical_id`/`global_canonical_id` 重命名为 `local_id`/`global_id`（更简洁）。LKM 新增 `binding_type` 字段作显式区分。

**不可变性**：CanonicalBinding 一旦写入不修改。新版本包重新 ingest 时追加新记录。

---

### PriorRecord

存入 `prior_records` 表。对应上游 `PriorRecord`，字段完全对齐。

```python
class PriorRecord(BaseModel):
    variable_id: str      # gcn_id（global variable node ID）
    value:       float    # ∈ (ε, 1-ε)，Cromwell clamped，ε=1e-3
    source_id:   str      # → ParameterizationSource.source_id
    created_at:  datetime
```

**约束**：
- 仅 `visibility=public` 且 `type=claim` 的 variable 可有 PriorRecord
- 同一 `variable_id` 可有多条记录（来自不同 source）
- 上游字段名为 `gcn_id`，LKM 重命名为 `variable_id`（语义一致，更清晰）

---

### FactorParamRecord

存入 `factor_param_records` 表。对应上游 `StrategyParamRecord`。

```python
class FactorParamRecord(BaseModel):
    factor_id:                str          # global factor node ID（gfac_ 前缀）
    conditional_probabilities: list[float] # Cromwell clamped
    source_id:                str          # → ParameterizationSource.source_id
    created_at:               datetime
```

**与上游的关系**：
上游 `StrategyParamRecord` 使用 `strategy_id`（gcs_ 前缀）；LKM 使用 `factor_id`（gfac_ 前缀）。语义一致——都指向全局 Strategy node。LKM 命名更一致（factor 统一命名）。

**约束**：
- 仅 `factor_type=strategy` 且 `subtype ∈ {infer, noisy_and}` 的 factor 需要 FactorParamRecord
- FormalStrategy subtypes（deduction/abduction/...）不需要独立 FactorParamRecord（行为从结构导出）
- `conditional_probabilities` 长度：`infer` = 2^k（k 为 premises 数），`noisy_and` = 1

---

### ParameterizationSource

存入 `param_sources` 表。描述参数记录的产生来源。**LKM 在上游基础上增加 `source_class` 字段**。

```python
class ParameterizationSource(BaseModel):
    source_id:    str                                          # 唯一 ID
    source_class: Literal["official", "heuristic", "provisional"]  # LKM 自有字段
    model:        str                                          # 如 reviewer ID、LLM model name
    policy:       str | None = None                            # 如 "conservative"
    config:       dict | None = None                           # 配置详情
    created_at:   datetime
```

**source_class 层级**（LKM-specific，不在上游契约中）：

| source_class | 来源 | 优先级 |
|---|---|---|
| `official` | 通过 registry 完整验证的 validated review reports（Pipeline A） | 最高 |
| `heuristic` | XML 提取规则估计（Pipeline B） | 中 |
| `provisional` | mock / 自动化 review | 最低 |

**不可逆规则**：`official` 参数永远不被 `heuristic` 或 `provisional` 覆盖。Resolution policy 在组装参数时按此层级过滤。

---

### BeliefSnapshot

存入 `belief_snapshots` 表。全球 BP 每次运行后写入一份快照。

```python
class BeliefSnapshot(BaseModel):
    snapshot_id:       str
    timestamp:         datetime
    graph_hash:        str            # 运行时图结构哈希
    resolution_policy: str            # "latest" | "source:<source_id>"
    prior_cutoff:      datetime       # 参数截止时间（保证可复现）
    beliefs:           dict[str, float]  # gcn_id → belief 值
    converged:         bool
    iterations:        int
    max_residual:      float
```

**可复现性**：`graph_hash + resolution_policy + prior_cutoff` 三者唯一确定一次 BP 运行。

---

## content_hash 计算

完全对齐上游实现（`Gaia/gaia/gaia_ir/knowledge.py`）：

```python
import hashlib
import json

def compute_content_hash(type_: str, content: str, parameters: list[Parameter]) -> str:
    """SHA-256(type + content + sorted(parameters))，不含 package_id。"""
    sorted_params = sorted((p.name, p.type) for p in parameters)
    payload = f"{type_}|{content}|{sorted_params}"
    return hashlib.sha256(payload.encode()).hexdigest()
```

**特性**：
- 不含 `package_id`，因此跨包同内容的 local nodes 产生相同的 `content_hash`
- 用于 integrate 时的 O(1) dedup 查找（全局索引）
- 不是对象主键，不替代 `id`

---

## 与 02-storage.md 的差异说明

`02-storage.md` 中的 `variable_node.sources[]` 来源列表已被 `CanonicalBinding` 独立表替代（设计演进）。`02-storage.md §不存储的内容` 中关于 CanonicalBinding 的说明需要更新——这是 TODO，不影响 M1 实现。

---

## 关键约束汇总

1. `content_hash` 必须用上述算法计算，不可自定义
2. QID 格式必须为 `{namespace}:{package_name}::{label}`，namespace ∈ `{reg, paper}`
3. `visibility=private` 的 node 禁止有 PriorRecord
4. `factor_type=operator` 的 node 禁止有 FactorParamRecord
5. `official` source_class 的参数记录不可被 `heuristic`/`provisional` 覆盖
6. GlobalVariableNode 不存 `content` 字段
7. GlobalFactorNode 不存 `steps` 字段
8. CanonicalBinding 不可变（写入后不修改）
9. `BeliefSnapshot.beliefs` 只包含 `visibility=public` 的 variable 的 belief 值

---

## 测试要求

- `test_content_hash_cross_package_stable`：不同 package_id 相同内容产生相同 hash
- `test_content_hash_parameter_order_stable`：parameters 顺序不影响 hash
- `test_prior_record_private_node_rejected`：private node 创建 PriorRecord 应抛出异常
- `test_factor_param_record_operator_rejected`：operator factor 创建 FactorParamRecord 应抛出异常
- `test_source_class_priority`：官方 source 不被低优先级 source 覆盖
- `test_cromwell_clamping`：prior value 0.0 和 1.0 被 clamp 到 `[ε, 1-ε]`

所有 model validation 可用纯单元测试（不需要 DB），放在 `tests/unit/test_models.py`。

---

## 实现文件结构

```
gaia_lkm/models/
  __init__.py          # 导出所有 public models
  variable.py          # LocalVariableNode, GlobalVariableNode, Parameter, LocalCanonicalRef
  factor.py            # LocalFactorNode, GlobalFactorNode, Step
  binding.py           # CanonicalBinding
  parameterization.py  # PriorRecord, FactorParamRecord, ParameterizationSource
  inference.py         # BeliefSnapshot
  _hash.py             # compute_content_hash（内部工具函数）
```
