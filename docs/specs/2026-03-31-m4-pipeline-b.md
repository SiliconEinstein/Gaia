# M4 — Pipeline B: Paper Extraction Spec

> **Status:** Draft (revised 2026-04-02)
> **Date:** 2026-03-31
> **实现文件:** `gaia_lkm/core/extract.py`, `gaia_lkm/pipelines/extract.py`

## 概述

M4 从已提取的论文推理链 XML（3 个文件）中解析命题、推理关系和参数估计，产出与 M3 相同结构的 local FactorGraph + 参数化记录，并写入存储。

M4 与 M3 并行（都依赖 M1，不依赖彼此），产出相同的数据结构供 M5 Integrate 消费。

## 输入格式

每篇论文由 3 个 XML 文件组成（已由上游 LLM pipeline 提取完成）：

| 文件 | 内容 |
|------|------|
| `select_conclusion.xml` | 研究问题（problem）+ 结论列表（conclusions with titles） |
| `reasoning_chain.xml` | 每个结论的推理步骤链（steps → conclusion） |
| `review.xml` | 每个结论的前提命题（premises with prior_probability） |

### XML 结构示例

**review.xml** — 前提命题 + prior：
```xml
<inference_unit>
  <premises>
    <premise id="P1" conclusion_id="2" step_id="4"
             prior_probability="0.70"
             title="BaCu3O4 molten-phase promotes more complete reactions"
             name="ba_cu3o4_melt_promotes_reaction">
      命题内容文本...
      <ref type="citation">12</ref>
    </premise>
    ...
  </premises>
</inference_unit>
```

**reasoning_chain.xml** — 推理步骤 + 结论：
```xml
<inference_unit>
  <conclusion_reasoning conclusion_id="2">
    <reasoning>
      <step id="1">推理步骤描述...</step>
      <step id="2">推理步骤描述...<ref type="citation">12</ref></step>
    </reasoning>
    <conclusion id="2" title="结论标题">结论内容文本...</conclusion>
  </conclusion_reasoning>
</inference_unit>
```

**select_conclusion.xml** — 研究问题 + 结论摘要：
```xml
<inference_unit>
  <problem>研究问题描述...</problem>
  <conclusions>
    <conclusion id="1" title="结论标题">结论内容...<problem>该结论对应的子问题</problem></conclusion>
  </conclusions>
</inference_unit>
```

---

## 输出

与 M3 相同结构：

```python
@dataclass
class PipelineBOutput:
    local_variables: list[LocalVariableNode]
    local_factors: list[LocalFactorNode]
    prior_records: list[PriorRecord]
    factor_param_records: list[FactorParamRecord]
    param_sources: list[ParameterizationSource]
    package_id: str              # "paper:{metadata_id}"
    version: str                 # 固定 "1.0.0"（论文不更新版本）
```

---

## 提取规则

### 命题提取 → LocalVariableNode

| XML 来源 | 输出 |
|---|---|
| `review.xml` 的 `<premise>` | `type="claim"`, `visibility="public"` |
| `reasoning_chain.xml` 的 `<conclusion>` | `type="claim"`, `visibility="public"` |
| `select_conclusion.xml` 的 `<problem>` | `type="question"`, `visibility="public"` |

QID 格式：
```
paper:{metadata_id}::{name}        # premise 有 name 属性时
paper:{metadata_id}::conclusion_{id} # conclusion
paper:{metadata_id}::problem        # research problem
```

### 推理关系提取 → LocalFactorNode

每个 `<conclusion_reasoning>` 对应一个 strategy factor：
- `factor_type="strategy"`, `subtype="infer"`
- `premises` = 该 conclusion 关联的所有 premise IDs
- `conclusion` = conclusion 的 QID
- `steps` = reasoning 中的 step 列表

### 参数提取

**PriorRecord**：直接从 `<premise prior_probability="0.70">` 提取
- `variable_id` = premise 的 QID（后续 integrate 时替换为 gcn_id）
- `value` = prior_probability 属性值（Cromwell clamped）
- `source_class = "heuristic"`

**FactorParamRecord**：每个 strategy factor 的条件概率
- 取该 factor 所有 premise 的 prior 均值作为条件概率估计

**ParameterizationSource**：
```
source_id    = "extract_paper_{metadata_id}"
source_class = "heuristic"
model        = "xml_extract_v1"
```

---

## 数据存储

提取完成后调用 M5 integrate 写入存储：

1. `lower()` 产出 local_variables + local_factors + prior_records
2. `integrate()` 写入 local nodes → commit → 写入 global graph + bindings + params

与 M3 共享同一个 integrate 流程。

---

## 关键约束

1. **确定性**：相同 XML 文件 → 相同输出
2. **source_class = "heuristic"**：所有参数记录的 source_class 为 heuristic
3. **不依赖 ML**：纯 XML 解析，不调用 LLM
4. **QID 稳定性**：同一论文的多次提取产出相同 QIDs
5. **与 Pipeline A 输出结构一致**：产出相同的 `(local_variables, local_factors, prior_records, ...)` 结构

---

## 测试要求

用 `tests/fixtures/inputs/papers/` 下的真实论文 XML 作为 fixture：
- `test_extract_premises`：从 review.xml 正确提取 premise → LocalVariableNode
- `test_extract_conclusions`：从 reasoning_chain.xml 正确提取 conclusion → LocalVariableNode
- `test_extract_factors`：每个 conclusion 对应一个 strategy factor
- `test_extract_priors`：prior_probability 正确提取为 PriorRecord
- `test_deterministic`：相同输入产出相同输出
- `test_integrate_paper`：提取 + integrate 端到端，验证数据可查询

---

## 实现文件结构

```
gaia/lkm/core/
    extract.py           # 核心提取算法：解析 3 个 XML → LKM 模型
gaia/lkm/pipelines/
    extract.py           # 薄层 adapter：接收文件路径，调用 core，返回标准输出
```

---

## 与 M3 的对比

| 方面 | M3 (Pipeline A) | M4 (Pipeline B) |
|------|----------------|----------------|
| 输入 | Gaia IR LocalCanonicalGraph | 3 个推理链 XML 文件 |
| source_class | official | heuristic |
| 参数来源 | reviewer 赋值 | XML 中的 prior_probability |
| QID namespace | `reg` | `paper` |
| 确定性 | 是 | 是 |
| 依赖 ML | 否 | 否 |
