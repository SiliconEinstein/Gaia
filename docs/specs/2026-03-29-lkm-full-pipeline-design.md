# LKM 全量 Pipeline 系统设计

| 文档属性 | 值 |
|---------|---|
| 版本 | 0.1 (draft) |
| 日期 | 2026-03-29 |
| 状态 | **Proposal** |

## 1. 目标

从 10 万篇论文（XML 格式）出发，构建一个包含约 100 万命题的全局知识图谱：

```
XML 论文 → Gaia IR → 存储 → Global Canonicalization → Global BP → Curation → Research Tasks
```

## 2. Pipeline 总览

```
Stage 1: Paper Ingestion        XML → LocalCanonicalGraph + LocalParameterization (per paper)
Stage 2: Storage                Local IR → LanceDB + Neo4j + ByteHouse
Stage 3: Global Canonicalization Local → Global identity (binding / equivalence)
Stage 4: Global BP              Parameterization assembly → multi-resolution inference → BeliefState
Stage 5: Curation               Contradiction detection, expansion opportunities, quality scoring
Stage 6: Research Tasks         Generate actionable research tasks from graph analysis
```

### 规模估算

| 维度 | 估算 |
|------|------|
| 论文数 | ~100,000 |
| 每篇命题数 | ~10 (claims + settings) |
| 总命题数 | ~1,000,000 |
| 每篇 Strategy 数 | ~5-8 |
| 总 Strategy 数 | ~500,000 - 800,000 |
| 跨包匹配候选数 | O(N²) 但可通过 embedding 索引降到 O(N log N) |
| Global graph 节点数（去重后） | ~300,000 - 500,000 (估算 50%-70% 去重率) |

---

## 3. 各 Stage 详细设计

### Stage 1: Paper Ingestion（XML → Gaia IR）

**输入**：论文 XML（已结构化标注：前提、推理、结论、prior、条件概率）
**输出**：`LocalCanonicalGraph` + `LocalParameterization` (per paper)

**子步骤**：

```
XML → rule-based parser → LocalCanonicalGraph + LocalParameterization
```

XML 输入已经包含结构化标注（Knowledge 类型、推理关系、概率参数），不需要 LLM 抽取或中间表示层（YAML/JSON）。转换是**纯 rule-based** 的确定性操作：

1. **XML 解析**：从 XML 中提取已标注的 Knowledge（claims/settings/questions）和 Strategy（推理关系）
2. **IR 构建**：
   - 分配 Knowledge IDs（`lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`）
   - 分配 Strategy IDs（`lcs_`）
   - 构建 LocalCanonicalGraph
3. **参数化**：从 XML 标注中提取 prior 和 conditional probability，构建 LocalParameterization

**规模考虑**：
- Rule-based 转换速度快（CPU bound，非 IO bound），单机可处理 10 万篇
- 需要并发处理（多进程/多线程）
- 需要断点续传（记录已处理的论文）

**模块位置**：算法逻辑在 `gaia/core/`，批量编排在 `gaia/lkm/pipelines/`

```
core/
  xml_to_ir.py              # XML → LocalCanonicalGraph + LocalParameterization（核心转换逻辑）

lkm/pipelines/
  run_paper_ingest.py       # 批量编排：遍历 XML 目录，调用 core/xml_to_ir + run_ingest
```

### Stage 2: Storage（Gaia IR → 数据库）

**输入**：LocalCanonicalGraph + LocalParameterization (per paper)
**输出**：持久化到三层存储

**三层存储**：

| 存储 | 用途 | 技术 |
|------|------|------|
| **LanceDB** | 内容存储 + 向量搜索 | 知识内容、策略、参数记录、embedding 向量 |
| **Neo4j** | 拓扑查询 | Knowledge → Strategy → Knowledge 连接关系 |
| **ByteHouse** | 分析查询 | 大规模聚合查询（如"所有 belief < 0.3 的 claims"、"contradiction 最多的领域"） |

**LanceDB 表**：

| 表 | 内容 |
|---|------|
| `knowledges` | Knowledge 节点（local + global） |
| `strategies` | Strategy 节点（三种形态，local + global） |
| `operators` | Operator 节点（顶层独立的 + FormalExpr 内的） |
| `canonical_bindings` | lcn → gcn 映射 |
| `prior_records` | claim 先验（原子记录） |
| `strategy_param_records` | Strategy 条件概率（原子记录） |
| `param_sources` | 参数来源 |
| `belief_states` | 推理输出 |
| `node_embeddings` | gcn_ 节点的向量表示 |

**ByteHouse 表**（分析视图，从 LanceDB 同步）：

| 表 | 用途 |
|---|------|
| `knowledge_beliefs` | gcn_id + type + content + prior + belief + package_count（宽表，方便分析） |
| `strategy_summary` | strategy_id + type + form + premise_count + conclusion + conditional_probability |
| `contradiction_pairs` | gcn_a + gcn_b + operator_id + belief_a + belief_b + delta |
| `package_stats` | package_id + knowledge_count + strategy_count + avg_belief |

**模块位置**：`gaia/libs/storage/`（已有），新增 `bytehouse.py`

### Stage 3: Global Canonicalization

**输入**：每个包的 LocalCanonicalGraph + 当前 GlobalCanonicalGraph
**输出**：CanonicalBindings + 新 global Knowledge/Strategy/Operator

**核心逻辑**（per gaia-ir.md §4.1）：

1. **Knowledge matching**：对每个 local Knowledge，在 global graph 中找语义匹配
   - 主要方法：embedding cosine similarity（查 `node_embeddings` 表）
   - 回退：TF-IDF
   - 过滤：同 type、参数结构匹配（α-equivalence for claims with parameters）

2. **独立证据判断**：匹配到 global Knowledge 后，判断新 Strategy 是否提供独立证据
   - 前提重叠度检查（结构信号）
   - 必要时由 review 层 override

3. **Binding**：非独立证据 → bind to existing Knowledge + merge Strategy into CompositeStrategy
4. **Equivalence**：独立证据 → 创建新 global Knowledge + equivalence Operator
5. **Strategy 提升**：lcn → gcn ID 重写，drop steps
6. **参数整合**：LocalParameterization → PriorRecord + StrategyParamRecord

**规模考虑**：
- 100 万命题的 pairwise matching 是 O(N²) → 需要 **embedding 索引**（ANN search）降到 O(N log N)
- 增量处理：每个包 ingest 时只和已有 global graph 比较，不重新全量计算
- 需要 embedding 缓存：每个 global Knowledge 的 embedding 存在 `node_embeddings` 表，新 local Knowledge 的 embedding 实时计算

**模块位置**：`gaia/core/canonicalize.py`（已有，需重写）

### Stage 4: Global BP

**输入**：GlobalCanonicalGraph + PriorRecord[] + StrategyParamRecord[] + ResolutionPolicy
**输出**：BeliefState

**核心逻辑**：

1. **参数组装**：按 resolution policy 从原子记录中选值
2. **图构建**：
   - 确定 expand_set（哪些 Strategy 展开）
   - Strategy → fold 为 noisy-AND 因子，或 expand 为 sub_strategies / Operators
   - Operator → 确定性因子
3. **推理执行**：loopy BP（或其他推理算法）
4. **输出**：BeliefState（gcn_id → posterior）

**规模考虑**：
- 30-50 万节点的 loopy BP 可能不收敛或收敛很慢
- 策略：**图分区**（partition into weakly connected components，独立跑 BP）
- 策略：**增量 BP**（只重跑受影响的子图）
- 策略：**分层 BP**（先在粗粒度（全部折叠）跑，再在高 residual 区域展开细粒度）

**模块位置**：`gaia/core/global_bp.py`（已有，需重写） + `gaia/bp/adapter.py`

### Stage 5: Curation

**输入**：GlobalCanonicalGraph + BeliefState
**输出**：CurationReport（矛盾列表、展开候选、质量问题）

**子任务**：

#### 5.1 Contradiction Detection（矛盾发现）

找到图中的矛盾信号：
- **显式矛盾**：contradiction Operator 连接的两个 Knowledge，belief 都较高（不应该同时为真但 BP 无法解决）
- **隐式矛盾**：同一 claim 被不同 Strategy chain 支持为 true 和 false（belief 震荡或不收敛）
- **跨域矛盾**：equivalence Operator 连接的两个 Knowledge，belief 差异大

#### 5.2 FormalExpr Expansion（推理细化）

找到可以被细粒度展开的 Strategy：
- type=infer 或 type=noisy_and 的叶子 Strategy，可能被 reviewer/agent 分类为命名策略
- 已分类但未展开的 FormalStrategy，可以自动生成 FormalExpr
- 高 conditional_probability 但低 conclusion belief 的 Strategy → 推理链可能有缺陷，值得展开检查

#### 5.3 Deduplication（去重）

- 高相似度但未被 canonicalization 匹配到的 Knowledge pairs
- 需要人工或 LLM 确认是否等价

#### 5.4 Quality Scoring（质量评估）

- Strategy 的推理质量（steps 的逻辑连贯性）
- Knowledge 的 provenance 质量（来源论文的可信度）
- Graph 结构质量（孤岛节点、悬空引用）

**模块位置**：`gaia/core/curation.py`（新建）

```
curation/
  contradiction.py        # 矛盾发现
  expansion.py            # FormalExpr 展开候选
  dedup.py                # 去重候选
  quality.py              # 质量评估
  report.py               # 报告生成
```

### Stage 6: Research Tasks（研究任务生成）

**输入**：GlobalCanonicalGraph + BeliefState + CurationReport
**输出**：Research Task 列表

**任务类型**：

| 任务类型 | 触发条件 | 描述 |
|---------|---------|------|
| **resolve_contradiction** | 两个 claim 通过 contradiction Operator 连接，belief 都较高 | 需要更多证据决定哪个为真 |
| **verify_equivalence** | equivalence Operator 处于 candidate 状态 | 需要 review 确认两个 Knowledge 是否真的等价 |
| **expand_reasoning** | Strategy 可被分类为命名策略但尚未展开 | 需要 agent 创建 FormalExpr / CompositeStrategy |
| **strengthen_claim** | claim 的 belief 在 0.3-0.7 之间（不确定） | 需要更多证据支持或反驳 |
| **resolve_low_quality** | Strategy 的推理 steps 被标记为低质量 | 需要重新审查推理过程 |
| **explore_question** | type=question 的 Knowledge 尚无相关 claim | 开放研究方向 |

**模块位置**：`gaia/core/research_tasks.py`（新建）

---

## 4. 完整模块结构

```
gaia/
  libs/
    models/                          # Gaia IR 数据定义（PR 1）
      knowledge.py                   # Knowledge (3 types)
      strategy.py                    # Strategy / CompositeStrategy / FormalStrategy
      operator.py                    # Operator (6 types)
      formal_expr.py                 # FormalExpr
      parameterization.py            # PriorRecord, StrategyParamRecord
      belief_state.py                # BeliefState
      binding.py                     # CanonicalBinding
    storage/                         # 持久化（PR 2）
      config.py
      base.py                        # ABC
      lance.py                       # LanceDB
      neo4j.py                       # Neo4j
      bytehouse.py                   # ByteHouse（新）
      manager.py                     # StorageManager
    embedding.py
    llm.py

  core/                              # 领域算法
    local_params.py
    xml_to_ir.py                     # XML → LocalCanonicalGraph + LocalParameterization（新）
    matching.py                      # Embedding + TF-IDF
    canonicalize.py                  # Binding / Equivalence / CompositeStrategy merge
    global_bp.py                     # Multi-resolution inference
    strategy_assembly.py             # 命名策略 FormalExpr 自动组装（新）
    curation/                        # Curation 引擎（新）
      contradiction.py
      expansion.py
      dedup.py
      quality.py
      report.py
    research_tasks.py                # Research Task 生成（新）

  bp/                                # 推理算法
    __init__.py                      # Bridge
    adapter.py                       # Strategy/Operator → FactorGraph（新）
    partitioner.py                   # 图分区（新，大规模 BP）

  lkm/
    pipelines/                       # 批量入口（薄编排层，调用 core/）
      run_paper_ingest.py            # 批量 XML → IR → Storage（新，编排 core/xml_to_ir + run_ingest）
      run_ingest.py                  # Gaia IR → Storage + Canonicalize
      run_global_bp.py               # Global BP
      run_curation.py                # Curation（新）
      run_research_tasks.py          # Research Task 生成（新）
      run_full.py                    # 全流程编排
    services/                        # API 入口
      app.py
      deps.py
      routes/
        packages.py
        knowledge.py
        inference.py
        curation.py                  # Curation API（新）
        tasks.py                     # Research Tasks API（新）
        tables.py
        neo4j_stats.py
        graph.py
```

---

## 5. 执行优先级

| 优先级 | 任务 | 依赖 |
|--------|------|------|
| **P0** | Models v2 (Knowledge/Strategy/Operator) | 无 |
| **P0** | Storage v2 (表结构迁移) | Models |
| **P1** | Paper Ingestion (XML → Gaia IR, rule-based) | Models |
| **P1** | Canonicalize v2 (独立证据判断 + CompositeStrategy merge) | Models + Storage |
| **P1** | Global BP v2 (多分辨率 + adapter) | Models + Storage |
| **P2** | ByteHouse 存储后端 | Storage |
| **P2** | Curation engine | Global BP |
| **P2** | Research Task generator | Curation |
| **P3** | 图分区 / 增量 BP（大规模优化） | Global BP |

---

## 6. 关键风险

| 风险 | 影响 | 缓解 |
|------|------|------|
| XML 标注质量不一致 | 部分论文标注不完整 | 验证器检查 + 跳过不合格论文 |
| 100 万命题的 canonicalization 性能 | O(N²) matching 不可行 | Embedding ANN 索引 + 增量处理 |
| 大规模 BP 不收敛 | 无有效 belief | 图分区 + 分层 BP + 收敛监控 |
| CompositeStrategy merge 逻辑复杂 | 实现 bug | 充分测试（galileo/newton/einstein fixtures） |
| ByteHouse 同步延迟 | 分析查询数据不一致 | 异步同步 + 版本标记 |
