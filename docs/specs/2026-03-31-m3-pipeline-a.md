# M3 — Pipeline A: Gaia IR Lowering Spec

> **Status:** Draft
> **Date:** 2026-03-31
> **实现文件:** `gaia_lkm/pipelines/lower.py`

## 概述

M3 将上游 `gaia.gaia_ir.LocalCanonicalGraph` lower 为 LKM 的 `(list[LocalVariableNode], list[LocalFactorNode])`，并从 validated review reports 提取参数化记录。Lowering 是确定性的——相同输入永远产出相同结果。

M3 是 Ingest 的第一步（Pipeline A 路径），产出 local FactorGraph 供 M5 Integrate 消费。

## 上游参考

- `Gaia/docs/foundations/gaia-ir/07-lowering.md`：lowering 契约权威来源
- `Gaia/docs/foundations/gaia-ir/02-gaia-ir.md`：Knowledge、Strategy、Operator schema
- `Gaia/docs/foundations/gaia-ir/04-helper-claims.md`：private variable 的 visibility 规则
- `Gaia/docs/foundations/gaia-ir/06-parameterization.md`：PriorRecord/StrategyParamRecord schema
- `Gaia/docs/foundations/ecosystem/05-review-and-curation.md`：review report 产出流程

---

## 输入

```python
@dataclass
class PipelineAInput:
    package: LocalCanonicalGraph  # 上游 gaia.gaia_ir 的完整包
    review_reports: list[dict]     # validated review reports（经 registry 验证）
    package_id: str
    version: str
```

- `LocalCanonicalGraph` 来自上游 `gaia.gaia_ir`，只读，不修改
- `review_reports` 是通过 registry 完整验证流程的 assigned review reports

## 输出

```python
@dataclass
class PipelineAOutput:
    local_variables: list[LocalVariableNode]
    local_factors: list[LocalFactorNode]
    prior_records: list[PriorRecord]
    factor_param_records: list[FactorParamRecord]
    param_sources: list[ParameterizationSource]
    package_id: str
    version: str
```

---

## Lowering 规则

严格对齐 `Gaia/docs/foundations/gaia-ir/07-lowering.md`。

### Knowledge → LocalVariableNode

| 输入 Knowledge 类型 | 输出 LocalVariableNode |
|---|---|
| `claim` | `type="claim"`, `visibility="public"` |
| `setting` | `type="setting"`, `visibility="public"` |
| `question` | `type="question"`, `visibility="public"` |

字段映射：

```
LocalVariableNode:
    id            = Knowledge.id (QID)
    type          = Knowledge.type
    visibility    = "public"
    content       = Knowledge.content
    content_hash  = compute_content_hash(type, content, parameters)  # 自动计算
    parameters    = Knowledge.parameters
    source_package = package_id
```

### FormalStrategy 展开 → private variable nodes

FormalStrategy 展开时产生的中间 Knowledge（如 deduction 的 conjunction 结果 M）→ `visibility="private"` 的 LocalVariableNode。

```
LocalVariableNode:
    id            = 中间 Knowledge 的 QID（由 compiler/展开器生成）
    type          = "claim"
    visibility    = "private"
    content       = 中间 Knowledge 的 content
    content_hash  = compute_content_hash(...)
    parameters    = []  # 中间节点通常无参数
    source_package = package_id
```

**Private variable 规则**（对齐 `04-helper-claims.md`）：
- 不参与 canonicalization（不走 content_hash dedup）
- 禁止有 PriorRecord
- 不暴露给外部查询

### Strategy → LocalFactorNode

| 输入 Strategy 形态 | 输出 |
|---|---|
| 叶子 Strategy (`infer`, `noisy_and`) | 一个 `factor_type="strategy"` 的 LocalFactorNode |
| FormalStrategy (`deduction`, `abduction`, ...) | 展开为内部 Operator + private variables |
| CompositeStrategy | 递归展开为 leaf strategies |

叶子 Strategy 映射：

```
LocalFactorNode:
    id            = "lfac_{sha256(strategy_id)[:16]}"
    factor_type   = "strategy"
    subtype       = Strategy.type  # "infer" | "noisy_and"
    premises      = Strategy.premises  # QIDs
    conclusion    = Strategy.conclusion  # QID
    background    = Strategy.background  # QIDs (setting/question)
    steps         = Strategy.steps
    source_package = package_id
```

### Operator → LocalFactorNode

```
LocalFactorNode:
    id            = "lfac_{sha256(operator_id)[:16]}"
    factor_type   = "operator"
    subtype       = Operator.operator  # "equivalence" | "contradiction" | ...
    premises      = Operator.variables  # QIDs
    conclusion    = Operator.conclusion  # QID
    background    = None
    steps         = None
    source_package = package_id
```

### CompositeStrategy 处理

CompositeStrategy 递归展开：遍历 `sub_strategies`，对每个子策略按其形态（叶子/Formal/Composite）递归 lower。CompositeStrategy 本身不产出 LocalFactorNode。

### FormalStrategy 展开

FormalStrategy 的 `formal_expr` 包含内部 Operator 列表。展开时：

1. 为每个 FormalExpr 内部的中间 Knowledge 创建 `visibility="private"` 的 LocalVariableNode
2. 为每个内部 Operator 创建 `factor_type="operator"` 的 LocalFactorNode
3. FormalStrategy 本身不产出独立的 factor（它被展开为内部结构）

---

## 参数提取

从 validated review reports 提取参数化记录。

### PriorRecord 提取

对每个 review report 中给新命题赋的 prior：

```
PriorRecord:
    variable_id  = 对应 claim 的 QID（后续 integrate 时映射为 gcn_id）
    value        = review 给出的 prior（Cromwell clamped）
    source_id    = ParameterizationSource.source_id
    created_at   = review report timestamp
```

**注意**：PriorRecord.variable_id 在 Pipeline A 产出时暂时使用 local QID。M5 Integrate 时替换为 gcn_id。

### FactorParamRecord 提取

对每条需要概率参数的推理链（`infer` / `noisy_and`）：

```
FactorParamRecord:
    factor_id                = 对应 LocalFactorNode.id
    conditional_probabilities = review 给出的条件概率（Cromwell clamped）
    source_id                = ParameterizationSource.source_id
    created_at               = review report timestamp
```

### ParameterizationSource

每个 review report 对应一个 ParameterizationSource：

```
ParameterizationSource:
    source_id    = "review_{reviewer_id}_{timestamp}"
    source_class = "official"  # Pipeline A 的参数来自 validated review
    model        = reviewer ID / model name
    policy       = review policy (如有)
    created_at   = review report timestamp
```

---

## 关键约束

1. **确定性**：相同 `LocalCanonicalGraph` + 相同 `review_reports` → 相同输出
2. **上游只读**：不修改 `gaia.gaia_ir.*` 对象
3. **Lowering 和 canonicalize 严格分离**：M3 只做 lowering（IR → local FactorGraph），不做 canonicalization（local → global）
4. **FormalStrategy 全展开**：当前实现默认展开所有 FormalStrategy（不折叠）
5. **source_class = "official"**：Pipeline A 所有参数记录的 source_class 必须为 official

---

## 测试要求

- `test_knowledge_to_local_variable`：各类型 Knowledge 正确映射为 LocalVariableNode
- `test_leaf_strategy_to_local_factor`：infer/noisy_and Strategy 正确映射
- `test_operator_to_local_factor`：各类型 Operator 正确映射
- `test_formal_strategy_expansion`：FormalStrategy 正确展开为 operators + private variables
- `test_composite_strategy_recursive`：CompositeStrategy 递归展开
- `test_review_report_extraction`：正确提取 PriorRecord/FactorParamRecord/ParameterizationSource
- `test_deterministic`：相同输入产出相同输出
- `test_private_variable_visibility`：FormalStrategy 中间节点 visibility 为 private

纯单元测试（不需要 DB），放在 `tests/unit/test_pipeline_a.py`。

---

## 实现文件结构

```
gaia_lkm/pipelines/
    __init__.py
    lower.py            # lower_package() 主函数
    _strategy_expand.py # FormalStrategy/CompositeStrategy 展开逻辑
    _param_extract.py   # review report → 参数记录提取
```
