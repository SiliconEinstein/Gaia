# LKM 重构开发路线图

**Status:** Active | **Created:** 2026-04-01  
**Goal:** 基于最新 spec (M1-M8) 在 `gaia/lkm/` 下重建 LKM 模块，与上游 `gaia/bp/`、`gaia/gaia_ir/` 解耦

---

## 整体架构

```
gaia/
├── bp/              # 上游：推理引擎（只读引用）
├── gaia_ir/         # 上游：Gaia IR 数据格式（只读引用，摄入输入）
└── lkm/             # 新建：LKM 服务端
    ├── __init__.py
    ├── models/      # M1: LKM 内部存储模型
    ├── storage/     # M2: 存储层（LanceDB + Graph）
    ├── pipelines/   # M3/M4: 摄入薄层（格式转换 adapter，不含算法）
    ├── core/        # M3-M7 核心算法：lowering、extract、集成、策展、全局 BP
    └── api/         # M8: FastAPI HTTP API

tests/
└── gaia/
    └── lkm/         # LKM 测试（镜像 source 结构）
        ├── models/
        ├── storage/
        ├── pipelines/
        ├── core/
        └── api/
```

### 与现有代码的关系

| 模块 | 关系 |
|------|------|
| `gaia/gaia_ir/` | LKM 的 **输入格式**，Pipeline A 的入参。只读引用，不修改 |
| `gaia/bp/` | LKM 的 **推理引擎**，M7 调用 `InferenceEngine.run()`。只读引用 |
| `libs/storage/` | **旧代码**，不复用。新 LKM 有独立的 storage 层 |
| `libs/inference/` | **旧代码**，已被 `gaia/bp/` 取代 |
| `scripts/pipeline/` | **旧管道**，可参考逻辑但不复用代码 |

### 设计原则

1. **LKM models ≠ Gaia IR models**：LKM 有自己的 Pydantic 模型，是内部存储格式
2. **Local/Global 二元性**：Global 层只有结构（无 content/steps），内容通过 representative_lcn 回查
3. **content_hash 去重**：跨包相同内容产生相同 hash（排除 package_id）
4. **Batch 写入**：所有 DB 操作必须批量，不允许逐条循环
5. **渐进式降级**：GraphStore/VectorStore 可选，LanceContentStore 是必选的
6. **Pipeline 薄层原则**：`pipelines/` 只做数据格式转换（adapter），所有算法逻辑在 `core/`

---

## Milestone 开发计划

### M1: Data Models — LKM 内部模型

**代码位置：** `gaia/lkm/models/`  
**测试位置：** `tests/gaia/lkm/models/`

**核心交付：**
- `variable.py`: LocalVariableNode, GlobalVariableNode, LocalCanonicalRef
- `factor.py`: LocalFactorNode, GlobalFactorNode
- `binding.py`: CanonicalBinding
- `parameterization.py`: PriorRecord, FactorParamRecord, ParameterizationSource
- `inference.py`: BeliefSnapshot
- `helpers.py`: Parameter, Step, compute_content_hash()

**验证闭环：**
```bash
# 单元测试验证所有模型的序列化/反序列化
pytest tests/gaia/lkm/models/ -v

# 关键测试点：
# 1. content_hash 跨包稳定性（不同 package_id 相同内容 → 相同 hash）
# 2. content_hash 参数顺序无关性
# 3. QID 格式验证（{namespace}:{package_name}::{label}）
# 4. Cromwell clamping（prior ∈ (ε, 1-ε)）
# 5. visibility 约束（private 不能有 PriorRecord）
# 6. GlobalVariableNode 无 content 字段
# 7. GlobalFactorNode 无 steps 字段
```

**前端检查方式：** N/A（纯后端模型）  
**后端 E2E 方式：** 构造 fixture 数据，验证 model_dump/model_validate 往返一致

---

### M2: Storage Layer — 存储后端

**代码位置：** `gaia/lkm/storage/`  
**测试位置：** `tests/gaia/lkm/storage/`  
**依赖：** M1

**M2 首期交付（8 张核心表 + StorageManager 骨架）：**
- `config.py`: StorageConfig (env prefix `LKM_`)
- `_serialization.py`: model ↔ row 序列化工具
- `lance_store.py`: LanceContentStore（8 张表：local/global variable/factor nodes, canonical_bindings, prior_records, factor_param_records, param_sources）
- `manager.py`: StorageManager facade（ingest_local_graph, integrate_global_graph, commit_package, find_global_by_content_hash）

**M2 延后项（在后续 milestone 按需加入）：**

| 延后项 | 加入时机 | 原因 |
|--------|---------|------|
| `belief_snapshots` 表 | M7 (Global BP) | BP 运行才写入 |
| `node_embeddings` 表 + VectorStore | M6 (Curation) | 语义去重才需要 embedding |
| GraphStore (Neo4j/Kuzu) | M6/M8 | 子图查询才需要，M5 integrate 不依赖 |
| BM25 全文搜索 | M8 (API) | API 搜索端点才需要 |
| 向量搜索 | M6 (Curation) | 语义相似度搜索 |

**验证闭环：**
```bash
# 集成测试（真实 LanceDB，用 tmp_path）
pytest tests/gaia/lkm/storage/ -v

# 关键测试点：
# 1. 8 张表创建 + schema 验证
# 2. 写入 → 读取往返一致
# 3. preparing → merged 可见性翻转
# 4. content_hash 索引 O(1) 查找
# 5. batch 写入（一次 table.add）
# 6. run_in_executor 异步包装
```

**前端检查方式：** N/A  
**后端 E2E 方式：**
```
E2E 脚本用 galileo/einstein/newton 三个包的真实内容构造 fixture：

1. 摄入 galileo 包：
   - 写入 local nodes (preparing) → commit → 变 merged
   - 写入 global nodes + bindings (all create_new)
2. 摄入 einstein 包：
   - 写入 local nodes → commit
   - 写入 global nodes + bindings (all create_new，无重叠)
3. 摄入 newton 包（有跨包依赖 galileo::vacuum_prediction）：
   - 写入 local nodes → commit
   - 写入 global nodes + bindings
   - galileo::vacuum_prediction 的 content_hash 命中 → match_existing
4. 验证：
   - 库里有 3 个包的 local nodes (all merged)
   - global_variable_nodes 去重正确（vacuum_prediction 只有 1 个 gcn）
   - canonical_bindings 双向查询正确
   - content_hash 索引查找 O(1)
```

---

### M3: Pipeline A — Gaia IR Lowering

**代码位置：**
- `gaia/lkm/core/lower.py` — lowering 算法（Knowledge→LocalVariableNode 映射、Strategy 展开、参数提取）
- `gaia/lkm/pipelines/lower.py` — 薄层 adapter（读取 LocalCanonicalGraph + review_reports，调用 core，输出标准结构）

**测试位置：** `tests/gaia/lkm/core/test_lower.py`  
**依赖：** M1（使用 M1 的模型输出，不依赖 M2）

**核心交付：**
- `core/lower.py`: 纯算法 — Knowledge/Strategy/Operator → LKM 模型的转换逻辑
- `pipelines/lower.py`: 薄层 — 接收 LocalCanonicalGraph，调用 core，返回标准输出结构
- 确定性转换（相同输入 → 相同输出）

**验证闭环：**
```bash
# 用 tests/fixtures/ 下的 Typst 包作为输入
pytest tests/gaia/lkm/pipelines/test_lower.py -v

# 关键测试点：
# 1. Knowledge → LocalVariableNode 映射正确
# 2. Strategy → LocalFactorNode 展开（包括 FormalStrategy）
# 3. Operator → LocalFactorNode
# 4. 参数提取（PriorRecord, FactorParamRecord）
# 5. 确定性：跑两次结果完全一致
# 6. 上游对象只读（不修改 gaia_ir 实例）
```

**前端检查方式：** N/A  
**后端 E2E 方式：**
```bash
# 端到端脚本：
# 1. 用 typst query 从真实包提取 LocalCanonicalGraph
# 2. 跑 lower() 得到 LKM 模型
# 3. 打印统计：变量数、因子数、参数数
# 4. 验证所有 QID 格式合法
python -m gaia.lkm.pipelines.lower --package tests/fixtures/galileo/
```

---

### M4: Pipeline B — XML 提取

**代码位置：**
- `gaia/lkm/core/extract.py` — 提取算法（XML 解析、规则匹配、启发式参数估计）
- `gaia/lkm/pipelines/extract.py` — 薄层 adapter（接收 XML bytes + metadata，调用 core，返回标准输出结构）

**测试位置：** `tests/gaia/lkm/core/test_extract.py`  
**依赖：** M1（与 M3 并行开发）

**核心交付：**
- `core/extract.py`: 纯算法 — XML 解析、claim/setting/question 提取、参数估计
- `pipelines/extract.py`: 薄层 — 接收 XML + metadata，调用 core，返回标准输出结构
- 规则匹配，无 ML 依赖

**验证闭环：**
```bash
pytest tests/gaia/lkm/pipelines/test_extract.py -v

# 关键测试点：
# 1. arXiv XML 解析（JATS/NLM）
# 2. PubMed XML 解析
# 3. 提取出的 claims/settings/questions 合理性
# 4. QID 格式：paper:{metadata_id}::{content_hash[:8]}
# 5. 启发式参数在合理范围
# 6. 确定性
```

**后端 E2E 方式：**
```bash
# 用一篇真实 arXiv XML 测试端到端：
python -m gaia.lkm.pipelines.extract \
  --xml tests/fixtures/papers/sample_arxiv.xml \
  --source arxiv --metadata-id 2301.12345
# 输出：提取的变量数、因子数、参数分布
```

---

### M5: Integrate — 本地 → 全局合并

**代码位置：** `gaia/lkm/core/integrate.py`  
**测试位置：** `tests/gaia/lkm/core/test_integrate.py`  
**依赖：** M1 + M2 + (M3 或 M4 的输出)

**核心交付：**
- `integrate.py`: 合并本地图到全局图
  - content_hash 去重（O(1) 索引查找）
  - CanonicalBinding 创建（match_existing / create_new）
  - 参数 ID 替换（QID → gcn_id, lfac_id → gfac_id）
  - 跨包引用解析

**验证闭环：**
```bash
pytest tests/gaia/lkm/core/test_integrate.py -v

# 关键测试点：
# 1. 首个包：所有节点创建为新全局节点
# 2. 第二个包（有重叠内容）：content_hash 命中 → match_existing
# 3. private 变量永不去重
# 4. CanonicalBinding 不可变
# 5. 跨包引用解析
# 6. 参数 ID 正确替换
# 7. 失败时保持 preparing 状态
```

**后端 E2E 方式：**
```bash
# 集成测试脚本：
# 1. lower() 两个有重叠 claim 的包
# 2. integrate() 包 A → 验证全局节点创建
# 3. integrate() 包 B → 验证去重命中
# 4. 查询全局图 → 验证 local_members 包含两个 local ref
python -m gaia.lkm.scripts.test_integrate_e2e
```

**这是第一个完整闭环的里程碑** — 完成后可以验证 "从 Gaia IR 包到全局知识图谱" 的端到端流程。

---

### M6: Curation Discovery — 语义去重 & 冲突检测

**代码位置：** `gaia/lkm/core/curation.py`  
**测试位置：** `tests/gaia/lkm/core/test_curation.py`  
**依赖：** M2 + M5（需要全局图数据）

**核心交付：**
- `curation.py`:
  - CanonicalizationDiscovery: embedding 相似度 → BindingProposal / EquivalenceProposal
  - ConflictDetection: BP 诊断 + 结构异常
  - StructuralAudit: 孤立节点、悬空因子、未解析引用

**验证闭环：**
```bash
pytest tests/gaia/lkm/core/test_curation.py -v

# 关键测试点：
# 1. 两个语义相似但文本不同的 claim → 发现候选
# 2. 前提重叠高 → BindingProposal
# 3. 前提独立 → EquivalenceProposal
# 4. 只处理 public 变量
# 5. StructuralAudit 检出孤立节点
```

**前端检查方式：**
- API `POST /curation/run` → 返回 CurationReport
- 前端展示发现的候选对和审计结果

**后端 E2E 方式：**
```bash
# 摄入多个包后运行 curation：
python -m gaia.lkm.scripts.run_curation
# 输出：发现的 binding 候选数、equivalence 候选数、矛盾数、审计警告
```

---

### M7: Global BP — 全局推理

**代码位置：** `gaia/lkm/core/global_bp.py`  
**测试位置：** `tests/gaia/lkm/core/test_global_bp.py`  
**依赖：** M2 + M5 + `gaia/bp/`（上游推理引擎）

**核心交付：**
- `global_bp.py`:
  - 参数解析（resolution_policy: latest / source:{id}）
  - source_class 优先级（official > heuristic > provisional）
  - 构建 BP 运行时图（LKM 模型 → gaia.bp.FactorGraph）
  - 运行 BP → BeliefSnapshot

**验证闭环：**
```bash
pytest tests/gaia/lkm/core/test_global_bp.py -v

# 关键测试点：
# 1. 参数解析：latest 取最新、official 优先于 heuristic
# 2. 完整性检查：缺少参数 → 拒绝运行
# 3. BP 结果：beliefs 只包含 public claim
# 4. 可复现性：相同 graph_hash + policy + cutoff → 相同结果
# 5. BeliefSnapshot 正确保存
```

**前端检查方式：**
- API `GET /beliefs/snapshots` → 查看推理历史
- API `GET /beliefs/variables/{id}` → 查看某变量的置信度变化

**后端 E2E 方式：**
```bash
# 完整流程：摄入 → 集成 → BP → 查看结果
python -m gaia.lkm.scripts.run_global_bp
# 输出：收敛状态、迭代次数、最大残差、top-10 高置信度 claims
```

---

### M8: HTTP API — FastAPI 服务

**代码位置：** `gaia/lkm/api/`  
**测试位置：** `tests/gaia/lkm/api/`  
**依赖：** M2 + M5（核心），M6/M7（可选 admin 端点）

**核心交付：**
- `app.py`: FastAPI 应用 + lifespan 管理
- `deps.py`: 依赖注入
- `routes/`: ingest, variables, factors, graph, beliefs, admin
- `schemas/`: 请求/响应模型

**验证闭环：**
```bash
# API 集成测试
pytest tests/gaia/lkm/api/ -v

# 关键测试点：
# 1. POST /packages/ingest → 完整摄入流程
# 2. GET /variables → BM25 搜索 + 分页
# 3. GET /variables/{id} → content 通过 representative_lcn 回查
# 4. GET /graph/subgraph → N-hop 子图
# 5. POST /bp/run → 触发 BP 并返回 snapshot
# 6. 404 / 422 / 503 错误处理
```

**前端检查方式：**
```bash
# 启动 API 服务
uvicorn gaia.lkm.api.app:create_app --factory --reload --port 8001

# 浏览器访问 Swagger
open http://localhost:8001/docs

# 测试场景：
# 1. 上传一个包 → 查看摄入结果
# 2. 搜索 "gravity" → 查看命中的 variables
# 3. 查看某个变量的详情（含 content）
# 4. 查看子图（1-hop neighbors）
# 5. 触发 BP → 查看置信度结果
```

---

## 执行策略

### 开发顺序

```
Phase 1: M1 → M2（基础，顺序执行）
         ↓
Phase 2: M3 + M5（先跑通 Gaia IR → 全局图的端到端流程）
         M4 可并行或延后
         ↓
Phase 3: M7（全局 BP，有了数据就能推理）
         M6 可并行或延后
         ↓
Phase 4: M8（API 暴露所有功能）
```

### 测试策略：E2E 优先，Unit Test 按需

**核心理念：** 看到真实数据流转 > 追求 unit test coverage

**每个 Milestone 必须有的：**
- 一个可运行的 E2E 验证脚本（`gaia/lkm/scripts/`），输入真实数据，输出可检查的结果
- 你可以直接运行脚本 → 看输出 → 判断对不对

**Unit Test 只写关键逻辑：**
- content_hash 确定性和跨包稳定性（错了下游全错）
- Cromwell clamping 边界值
- 参数 ID 替换逻辑（QID → gcn_id）
- 不写"序列化往返"之类的低价值测试

**不用 TDD 流程：**
- 先写实现 → 跑 E2E 脚本验证 → 发现问题再补针对性测试

### 每个 Milestone 的工作模式

1. **Brainstorm**：讨论最小闭环 deliverable + 验证方式
2. **Plan**：用 writing-plans skill 写 implementation plan
3. **Implement**：先写实现，边写边跑 E2E 脚本验证
4. **Verify**：E2E 脚本通过 + 关键逻辑的 unit test 通过
5. **PR**：用 finishing-a-development-branch 收尾

### 与旧代码的迁移策略

- **不迁移**：旧代码（`libs/storage/`, `libs/inference/`, `scripts/pipeline/`）保持原样
- **参考不复用**：新代码可参考旧实现的逻辑，但不 import 旧模块
- **上游只读**：`gaia/bp/` 和 `gaia/gaia_ir/` 作为上游依赖引用，不修改

---

## E2E 测试 Fixture 资源

仓库里已有丰富的 Gaia IR fixture，可直接用于 LKM E2E 测试。

### 可直接用于 LKM E2E 的

| Fixture | 位置 | 用途 |
|---------|------|------|
| **Typst v4 包** (4个) | `tests/fixtures/gaia_language_packages/{galileo,einstein,newton,dark_energy}_*_v4/` | M3 E2E: typst compile → LocalCanonicalGraph → lower() → LKM models |
| **Gaia IR inline fixtures** | `tests/gaia_ir/test_*.py` 中的 Python 构造 | M3 unit: 直接构造 Knowledge/Strategy/Operator → lower() |
| **Curation before/after** | `tests/fixtures/curation/{before,after}.json` | M5/M6 E2E: GlobalCanonicalGraph 有重复节点，测试 integrate 去重和 curation |
| **Global graph bindings** | `tests/fixtures/global_graph/global_graph.json` | M5 E2E: CanonicalBinding 样例 |

### 数据可参考但 schema 不兼容的（旧格式）

| Fixture | 位置 | 说明 |
|---------|------|------|
| **Galileo falling bodies** | `tests/fixtures/storage/gelileo_falling_bodies/` | 旧 Knowledge/Chain/Module/Package 格式，数据内容可参考 |
| **3 篇论文** | `tests/fixtures/storage/papers/` | 旧格式，含 factors.json (旧 operator 命名) |
| **Sciencepedia** (3个话题) | `tests/fixtures/storage/sciencepedia/` | 旧格式，含 embeddings |
| **Einstein elevator / Galileo tied balls** | `tests/fixtures/examples/` | manifest + nodes/edges 格式，含 expected_beliefs |

### 推荐 E2E 流程

```
Typst v4 包 (galileo_falling_bodies_v4)
  → typst compile → LocalCanonicalGraph
  → lower() (M3) → LocalVariableNode + LocalFactorNode
  → StorageManager.ingest_local_graph() (M2)
  → integrate() (M5) → GlobalVariableNode + CanonicalBinding
  → global_bp() (M7) → BeliefSnapshot
```

用同一组 fixture 数据贯穿 M1-M7，每个 milestone 验证一段。

---

## 关键决策记录

| 决策 | 原因 |
|------|------|
| 新代码放 `gaia/lkm/` 而非 `libs/` | 与旧代码解耦，对齐新架构 |
| 环境变量前缀 `LKM_` 而非 `GAIA_` | 与旧存储配置不冲突 |
| 先做 M3+M5 再做 M4 | Gaia IR 包是主要数据源，论文提取可延后 |
| M6 可延后到 M7 之后 | BP 不依赖 curation 就能跑，curation 是质量优化 |
| 测试用真实 LanceDB（tmp_path） | spec 明确要求集成测试，不用 mock |
| pipelines/ 只放薄层 adapter | 算法逻辑全部在 core/，pipeline 只做格式转换，方便测试和复用 |
| E2E 验证优先于 unit test coverage | 看到真实数据流转比追求 coverage 更有价值 |
