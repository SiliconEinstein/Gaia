# ByteHouse LKM 操作手册

> **Status:** Current canonical
> **前置阅读:** [bytehouse-schema.md](bytehouse-schema.md) — 表结构与字段说明

## 写入机制

ByteHouse 使用 HaUniqueMergeTree 引擎，**没有传统的 UPDATE 语句**。所有写操作都是 INSERT：

| 操作 | 实现方式 |
|------|---------|
| 新增一行 | `INSERT INTO ... VALUES (...)` |
| 更新一行 | 用**相同 UNIQUE KEY** 再次 INSERT，新行在后台 merge 时覆盖旧行 |
| 部分字段更新 | 先 SELECT 出完整行，修改目标字段，整行重新 INSERT |
| 删除 | `ALTER TABLE ... DELETE WHERE ...`（异步 mutation，较重） |

> **注意**：HaUniqueMergeTree 的 merge 是**异步**的。INSERT 后立即 SELECT 可能看到新旧两行并存，merge 完成后收敛为一行。对于需要立即一致的场景，查询时加 `FINAL` 关键字（有性能开销）。

---

## 1. Local Layer 操作

### 1.1 写入 local variable（全列）

Ingest pipeline 导入一个 package 时，每个命题写一行：

```sql
INSERT INTO lkm_local_variables (
    id, type, visibility, content, content_hash,
    parameters, source_package, version, metadata, ingest_status
) VALUES (
    -- QID 格式：{namespace}:{package_name}::{label}
    'paper:1207298268707422210::claim_1',
    'claim',
    'public',
    'The binding affinity of compound X to target Y exceeds 10nM.',
    'a3f8c2e1b4d6...',          -- SHA-256 of (type, content, parameters)
    '[]',                        -- JSON: list of Parameter objects
    'paper:1207298268707422210', -- source package ID
    '1.0.0',
    '{"doi": "10.1234/example"}', -- JSON metadata
    'preparing'                   -- 初始状态：preparing，提交后改为 merged
);
```

### 1.2 提交 ingest（状态更新：preparing → merged）

写入完成后，将该 package 的所有 preparing 行标记为 merged。**因为没有 UPDATE，用 SELECT + 重新 INSERT 实现**：

```sql
-- Step 1: 查出所有 preparing 行
SELECT * FROM lkm_local_variables
WHERE source_package = 'paper:1207298268707422210'
  AND version = '1.0.0'
  AND ingest_status = 'preparing';

-- Step 2: 将查出的每一行，修改 ingest_status 为 'merged'，重新 INSERT
-- HaUniqueMergeTree 按 UNIQUE KEY (id) 去重，新行覆盖旧行
INSERT INTO lkm_local_variables (
    id, type, visibility, content, content_hash,
    parameters, source_package, version, metadata, ingest_status
) VALUES (
    'paper:1207298268707422210::claim_1',
    'claim',
    'public',
    'The binding affinity of compound X to target Y exceeds 10nM.',
    'a3f8c2e1b4d6...',
    '[]',
    'paper:1207298268707422210',
    '1.0.0',
    '{"doi": "10.1234/example"}',
    'merged'   -- ← 改了这一个字段
);
```

> **代码路径**: `BytehouseLkmStore.commit_ingest()` 自动完成上述两步。

### 1.3 写入 local factor（premises 是 Array）

```sql
INSERT INTO lkm_local_factors (
    id, factor_type, subtype, premises, conclusion,
    background, steps, source_package, version, metadata, ingest_status
) VALUES (
    'lfac_000ce16c55eb144b',
    'strategy',
    'infer',
    -- premises 是 Array(String)，直接传数组，不是 JSON 字符串
    ['paper:1207298268707422210::P2', 'paper:1207298268707422210::P6'],
    'paper:1207298268707422210::conclusion_1',
    '',           -- background: JSON string, strategy only
    '',           -- steps: JSON string, strategy only
    'paper:1207298268707422210',
    '1.0.0',
    '',
    'merged'
);
```

### 1.4 批量写入（batch upsert）

Pipeline 批量导入时直接以 merged 状态写入，跳过 preparing 阶段：

```sql
-- 批量 INSERT，HaUniqueMergeTree 自动按 UNIQUE KEY (id) 去重
INSERT INTO lkm_local_variables (
    id, type, visibility, content, content_hash,
    parameters, source_package, version, metadata, ingest_status
) VALUES
    ('paper:pkg1::c1', 'claim', 'public', 'content 1', 'hash1', '[]', 'paper:pkg1', '1.0.0', '', 'merged'),
    ('paper:pkg1::c2', 'claim', 'public', 'content 2', 'hash2', '[]', 'paper:pkg1', '1.0.0', '', 'merged'),
    ('paper:pkg1::s1', 'setting', 'private', 'setting 1', 'hash3', '[]', 'paper:pkg1', '1.0.0', '', 'merged');
```

---

## 2. Global Layer 操作

### 2.1 写入 global variable

Canonicalize 阶段，按 content_hash 去重后创建全局节点：

```sql
INSERT INTO lkm_global_variables (
    id, type, visibility, content_hash,
    parameters, representative_lcn, local_members, metadata
) VALUES (
    'gcn_a3f8c2e1b4d60001',   -- gcn_{uuid4_hex[:16]}
    'claim',
    'public',
    'a3f8c2e1b4d6...',
    '[]',
    -- representative_lcn: JSON，指向代表性的 local 节点
    '{"local_id": "paper:1207298268707422210::claim_1", "package_id": "paper:1207298268707422210", "version": "1.0.0"}',
    -- local_members: JSON array，所有合并进来的 local 节点
    '[{"local_id": "paper:1207298268707422210::claim_1", "package_id": "paper:1207298268707422210", "version": "1.0.0"}]',
    ''
);
```

### 2.2 更新 global variable 的 members（部分字段更新）

当新 package 的某个 local variable 跟已有 global variable 的 content_hash 匹配时，需要把新 local 节点加入 local_members 列表：

```sql
-- Step 1: 查出现有行
SELECT * FROM lkm_global_variables WHERE id = 'gcn_a3f8c2e1b4d60001';

-- Step 2: 在应用层修改 local_members JSON，然后整行重新 INSERT
-- UNIQUE KEY (id) 保证覆盖旧行
INSERT INTO lkm_global_variables (
    id, type, visibility, content_hash,
    parameters, representative_lcn, local_members, metadata
) VALUES (
    'gcn_a3f8c2e1b4d60001',    -- 同一个 id
    'claim',
    'public',
    'a3f8c2e1b4d6...',
    '[]',
    '{"local_id": "paper:1207298268707422210::claim_1", "package_id": "paper:1207298268707422210", "version": "1.0.0"}',
    -- ← 这里更新了，多了一个 member
    '[{"local_id": "paper:1207298268707422210::claim_1", "package_id": "paper:1207298268707422210", "version": "1.0.0"}, {"local_id": "paper:9999::claim_1", "package_id": "paper:9999", "version": "1.0.0"}]',
    ''
);
```

> **代码路径**: `BytehouseLkmStore.update_global_variable_members(gcn_id, updated_node)`

### 2.3 写入 global factor

```sql
INSERT INTO lkm_global_factors (
    id, factor_type, subtype, premises, conclusion,
    representative_lfn, source_package, metadata
) VALUES (
    'gfac_b7e2d1c3a4f50001',
    'strategy',
    'infer',
    -- premises: Array(String)，全局 gcn_id 列表
    ['gcn_a3f8c2e1b4d60001', 'gcn_c5d7e9f2a1b30002'],
    'gcn_f1a2b3c4d5e60003',
    'lfac_000ce16c55eb144b',    -- 代表性 local factor
    'paper:1207298268707422210',
    ''
);
```

---

## 3. Binding 操作

### 3.1 写入 canonical binding

记录 local → global 的映射关系：

```sql
INSERT INTO lkm_canonical_bindings (
    local_id, global_id, binding_type,
    package_id, version, decision, reason, created_at
) VALUES (
    'paper:1207298268707422210::claim_1',  -- local QID
    'gcn_a3f8c2e1b4d60001',               -- global ID
    'variable',                             -- variable | factor
    'paper:1207298268707422210',
    '1.0.0',
    'create_new',                           -- create_new | match_existing
    'No existing global variable with matching content_hash',
    '2026-04-11T10:30:00+00:00'
);
```

### 3.2 绑定已有 global（match_existing）

当 content_hash 匹配到已有 global variable 时：

```sql
INSERT INTO lkm_canonical_bindings (
    local_id, global_id, binding_type,
    package_id, version, decision, reason, created_at
) VALUES (
    'paper:9999::claim_1',
    'gcn_a3f8c2e1b4d60001',   -- 复用已有的 global
    'variable',
    'paper:9999',
    '1.0.0',
    'match_existing',           -- ← 关键：匹配已有
    'content_hash a3f8c2e1b4d6... matches existing gcn',
    '2026-04-11T10:35:00+00:00'
);
```

---

## 4. Parameterization 操作

### 4.1 写入先验概率

LLM 估算每个 public claim 的先验概率 P(true)：

```sql
INSERT INTO lkm_prior_records (
    id, variable_id, value, source_id, created_at
) VALUES (
    -- 复合 ID: {variable_id}::{source_id}
    'gcn_a3f8c2e1b4d60001::src_gpt5_20260411',
    'gcn_a3f8c2e1b4d60001',
    0.75,                                       -- P(claim=true), Cromwell-clamped ∈ (ε, 1-ε)
    'src_gpt5_20260411',                        -- → lkm_param_sources.source_id
    '2026-04-11T10:40:00+00:00'
);
```

### 4.2 更新先验概率（用新模型重新估算）

同一个 variable 用不同 source 估算时，每个 source 各一行（`id = {variable_id}::{source_id}`）。用**同一个 source 重新估算**时，INSERT 相同 id 覆盖旧值：

```sql
-- 同一个 source 重跑，UNIQUE KEY (id) 保证覆盖
INSERT INTO lkm_prior_records (
    id, variable_id, value, source_id, created_at
) VALUES (
    'gcn_a3f8c2e1b4d60001::src_gpt5_20260411',   -- 同一个复合 ID
    'gcn_a3f8c2e1b4d60001',
    0.82,                                          -- ← 更新后的概率
    'src_gpt5_20260411',
    '2026-04-12T08:00:00+00:00'                    -- ← 更新的时间
);
```

### 4.3 写入条件概率

```sql
INSERT INTO lkm_factor_param_records (
    id, factor_id, conditional_probabilities, source_id, created_at
) VALUES (
    'gfac_b7e2d1c3a4f50001::src_gpt5_20260411',
    'gfac_b7e2d1c3a4f50001',
    -- JSON array: [P(conclusion=T|all premises=T), P(conclusion=T|any premise=F)]
    '[0.95, 0.1]',
    'src_gpt5_20260411',
    '2026-04-11T10:45:00+00:00'
);
```

### 4.4 注册参数来源

```sql
INSERT INTO lkm_param_sources (
    source_id, source_class, model, policy, config, created_at
) VALUES (
    'src_gpt5_20260411',
    'heuristic',                    -- official | heuristic | provisional
    'openai/chenkun/gpt-5-mini',   -- LLM 模型名
    'default',                      -- 估算策略
    '{"temperature": 0.3}',         -- JSON 配置
    '2026-04-11T10:30:00+00:00'
);
```

---

## 5. Import Status 操作

### 5.1 记录成功的 ingest

```sql
INSERT INTO lkm_import_status (
    package_id, status, variable_count, factor_count,
    prior_count, factor_param_count, started_at, completed_at, error
) VALUES (
    'paper:1207298268707422210',
    'ingested',
    35,      -- 本次导入的 variable 数量
    11,      -- 本次导入的 factor 数量
    35,      -- 本次生成的 prior 数量
    8,       -- 本次生成的 factor_param 数量
    '2026-04-11T10:30:00+00:00',
    '2026-04-11T10:31:23+00:00',
    ''       -- 无错误
);
```

### 5.2 记录失败的 ingest

```sql
INSERT INTO lkm_import_status (
    package_id, status, variable_count, factor_count,
    prior_count, factor_param_count, started_at, completed_at, error
) VALUES (
    'paper:1207298268707422210',
    'failed:ValueError',
    0, 0, 0, 0,
    '2026-04-11T11:00:00+00:00',  -- ← 不同的 started_at
    '2026-04-11T11:00:15+00:00',
    'ValueError: Invalid XML structure in paper source'
);
```

> **UNIQUE KEY 是 `(package_id, started_at)`**，所以同一个 package 的每次尝试（不同 started_at）都会保留。这是 attempt log 语义，不是 upsert 语义。

### 5.3 查询 package 的最新状态

```sql
SELECT *
FROM lkm_import_status
WHERE package_id = 'paper:1207298268707422210'
ORDER BY started_at DESC
LIMIT 1;
```

### 5.4 查询所有已成功导入的 package

```sql
SELECT DISTINCT package_id
FROM lkm_import_status
WHERE status = 'ingested';
```

### 5.5 查询失败次数最多的 package（排查）

```sql
SELECT package_id, count() AS fail_count, max(error) AS last_error
FROM lkm_import_status
WHERE status != 'ingested'
GROUP BY package_id
ORDER BY fail_count DESC
LIMIT 20;
```

---

## 6. 常用查询

### 6.1 按 content_hash 批量查重（canonicalize 阶段核心查询）

```sql
SELECT id, content_hash, type, visibility
FROM lkm_global_variables
WHERE content_hash IN (
    'a3f8c2e1b4d6...', 'b5c7d9e1f2a3...', 'c8d0e2f4a6b8...'
);
```

### 6.2 查某个 conclusion 的所有 factor（BP 推理入口）

```sql
SELECT id, premises, conclusion, factor_type, subtype
FROM lkm_global_factors
WHERE conclusion = 'gcn_f1a2b3c4d5e60003';
```

### 6.3 查某个 premise 参与的所有 factor（反向查询，用 Array has()）

```sql
SELECT id, premises, conclusion, factor_type
FROM lkm_global_factors
WHERE has(premises, 'gcn_a3f8c2e1b4d60001');
```

### 6.4 批量获取 local variable 的内容（embedding pipeline 用）

```sql
SELECT id, content, type, source_package
FROM lkm_local_variables
WHERE id IN ('paper:pkg1::c1', 'paper:pkg1::c2', 'paper:pkg2::c1')
  AND ingest_status = 'merged';
```

### 6.5 获取某个 global variable 的完整信息链

```sql
-- 1. global variable 本身
SELECT * FROM lkm_global_variables WHERE id = 'gcn_a3f8c2e1b4d60001';

-- 2. 它的 binding（哪些 local 节点绑到了它）
SELECT * FROM lkm_canonical_bindings WHERE global_id = 'gcn_a3f8c2e1b4d60001';

-- 3. 它的先验概率
SELECT * FROM lkm_prior_records WHERE variable_id = 'gcn_a3f8c2e1b4d60001';

-- 4. 它参与的推理链接（作为 conclusion 或 premise）
SELECT * FROM lkm_global_factors WHERE conclusion = 'gcn_a3f8c2e1b4d60001';
SELECT * FROM lkm_global_factors WHERE has(premises, 'gcn_a3f8c2e1b4d60001');
```

### 6.6 统计各表行数

```sql
SELECT 'local_variables' AS tbl, count() AS n FROM lkm_local_variables
UNION ALL SELECT 'local_factors', count() FROM lkm_local_factors
UNION ALL SELECT 'global_variables', count() FROM lkm_global_variables
UNION ALL SELECT 'global_factors', count() FROM lkm_global_factors
UNION ALL SELECT 'canonical_bindings', count() FROM lkm_canonical_bindings
UNION ALL SELECT 'prior_records', count() FROM lkm_prior_records
UNION ALL SELECT 'factor_param_records', count() FROM lkm_factor_param_records
UNION ALL SELECT 'param_sources', count() FROM lkm_param_sources
UNION ALL SELECT 'import_status', count() FROM lkm_import_status;
```

---

## 7. 注意事项

### UNIQUE KEY 覆盖行为

```sql
-- 第一次 INSERT
INSERT INTO lkm_prior_records VALUES ('gcn_x::src1', 'gcn_x', 0.5, 'src1', '2026-04-11');

-- 第二次 INSERT，相同 UNIQUE KEY (id='gcn_x::src1')
-- merge 后旧行被新行覆盖
INSERT INTO lkm_prior_records VALUES ('gcn_x::src1', 'gcn_x', 0.82, 'src1', '2026-04-12');

-- 查询结果：value = 0.82（新值）
-- 但在 merge 完成前，可能短暂看到两行
SELECT * FROM lkm_prior_records WHERE id = 'gcn_x::src1';

-- 如果需要立即一致（有性能开销）：
SELECT * FROM lkm_prior_records FINAL WHERE id = 'gcn_x::src1';
```

### Array(String) 字段写入

```sql
-- ✅ 正确：直接传数组
INSERT INTO lkm_local_factors (..., premises, ...) VALUES (..., ['a', 'b', 'c'], ...);

-- ❌ 错误：传 JSON 字符串
INSERT INTO lkm_local_factors (..., premises, ...) VALUES (..., '["a", "b", "c"]', ...);

-- 查询 Array：用 has()
SELECT * FROM lkm_global_factors WHERE has(premises, 'gcn_xxx');

-- 查询 Array 长度
SELECT id, length(premises) AS premise_count FROM lkm_global_factors;
```

### DROP TABLE 必须加 SYNC

```sql
-- ✅ 正确：SYNC 确保 ZooKeeper 副本清理完毕
DROP TABLE IF EXISTS lkm_local_variables SYNC;

-- ❌ 危险：不加 SYNC，ZK 副本残留，后续 CREATE TABLE 会复活旧 schema + 旧数据
DROP TABLE IF EXISTS lkm_local_variables;
```

详见 [bytehouse-schema.md](bytehouse-schema.md) 注意事项章节。
