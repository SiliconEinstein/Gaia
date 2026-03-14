# Storage Layer 数据库报告

> 基于 `upload_fixtures.py` 写入 3 篇论文后的数据快照
> 日期: 2026-03-13 | 分支: feature/storage-graph-ir

---

## 一、LanceDB (ContentStore) — 13 张表

### 1. `packages` — 知识包注册表

| 字段 | 类型 | 含义 |
|------|------|------|
| `package_id` | string | 包唯一标识 |
| `name` | string | 包名称 |
| `version` | string | 语义化版本号 |
| `description` | string | 包描述 |
| `modules` | JSON | 包含的模块 ID 列表 |
| `exports` | JSON | 对外导出的 knowledge ID 列表 |
| `submitter` | string | 提交者 |
| `submitted_at` | datetime | 提交时间 |
| `status` | string | 状态: `preparing` / `submitted` / `merged` / `rejected` |

**示例** (共 3 行):
```json
{
  "package_id": "paper_10_1038332139a0_1988_natu",
  "name": "paper_10_1038332139a0_1988_natu",
  "version": "1.0.0",
  "description": "Reasoning chains extracted from paper 10.1038332139a0_1988_Natu",
  "modules": ["paper_10_1038332139a0_1988_natu.reasoning"],
  "exports": ["paper_.../discovery_of_high_tc_superconductivity_in_the_tlcabacuo_system", ...],
  "submitter": "paper_extractor",
  "submitted_at": "2026-03-12T00:00:00",
  "status": "merged"
}
```

---

### 2. `modules` — 模块（知识的逻辑分组）

| 字段 | 类型 | 含义 |
|------|------|------|
| `module_id` | string | 模块唯一标识 (`package_id.name`) |
| `package_id` | string | 所属包 |
| `package_version` | string | 所属包版本 |
| `name` | string | 模块名称 |
| `role` | string | 角色: `reasoning` / `setting` / `motivation` / `follow_up_question` / `other` |
| `imports` | JSON | 跨模块依赖引用列表 |
| `chain_ids` | JSON | 模块内的推理链 ID 列表 |
| `export_ids` | JSON | 模块导出的 knowledge ID 列表 |

**示例** (共 3 行):
```json
{
  "module_id": "paper_10_1038332139a0_1988_natu.reasoning",
  "package_id": "paper_10_1038332139a0_1988_natu",
  "package_version": "1.0.0",
  "name": "reasoning",
  "role": "reasoning",
  "imports": [],
  "chain_ids": ["...reasoning.chain_1", "...reasoning.chain_2", "...reasoning.chain_3", "...reasoning.chain_4"],
  "export_ids": ["...discovery_of_high_tc_superconductivity_in_the_tlcabacuo_system", ...]
}
```

---

### 3. `knowledge` — 知识节点（命题/设定/问题）

| 字段 | 类型 | 含义 |
|------|------|------|
| `knowledge_id` | string | 知识唯一标识 (`package_id/name`) |
| `version` | int | 版本号 |
| `type` | string | 类型: `claim` / `question` / `setting` / `action` / `contradiction` / `equivalence` |
| `kind` | string | 子类型（如 `hypothesis`），可为空 |
| `parameters` | JSON | schema 参数列表（∀-量化变量），空 `[]` 表示非 schema |
| `content` | string | 知识内容（自然语言命题） |
| `prior` | float | 先验概率 (0, 1] |
| `keywords` | JSON | 关键词列表 |
| `source_package_id` | string | 来源包 |
| `source_package_version` | string | 来源包版本 |
| `source_module_id` | string | 来源模块 |
| `created_at` | datetime | 创建时间 |
| `embedding` | string | 嵌入向量（可为空） |

**示例** (共 81 行):
```json
{
  "knowledge_id": "paper_10_1038332139a0_1988_natu/synthesis_precursors",
  "version": 1,
  "type": "setting",
  "kind": "",
  "parameters": [],
  "content": "The starting materials used for the preparation of superconducting samples in the Tl–Ca/Ba–Cu–O system are thallium(III) oxide, calcium oxide, and BaCu₃O₄...",
  "prior": 0.7,
  "keywords": [],
  "source_package_id": "paper_10_1038332139a0_1988_natu",
  "source_package_version": "1.0.0",
  "source_module_id": "paper_10_1038332139a0_1988_natu.reasoning",
  "created_at": "2026-03-12T00:00:00"
}
```

---

### 4. `chains` — 推理链

| 字段 | 类型 | 含义 |
|------|------|------|
| `chain_id` | string | 推理链唯一标识 (`package.module.chain_name`) |
| `module_id` | string | 所属模块 |
| `package_id` | string | 所属包 |
| `package_version` | string | 所属包版本 |
| `type` | string | 推理类型: `deduction` / `induction` / `abstraction` / `contradiction` / `retraction` |
| `steps` | JSON | 推理步骤数组，每步含 `premises[]` → `conclusion` |

**示例** (共 15 行):
```json
{
  "chain_id": "paper_10_1038332139a0_1988_natu.reasoning.chain_1",
  "module_id": "paper_10_1038332139a0_1988_natu.reasoning",
  "package_id": "paper_10_1038332139a0_1988_natu",
  "package_version": "1.0.0",
  "type": "deduction",
  "steps": [
    {
      "step_index": 0,
      "premises": [
        {"knowledge_id": ".../synthesis_precursors", "version": 1},
        {"knowledge_id": ".../properties_of_bacu3o4_precursor", "version": 1},
        {"knowledge_id": ".../synthesis_procedure", "version": 1}
      ],
      "reasoning": "The authors prepared Tl-Ca/Ba-Cu-O samples...",
      "conclusion": {"knowledge_id": ".../discovery_of_high_tc_...", "version": 1}
    }
  ]
}
```

---

### 5. `probabilities` — 推理步骤可靠性评分

| 字段 | 类型 | 含义 |
|------|------|------|
| `chain_id` | string | 推理链 ID |
| `step_index` | int | 步骤索引 |
| `value` | float | 可靠性概率 (0, 1] |
| `source` | string | 评分来源: `author` / `llm_review` / `lean_verify` / `code_verify` |
| `source_detail` | string | 评分详情 |
| `recorded_at` | datetime | 记录时间 |

**示例** (共 109 行):
```json
{
  "chain_id": "paper_10_1038332139a0_1988_natu.reasoning.chain_1",
  "step_index": 0,
  "value": 0.7,
  "source": "author",
  "source_detail": "",
  "recorded_at": "2026-03-12T00:00:00"
}
```

---

### 6. `belief_history` — BP 推理结果历史

| 字段 | 类型 | 含义 |
|------|------|------|
| `knowledge_id` | string | 知识节点 ID |
| `version` | int | 知识版本 |
| `belief` | float | 信念概率 [0, 1] |
| `bp_run_id` | string | BP 运行批次 ID |
| `computed_at` | datetime | 计算时间 |

**示例** (共 81 行):
```json
{
  "knowledge_id": "paper_10_1038332139a0_1988_natu/synthesis_precursors",
  "version": 1,
  "belief": 0.7,
  "bp_run_id": "mock_bp_run",
  "computed_at": "2026-03-12T00:00:00"
}
```

---

### 7. `resources` — 附件资源元数据

| 字段 | 类型 | 含义 |
|------|------|------|
| `resource_id` | string | 资源唯一标识 |
| `type` | string | 类型: `image` / `code` / `notebook` / `dataset` / `checkpoint` / `tool_output` / `other` |
| `format` | string | 文件格式 |
| `title` | string | 标题 |
| `description` | string | 描述 |
| `storage_backend` | string | 存储后端 |
| `storage_path` | string | 存储路径 |
| `size_bytes` | int | 文件大小 |
| `checksum` | string | 校验和 |
| `metadata` | JSON | 额外元数据 |
| `created_at` | datetime | 创建时间 |
| `source_package_id` | string | 来源包 |

**当前为空**（论文 fixtures 不含附件资源）

---

### 8. `resource_attachments` — 资源与实体的多对多关联

| 字段 | 类型 | 含义 |
|------|------|------|
| `resource_id` | string | 资源 ID |
| `target_type` | string | 目标类型: `knowledge` / `chain` / `chain_step` / `module` / `package` |
| `target_id` | string | 目标实体 ID |
| `role` | string | 关联角色: `evidence` / `visualization` / `implementation` / `reproduction` / `supplement` |
| `description` | string | 关联描述 |

**当前为空**

---

### 9. `factors` — Graph IR 因子节点 🆕

| 字段 | 类型 | 含义 |
|------|------|------|
| `factor_id` | string | 因子唯一标识 |
| `type` | string | 因子类型: `reasoning` / `instantiation` / `mutex_constraint` / `equiv_constraint` |
| `premises` | JSON | 前提 knowledge ID 列表 |
| `contexts` | JSON | 上下文 knowledge ID 列表 |
| `conclusion` | string | 结论 knowledge ID |
| `package_id` | string | 所属包 |
| `source_ref` | JSON | 来源引用 (`{package, version, module, knowledge_name}`) |
| `metadata` | JSON | 额外元数据 |

**当前为空**（论文 fixtures 不含 factor 数据，需由编译器生成）

---

### 10. `canonical_bindings` — 局部→全局身份映射 🆕

| 字段 | 类型 | 含义 |
|------|------|------|
| `package` | string | 包名 |
| `version` | string | 包版本 |
| `local_graph_hash` | string | 局部图哈希 |
| `local_canonical_id` | string | 局部规范化 ID |
| `decision` | string | 决策: `match_existing` / `create_new` |
| `global_canonical_id` | string | 全局规范化 ID |
| `decided_at` | datetime | 决策时间 |
| `decided_by` | string | 决策者（人/自动匹配器） |
| `reason` | string | 决策原因 |

**当前为空**（需由 canonicalization pipeline 填充）

---

### 11. `global_canonical_nodes` — 全局去重身份注册 🆕

| 字段 | 类型 | 含义 |
|------|------|------|
| `global_canonical_id` | string | 全局唯一标识 |
| `knowledge_type` | string | 知识类型 |
| `kind` | string | 子类型 |
| `representative_content` | string | 代表性内容 |
| `parameters` | JSON | schema 参数列表 |
| `member_local_nodes` | JSON | 成员局部节点引用列表 |
| `provenance` | JSON | 来源包引用列表 |
| `metadata` | JSON | 额外元数据 |

**当前为空**（需由 canonicalization pipeline 填充）

---

### 12. `global_inference_state` — 全局推理状态 🆕

| 字段 | 类型 | 含义 |
|------|------|------|
| `graph_hash` | string | 当前图结构哈希（用于检测变更） |
| `node_priors` | JSON | 节点先验概率 `{gcn_id: float}` |
| `factor_parameters` | JSON | 因子运行时参数 `{factor_id: {conditional_probability: float}}` |
| `node_beliefs` | JSON | BP 计算后的信念值 `{gcn_id: float}` |
| `updated_at` | datetime | 最后更新时间 |

**当前为空**（单行设计，由 BP 引擎写入）

---

### 13. `submission_artifacts` — 提交审计快照 🆕

| 字段 | 类型 | 含义 |
|------|------|------|
| `package_name` | string | 包名 |
| `commit_hash` | string | Git commit 哈希 |
| `source_files` | JSON | 源文件内容 `{filename: content}` |
| `raw_graph` | JSON | 编译后的原始图 |
| `local_canonical_graph` | JSON | 局部规范化后的图 |
| `canonicalization_log` | JSON | 规范化日志 |
| `submitted_at` | datetime | 提交时间 |

**当前为空**（需由 publish pipeline 填充）

---

## 二、Kuzu (GraphStore) — 图拓扑

### 节点表

| 节点表 | 主键 | 字段 | 行数 | 说明 |
|--------|------|------|------|------|
| **Knowledge** | `knowledge_vid` | `knowledge_id`, `version`, `type`, `prior`, `belief` | 81 | 知识节点，PK = `knowledge_id@version` |
| **Chain** | `chain_id` | `type` | 15 | 推理链节点 |
| **Resource** | `resource_id` | `type`, `format` | 0 | 附件资源节点 |
| **Factor** 🆕 | `factor_id` | `type`, `is_gate` | 0 | Graph IR 因子节点 |
| **GlobalCanonicalNode** 🆕 | `global_canonical_id` | `knowledge_type`, `kind`, `representative_content` | 0 | 全局规范化节点 |

**Knowledge 示例:**
```
knowledge_vid: paper_10_1038332139a0_1988_natu/synthesis_precursors@1
knowledge_id:  paper_10_1038332139a0_1988_natu/synthesis_precursors
version:       1
type:          setting
prior:         0.7
belief:        0.7
```

**Chain 示例:**
```
chain_id: paper_10_1038332139a0_1988_natu.reasoning.chain_1
type:     deduction
```

### 关系表

| 关系表 | 方向 | 属性 | 行数 | 说明 |
|--------|------|------|------|------|
| **PREMISE** | Knowledge → Chain | `step_index` | 56 | 前提→推理链（某步骤的前提） |
| **CONCLUSION** | Chain → Knowledge | `step_index`, `probability` | 109 | 推理链→结论（某步骤的结论） |
| **ATTACHED_TO** | Resource → Knowledge/Chain | `role`, `step_index` | 0 | 资源附件关联 |
| **FACTOR_PREMISE** 🆕 | Knowledge → Factor | — | 0 | 因子的前提边 |
| **FACTOR_CONTEXT** 🆕 | Knowledge → Factor | — | 0 | 因子的上下文边 |
| **FACTOR_CONCLUSION** 🆕 | Factor → Knowledge | — | 0 | 因子的结论边 |
| **CANONICAL_BINDING** 🆕 | Knowledge → GlobalCanonicalNode | `decision`, `package`, `version` | 0 | 局部→全局身份绑定 |

**PREMISE 示例:**
```
(Knowledge: .../synthesis_precursors@1)
  -[:PREMISE {step_index: 0}]->
(Chain: ...reasoning.chain_1)
```

**CONCLUSION 示例:**
```
(Chain: ...reasoning.chain_1)
  -[:CONCLUSION {step_index: 0, probability: 0.0}]->
(Knowledge: .../discovery_of_high_tc_superconductivity...@1)
```

---

## 三、数据统计总览

| 维度 | 数量 |
|------|------|
| 论文包 | 3 |
| 模块 | 3 |
| 知识节点 | 81 |
| 推理链 | 15 |
| 概率记录 | 109 |
| 信念快照 | 81 |
| 图节点 (Knowledge) | 81 |
| 图节点 (Chain) | 15 |
| 图边 (PREMISE) | 56 |
| 图边 (CONCLUSION) | 109 |
| Graph IR 新表 (factors, canonical_bindings, global_*, submission_artifacts) | 5 张表, 均为空 |

### 🆕 新增表说明

本次 Graph IR 实现新增了 5 张 LanceDB 表和 5 个 Kuzu 图实体（2 节点表 + 3 关系表），均为空表。这些表将在以下 pipeline 阶段被填充:

- **factors** / **Factor** + 边: 由 Gaia Language 编译器生成 factor graph 后写入
- **canonical_bindings** / **CANONICAL_BINDING**: 由 canonicalization pipeline 在 publish 阶段写入
- **global_canonical_nodes** / **GlobalCanonicalNode**: 由 registry 在跨包去重时写入
- **global_inference_state**: 由 BP 引擎在推理执行后写入
- **submission_artifacts**: 由 publish pipeline 写入审计快照
