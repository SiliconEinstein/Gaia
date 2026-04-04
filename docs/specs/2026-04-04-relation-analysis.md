# M6b — Relation Analysis: 从语义聚类到关系提案包

> **Status:** Draft
> **Date:** 2026-04-04
> **依赖:** M6 Semantic Discovery（clustering 结果）

## 概述

接收 M6 输出的语义��类结果（`SemanticCluster` 列表），对每个 cluster 进行 **group-level 关系分析**，判断组内所有结论之间的关系类型，并生成对应的 Gaia Lang package 作为 relation proposal 提交。

**核心原则：** 分析以 group 为单位，不是 pairwise。一个 cluster 整体被分类为一种关系类型，然后根据类型生成对应的 IR 结构。

## 上游参考

- `propositional_logic_analysis/clustering/prompts/join_symmetric.md`：LLM prompt 的写法参考（关系定义、join 构造规则、entailment 自检）
- `docs/foundations/gaia-ir/05-canonicalization.md`：canonicalization 进入公共记录的方式
- M6 Semantic Discovery spec：clustering 输出格式

---

## 四种 Group 关系类型

对每个语义 cluster，LLM 将其整体��类为以下之一：

### 1. Partial Overlap（部分重叠）

**含义：** 组内结论讨论相关主题，有共同内容，但各自有独立主张。

**IR 结构：**
```
Conclusion_A ──subsumption──►  Join Node (抽象共同内容)
Conclusion_B ──subsumption──►  Join Node
Conclusion_C ──subsumption──►  Join Node
```

- 新建一个 **join node**（claim），内容是组内所有结论共同 entail 的最具体命题
- 每个结论到 join node 建立 subsumption（strategy: deduction，premise → conclusion）
- join node 必须满足 join_symmetric.md 的质量要求：
  - 自包含（不依赖原始结论就能理解）
  - intersection 而非 union（每个结论独立 entail join）
  - 有实质科学内容（不能是空洞泛化）
  - 不使用 meta-language（"is studied"、"focuses on" 等）

**关键检验：one-child test** — 对 join 中的每个断言，问："如果只看这一个结论，它能独立支持这个断言吗？" 如果不能，就是 union error，需要删掉。

### 2. Equivalence（等价）

**含义：** 组内结论在说同一件事（不同表述、不同粒度、不同符号，但语义等价）。

**IR 结构：**
```
Conclusion_A ──equivalence──► Common Conclusion Node
Conclusion_B ──equivalence──► Common Conclusion Node
Conclusion_C ──equivalence──► Common Conclusion Node
```

- 新建一个**公共 conclusion node**（claim），是组内结论的统一表述
- 每个原始结论和公共 conclusion 之间建立 equivalence operator
- 公共 conclusion 的内容应选择组内最清晰、最完整的表述，或由 LLM 综合

### 3. Contradiction（矛盾）

**含义：** 组内结论对同一系统在同一条件下做出不兼容的断言。

**IR 结构：**
```
Conclusion_A ──contradiction──► Conclusion_B
Conclusion_A ──contradiction──► Conclusion_C
Conclusion_B ──contradiction──► Conclusion_C

（可选，如果有共同内容）
Conclusion_A ──subsumption──► Join Node
Conclusion_B ──subsumption──► Join Node
Conclusion_C ──subsumption──► Join Node
```

- 矛盾结论之间建立 contradiction operator
- **可选加 join node**：如果矛盾组有共同前提或共同主题（例如"理论预测 X" 和 "实验否定 X" 共享 "X 被预测/��论"），则创建 join node 捕获共同内容
- join node 是否需要，由 LLM 判断

### 4. Unrelated（无关）

**含义：** 聚类误匹配，组内结论无实质逻辑关联。

**IR 结构：** 无。丢弃该 cluster，不生成任何 package。

---

## 流程

```
M6 Clustering Result
  │
  │  for each SemanticCluster:
  ▼
┌──────────────────────────┐
│  1. Load content          │  从 LanceDB 加载 cluster 内每个 gcn_id 的 content
│                          │  （通过 representative_lcn → local_variable_nodes）
├──────────────────────────┤
│  2. LLM Group Analysis   │  将整组结论发给 LLM，判断 group 关系类型
│                          │  + 生成 join/common conclusion（如需要）
│                          │  Prompt 参考 join_symmetric.md
├──────────────────────────┤
│  3. Parse LLM Output     │  ��析 XML 输出 → GroupAnalysisResult
│                          │
├──────────────────────────┤
│  4. Generate Gaia Lang   │  根据关系类型生成对应的 IR 结构
│     Package              │  （knowledge nodes + operators/strategies）
│                          │
├──────────────────────────┤
│  5. Validate & Submit    │  验证生成的 package 合法
│                          │  （IR validation + compile check）
└──────────────────────────┘
```

---

## LLM Prompt 设计

### 输入

```xml
<cluster id="cluster_xxx" node_type="claim" size="4">
  <proposition id="gcn_001">
    <content>Single-layer FeSe/STO exhibits a superconducting transition at Tc ≈ 109 K...</content>
  </proposition>
  <proposition id="gcn_002">
    <content>Interface-enhanced superconductivity in FeSe thin films on STO substrates...</content>
  </proposition>
  <proposition id="gcn_003">
    <content>The superconducting gap of FeSe/STO is nodeless with Δ ≈ 20 meV...</content>
  </proposition>
  <proposition id="gcn_004">
    <content>FeSe/STO does not exhibit bulk superconductivity above 10 K...</content>
  </proposition>
</cluster>
```

### LLM 任务

> 你是一个严谨的科学逻辑学家。给定一组科学命题（通过 embedding 相似度聚类），判断它们之间的 **group-level 关系**。
>
> **四种可能的关系（互斥）：**
>
> 1. **Partial Overlap** — 共同主题但各有独立主张 → 构造 join node
> 2. **Equivalence** — 在说同一件事 → 构造 common conclusion
> 3. **Contradiction** — 对同一系统做不兼容断言 → 标记矛盾，可选 join
> 4. **Unrelated** — 无实质关联 → 丢弃
>
> **重要：这是 group-level 判断，不是 pairwise。** 一个 group 整体归为一种类型。如果 group 内同时有 equivalent 和 contradictory 的 pair，以 contradiction 为主（contradiction 优先）。

### 输出格式

```xml
<group_analysis cluster_id="cluster_xxx" relation="partial_overlap">
  <!-- relation: "partial_overlap" | "equivalence" | "contradiction" | "unrelated" -->

  <!-- For partial_overlap: join node -->
  <join>
    <title>Short title of the join proposition</title>
    <content>Self-contained proposition capturing shared content...</content>
    <notations>
      - Symbol: definition
    </notations>
    <keywords>
      - keyword1
      - keyword2
    </keywords>
    <entailment_check>
      <child id="gcn_001" entails="true">Reason why this child entails the join</child>
      <child id="gcn_002" entails="true">Reason...</child>
    </entailment_check>
  </join>

  <!-- For equivalence: common conclusion -->
  <common_conclusion>
    <title>Unified statement</title>
    <content>The canonical form of what all propositions are saying...</content>
  </common_conclusion>

  <!-- For contradiction: pairs + optional join -->
  <contradictions>
    <pair a="gcn_001" b="gcn_004">
      <reason>gcn_001 claims Tc ≈ 109K, gcn_004 claims no bulk Tc above 10K...</reason>
    </pair>
  </contradictions>
  <join><!-- optional, same format as partial_overlap join --></join>

  <reasoning>Overall reasoning for the group classification...</reasoning>
</group_analysis>
```

---

## IR 生成规则

### Partial Overlap → Package

```python
# 1. 创建 join claim
join_claim = Claim(
    content=llm_output.join.content,
    label="join_{cluster_id}",
)

# 2. ��个原始结论 → join 的 subsumption
for gcn_id in cluster.gcn_ids:
    Strategy(
        type="deduction",
        conclusion=join_claim,
        given=[ExternalRef(gcn_id)],  # 引用已有 global variable
    )
```

### Equivalence → Package

```python
# 1. 创建 common conclusion
common = Claim(
    content=llm_output.common_conclusion.content,
    label="common_{cluster_id}",
)

# 2. 每个原始结论和 common 之间建立 equivalence
for gcn_id in cluster.gcn_ids:
    Operator(
        type="equivalence",
        operands=[ExternalRef(gcn_id), common],
    )
```

### Contradiction → Package

```python
# 1. 矛盾 pair 之间建立 contradiction
for pair in llm_output.contradictions:
    Operator(
        type="contradiction",
        operands=[ExternalRef(pair.a), ExternalRef(pair.b)],
    )

# 2. 可选 join（如果有共同内容）
if llm_output.join:
    join_claim = Claim(content=llm_output.join.content, ...)
    for gcn_id in cluster.gcn_ids:
        Strategy(type="deduction", conclusion=join_claim, given=[ExternalRef(gcn_id)])
```

---

## 配置

```python
@dataclass
class RelationAnalysisConfig:
    # LLM
    llm_model: str = "openai/chenkun/gpt-5-mini"
    llm_concurrency: int = 8
    llm_max_retries: int = 3

    # 过滤
    min_cluster_size: int = 2       # 单个 variable 的 cluster 跳过
    max_cluster_size: int = 20      # 太大的 cluster 先拆分再分析

    # 输出
    output_dir: str = "./output/relation-packages"
```

---

## 质量保障

### LLM 输出校验

1. **XML 解析检查**：输出必须是 well-formed XML
2. **relation 类型合法**：必须是四种之一
3. **join 质量检查**（for partial_overlap / contradiction with join）：
   - entailment_check 中所有 child 必须 entails="true"
   - content 不为空，长度 > 50 chars
   - 不含 meta-language（"is studied"、"focuses on" 等）
4. **equivalence 检查**：common_conclusion content 不为空
5. **contradiction 检查**：至少一对 contradiction pair

### 失败处理

- LLM 输出解析失败 → 重试（最多 3 次）
- 重试仍失败 → 标记为 `analysis_failed`，跳过
- join 质量不达标 → 降级为 unrelated（宁可丢弃也不产出低质量 proposal）

---

## ���现文件结构

```
gaia/lkm/core/
    relation_analysis.py      # run_relation_analysis() 主函数
    _llm_analyzer.py          # LLM 调用 + prompt 构造 + output 解析
    _package_generator.py     # 从 GroupAnalysisResult 生成 Gaia Lang package

gaia/lkm/models/
    relation.py               # GroupAnalysisResult, JoinNode, ContradictionPair, etc.
```

---

## 关键约束

1. **Group-level 分析，不是 pairwise** — 一个 cluster 整体归为一种关系
2. **Contradiction 优先** — 如果组内同时有 equivalent 和 contradictory 的元素，以 contradiction 为主
3. **Join node 必须是 intersection 不是 union** — 每个 child 独立 entail join
4. **生成的 package 是 proposal** — 提交到 registry，走正常 review 流程，不直接修改 global graph
5. **LLM 调用走 litellm + AI gateway** — 用 `openai/` 前缀模型名
6. **Unrelated 不产出** — 宁可丢弃也不产出无关 proposal

---

## 测试要求

### 单元测试

- `test_partial_overlap_generates_join`：partial overlap group → 生成 join node + subsumption
- `test_equivalence_generates_common`：equivalence group → 生成 common conclusion + equivalence operators
- `test_contradiction_generates_operators`：contradiction group → 生成 contradiction operators
- `test_unrelated_produces_nothing`：unrelated group → 无输出
- `test_join_quality_one_child_test`：join 不通过 one-child test → 降级为 unrelated
- `test_xml_parsing`：各种 LLM 输出格式的解析

### 集成测试

- `test_end_to_end_from_clusters`：从 fixture clustering 结果 → LLM 分析 → package 生成
- `test_generated_package_validates`：生成的 Gaia Lang package 通过 IR validation
