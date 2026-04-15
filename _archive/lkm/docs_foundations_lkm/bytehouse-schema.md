# ByteHouse LKM Schema Reference

> **Status:** Current canonical
> **Engine:** HaUniqueMergeTree (ByteHouse / ClickHouse-compatible)
> **Database:** `gaia_test` (test) / `gaia_prod` (prod)
> **Table prefix:** `lkm_`

## 概览

LKM 的 9 张 ByteHouse 表对应 LanceDB 的 9 张表，分为四层：

```
Local Layer (package 级别，保存原始内容)
├── lkm_local_variables    ← 命题内容（content 字段最大）
└── lkm_local_factors      ← 推理链接（premises 为 Array(String)）

Global Layer (去重后的全局节点)
├── lkm_global_variables   ← 全局命题（content_hash 去重）
└── lkm_global_factors     ← 全局推理链接

Binding (local → global 的映射)
└── lkm_canonical_bindings ← 每个 local node 绑定到哪个 global node

Parameterization (概率参数)
├── lkm_prior_records          ← 先验概率 P(claim=true)
├── lkm_factor_param_records   ← 条件概率 P(conclusion|premises)
└── lkm_param_sources          ← 参数来源元数据

Operational (运维)
└── lkm_import_status      ← ingest pipeline 执行记录
```

## 数据流

```
Paper XML → extract → LocalVariableNode + LocalFactorNode
                          ↓ ingest
                    lkm_local_variables / lkm_local_factors
                          ↓ canonicalize (content_hash 去重)
                    lkm_global_variables / lkm_global_factors
                          ↓ bind
                    lkm_canonical_bindings
                          ↓ parameterize (LLM 估算概率)
                    lkm_prior_records / lkm_factor_param_records
```

---

## Local Layer

### lkm_local_variables

每个 package（论文）中的每个命题（claim/setting/question/action）一行。`content` 字段存储命题原文，是整个数据集中最大的字段。

```sql
CREATE TABLE IF NOT EXISTS lkm_local_variables (
    -- 命题 ID，QID 格式：{namespace}:{package_name}::{label}
    id              String,
    -- 命题类型：claim | setting | question | action
    type            String,
    -- 可见性：public（参与全局推理）| private（仅包内可见）
    visibility      String,
    -- 命题原文（自然语言）
    content         String,
    -- content 的 SHA-256 hash，用于全局去重（不含 package_id）
    content_hash    String,
    -- 量化参数列表，JSON：[{"name": "x", "type": "int"}, ...]
    parameters      String,
    -- 来源 package ID
    source_package  String,
    -- package 版本号
    version         String,
    -- 扩展元数据，JSON dict
    metadata        String,
    -- ingest 状态：preparing（写入中）| merged（已提交，可查询）
    ingest_status   String DEFAULT 'merged',
    created_at      DateTime DEFAULT now(),

    -- 加速 content_hash 查询（canonicalize 时按 hash 查重）
    INDEX idx_content_hash content_hash TYPE bloom_filter GRANULARITY 1,
    -- 加速按 package 过滤
    INDEX idx_source_package source_package TYPE bloom_filter GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_local_variables/{shard}',
    '{replica}'
)
-- 主键：命题 ID，全局唯一
ORDER BY id
UNIQUE KEY id
SETTINGS index_granularity = 128
```

### lkm_local_factors

每个 package 中的每条推理链接（strategy/operator）一行。`premises` 使用 `Array(String)` 而非 JSON string，支持 `has(premises, 'xxx')` 原生查询。

```sql
CREATE TABLE IF NOT EXISTS lkm_local_factors (
    -- 因子 ID：lfac_{sha256[:16]}
    id              String,
    -- 因子类型：strategy（推理策略）| operator（逻辑算子）
    factor_type     String,
    -- 子类型：infer | noisy_and | contradiction | retraction 等
    subtype         String,
    -- 前提命题 ID 列表（Array 而非 JSON，支持 has() 查询）
    premises        Array(String),
    -- 结论命题 ID
    conclusion      String,
    -- 背景知识 ID 列表，JSON string（strategy only）
    background      String,
    -- 推理步骤，JSON string（strategy only）
    steps           String,
    -- 来源 package
    source_package  String,
    version         String,
    metadata        String,
    ingest_status   String DEFAULT 'merged',
    created_at      DateTime DEFAULT now(),

    INDEX idx_conclusion conclusion TYPE bloom_filter GRANULARITY 1,
    INDEX idx_source_package source_package TYPE bloom_filter GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_local_factors/{shard}',
    '{replica}'
)
ORDER BY id
UNIQUE KEY id
SETTINGS index_granularity = 128
```

---

## Global Layer

### lkm_global_variables

全局去重后的命题节点。多个 local variables 如果 content_hash 相同，会合并到同一个 global variable。不存储 content（通过 `representative_lcn` 回查 local 层获取）。

```sql
CREATE TABLE IF NOT EXISTS lkm_global_variables (
    -- 全局命题 ID：gcn_{uuid4_hex[:16]}
    id                  String,
    type                String,
    -- public 的 global variable 参与全局 BP 推理
    visibility          String,
    -- 从 representative_lcn 继承的 content_hash
    content_hash        String,
    parameters          String,
    -- 代表性 local 节点引用，JSON：{"local_id": "...", "package_id": "...", "version": "..."}
    representative_lcn  String,
    -- 所有合并进来的 local 节点列表，JSON array
    local_members       String,
    metadata            String,
    created_at          DateTime DEFAULT now(),

    INDEX idx_content_hash content_hash TYPE bloom_filter GRANULARITY 1,
    -- visibility 值域很小（public/private），用 set index
    INDEX idx_visibility visibility TYPE set(8) GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_global_variables/{shard}',
    '{replica}'
)
ORDER BY id
UNIQUE KEY id
SETTINGS index_granularity = 128
```

### lkm_global_factors

全局推理链接。premises 和 conclusion 都是 gcn_id（全局 ID），不再是 local QID。

```sql
CREATE TABLE IF NOT EXISTS lkm_global_factors (
    -- 全局因子 ID：gfac_{sha256[:16]}
    id                  String,
    factor_type         String,
    subtype             String,
    -- 前提全局命题 ID 列表（Array(String)，支持 has() 查询）
    premises            Array(String),
    -- 结论全局命题 ID
    conclusion          String,
    -- 代表性 local factor ID（用于回查 steps）
    representative_lfn  String,
    -- 来源 package（取自第一个 local factor）
    source_package      String,
    metadata            String,
    created_at          DateTime DEFAULT now(),

    INDEX idx_conclusion conclusion TYPE bloom_filter GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_global_factors/{shard}',
    '{replica}'
)
ORDER BY id
UNIQUE KEY id
SETTINGS index_granularity = 128
```

---

## Binding

### lkm_canonical_bindings

记录每个 local 节点被映射到了哪个 global 节点。一个 local_id 只绑定一个 global_id（1:1），但一个 global_id 可以被多个 local_id 绑定（N:1）。

```sql
CREATE TABLE IF NOT EXISTS lkm_canonical_bindings (
    -- local 节点 ID（variable QID 或 lfac_ ID）
    local_id      String,
    -- 绑定到的 global 节点 ID（gcn_ 或 gfac_ ID）
    global_id     String,
    -- 绑定类型：variable | factor
    binding_type  String,
    -- 来源 package
    package_id    String,
    version       String,
    -- 绑定决策：match_existing（复用已有 global）| create_new（新建 global）
    decision      String,
    -- 决策原因
    reason        String,
    created_at    String,

    INDEX idx_global_id global_id TYPE bloom_filter GRANULARITY 1,
    INDEX idx_package_id package_id TYPE bloom_filter GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_canonical_bindings/{shard}',
    '{replica}'
)
-- 每个 local_id 只有一条绑定记录
ORDER BY local_id
UNIQUE KEY local_id
SETTINGS index_granularity = 128
```

---

## Parameterization

### lkm_prior_records

每个 public claim 类型的 global variable 的先验概率 P(claim=true)。由 LLM 估算或人工标注。

```sql
CREATE TABLE IF NOT EXISTS lkm_prior_records (
    -- 复合 ID：{variable_id}::{source_id}，同一变量可有多个来源的估算
    id           String,
    -- 目标 global variable ID (gcn_)
    variable_id  String,
    -- 先验概率值，∈ (ε, 1-ε)，Cromwell 截断
    value        Float64,
    -- 参数来源 ID → lkm_param_sources.source_id
    source_id    String,
    created_at   String,

    INDEX idx_variable_id variable_id TYPE bloom_filter GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_prior_records/{shard}',
    '{replica}'
)
-- 复合 ID 保证同一变量 + 同一来源只有一条记录
ORDER BY id
UNIQUE KEY id
SETTINGS index_granularity = 128
```

### lkm_factor_param_records

Strategy 类型因子的条件概率参数 P(conclusion|premises)。用于 BP 推理的 factor potential。

```sql
CREATE TABLE IF NOT EXISTS lkm_factor_param_records (
    -- 复合 ID：{factor_id}::{source_id}
    id                         String,
    -- 目标 global factor ID (gfac_)
    factor_id                  String,
    -- 条件概率表，JSON array of floats，Cromwell 截断
    conditional_probabilities  String,
    source_id                  String,
    created_at                 String,

    INDEX idx_factor_id factor_id TYPE bloom_filter GRANULARITY 1
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_factor_param_records/{shard}',
    '{replica}'
)
ORDER BY id
UNIQUE KEY id
SETTINGS index_granularity = 128
```

### lkm_param_sources

参数化来源的元数据。记录"这批概率是谁、用什么模型、什么策略估算的"。

```sql
CREATE TABLE IF NOT EXISTS lkm_param_sources (
    -- 来源 ID（唯一）
    source_id     String,
    -- 来源等级：official（权威）| heuristic（启发式）| provisional（临时）
    source_class  String,
    -- 使用的 LLM 模型名
    model         String,
    -- 估算策略
    policy        String,
    -- 额外配置，JSON dict
    config        String,
    created_at    String
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_param_sources/{shard}',
    '{replica}'
)
ORDER BY source_id
UNIQUE KEY source_id
SETTINGS index_granularity = 128
```

---

## Operational

### lkm_import_status

Ingest pipeline 的执行记录（attempt log）。每次 ingest 尝试追加一行，无论成功或失败。用于追踪"哪些 package 已导入"和"失败原因排查"。

```sql
CREATE TABLE IF NOT EXISTS lkm_import_status (
    -- package ID
    package_id          String,
    -- 执行结果：ingested | failed:<ErrorType>
    status              String,
    -- 本次导入的节点计数
    variable_count      Int32,
    factor_count        Int32,
    prior_count         Int32,
    factor_param_count  Int32,
    -- 本次执行的起止时间（ISO 8601 string）
    started_at          String,
    completed_at        String,
    -- 失败时的错误信息
    error               String
)
ENGINE = HaUniqueMergeTree(
    '/clickhouse/2100109874/sciencepedia_new/{database}.lkm_import_status/{shard}',
    '{replica}'
)
-- 复合 key：同一个 package 的多次尝试都保留（attempt log 语义）
-- 查最新状态：ORDER BY started_at DESC LIMIT 1
-- 查成功列表：SELECT DISTINCT package_id WHERE status = 'ingested'
ORDER BY (package_id, started_at)
UNIQUE KEY (package_id, started_at)
SETTINGS index_granularity = 128
```

---

## 关键查询模式

| 场景 | SQL | 性能 |
|------|-----|------|
| 按 content_hash 查重 | `SELECT * FROM lkm_global_variables WHERE content_hash IN (...)` | bloom_filter 索引，<1s |
| 按 conclusion 查 factor | `SELECT * FROM lkm_global_factors WHERE conclusion IN (...)` | bloom_filter 索引，<1s |
| 查某 premise 参与的 factor | `SELECT * FROM lkm_global_factors WHERE has(premises, 'gcn_xxx')` | Array 原生 has()，全表 scan 但列存压缩快 |
| 批量取 local 内容 | `SELECT * FROM lkm_local_variables WHERE id IN (500 ids)` | ORDER BY id = 主键，<1s |
| 查 package 导入状态 | `SELECT * FROM lkm_import_status WHERE package_id = 'x' ORDER BY started_at DESC LIMIT 1` | ORDER BY 主键前缀，<100ms |
| 所有已导入 package | `SELECT DISTINCT package_id FROM lkm_import_status WHERE status = 'ingested'` | 全表 scan，秒级 |

## 注意事项

- **HaUniqueMergeTree 去重是异步的**：INSERT 后立即 SELECT 可能看到新旧两行并存，merge 后收敛为一行（新值覆盖旧值）
- **DROP TABLE 必须加 SYNC**：否则 ZooKeeper 副本不清理，re-CREATE 会复活旧 schema 和旧数据（详见 memory: project_bytehouse_drop_sync.md）
- **premises 是 Array(String)**：写入时传 Python list，不要传 JSON string；读出时也是 list，不需要 json.loads
