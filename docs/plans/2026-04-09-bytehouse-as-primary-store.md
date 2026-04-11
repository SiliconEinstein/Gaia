# ByteHouse as Primary LKM Store — Migration Plan

> **Status:** Draft
> **Date:** 2026-04-09
> **Context:** LanceDB on remote S3 cannot scale beyond a few million rows for indexed queries. Scalar index builds OOM (`ExternalSorterMerge` resource exhausted), unindexed `WHERE` queries do full table scans (12M rows = minutes per query). M6 embedding pipeline blocks on these queries.

## 决策

**架构切换：ByteHouse 成为 LKM 主存储，LanceDB 降级为冷备份。**

- StorageManager 通过 backend strategy 切换底层存储（保留接口契约，不破坏已有代码）
- `integrate()` / `ingest_local_graph()` 只写 ByteHouse
- 异步 dump 任务定期把 ByteHouse 内容导出成 LanceDB 文件（按 package 分片）
- 现有 LanceDB 数据通过一次性 backfill 拷到 ByteHouse

## 为什么

1. **LanceDB scalar index 在远程 S3 不可用** — 12M 行的 index 构建因为 sort buffer 不足直接失败
2. **未索引查询全表 scan** — `WHERE conclusion IN (...)` 5+ 分钟
3. **`to_batches()` 不是真流式** — 需要先 prefetch 整个 fragment
4. **ByteHouse 列存天然适合这些查询** — sparse index、高效压缩、`Array(String)` 原生支持 `has()`

## Schema 映射

LanceDB 9 张表 → ByteHouse 对应表（命名加 `lkm_` 前缀避免冲突）：

| LanceDB 表 | ByteHouse 表 | 关键改动 |
|-----------|-------------|---------|
| `local_variable_nodes` | `lkm_local_variables` | 增加 indexes on (id, source_package, content_hash) |
| `local_factor_nodes` | `lkm_local_factors` | premises: JSON String → `Array(String)` |
| `global_variable_nodes` | `lkm_global_variables` | 增加 (id, content_hash, visibility) indexes |
| `global_factor_nodes` | `lkm_global_factors` | premises: JSON String → `Array(String)`, conclusion 索引 |
| `canonical_bindings` | `lkm_canonical_bindings` | (local_id, global_id) 双索引 |
| `prior_records` | `lkm_prior_records` | variable_id 索引 |
| `factor_param_records` | `lkm_factor_param_records` | factor_id 索引 |
| `param_sources` | `lkm_param_sources` | source_id 主键 |
| `import_status` | `lkm_import_status` | package_id 主键 |

所有表用 `HaUniqueMergeTree` 引擎，`UNIQUE KEY` 保证幂等。

## 关键查询性能

| 查询 | LanceDB 现状 | ByteHouse 目标 |
|------|------------|---------------|
| `SELECT id FROM global_variables WHERE visibility='public'` | 全表 scan ~30s | <1s |
| `SELECT * FROM global_variables WHERE id IN (500 ids)` | 全表 scan ~60s | <1s |
| `SELECT * FROM global_factors WHERE conclusion IN (500 ids)` | 全表 scan ~5min | <1s |
| `SELECT gcn FROM global_factors WHERE has(premises, 'gcn_xxx')` | 不支持 | <100ms |
| `SELECT content FROM local_variables WHERE id IN (500 ids)` | 全表 scan | <1s |

## 实施路径

### Phase 1: 新建 ByteHouse 表 + Storage 抽象（不破坏现状）

**目标：** 让代码能向 ByteHouse 写，但默认还是写 LanceDB。

1. `gaia/lkm/storage/_bytehouse_schemas.py` — 9 张表的 DDL
2. `gaia/lkm/storage/bytehouse_lkm_store.py` — 实现 LanceContentStore 同样的接口（write_*, get_*, find_*, list_*）
3. `gaia/lkm/storage/protocol.py` — 抽出 `LkmContentStore` Protocol，LanceContentStore 和 BytehouseLkmStore 都满足
4. 单元测试 `test_bytehouse_lkm_store.py` — mock clickhouse client
5. 集成测试 `test_bytehouse_lkm_integration.py` — 真实 ByteHouse，用临时表

### Phase 2: StorageManager 支持 backend 切换

**目标：** 通过配置切换底层存储。

1. `StorageConfig.lkm_backend: str = "lance"` （新字段，默认 lance）
2. `StorageManager.initialize()` 根据 backend 实例化对应的 store
3. 所有调用方通过 `storage.content` 访问，无需修改
4. 新增配置 `LKM_BACKEND=bytehouse` 在 `.env` 切换

### Phase 3: 一次性 backfill 现有 LanceDB 数据

**目标：** 把现有 12M 行从 LanceDB 拷到 ByteHouse。

1. `scripts/migrate_lance_to_bytehouse.py` — 全量迁移脚本
   - 按 package_id 分批 scan LanceDB
   - 转换 schema（JSON string → Array）
   - 写入 ByteHouse
   - 进度日志（每 10k 行一行）
   - 断点续传（基于 package_id 已迁移的标记）
2. 预计耗时：12M 行 / 100k per minute ≈ 2 小时
3. 验证：count 对比

### Phase 4: 切换 embedding pipeline 到 ByteHouse

**目标：** embedding pipeline 完全不碰 LanceDB。

1. `pipelines/embedding.py` 改用 `LKM_BACKEND=bytehouse` 的 storage
2. role_map 用 `WHERE conclusion IN (...)` 在 ByteHouse 查（秒级）
3. content 预取用 ByteHouse `WHERE id IN (...)` 查 `lkm_local_variables`（秒级）
4. 小规模验证：500 条端到端，< 30 秒
5. 全量验证：跑 245k embedding，< 1 小时

### Phase 5: 切换 import_lance pipeline 写 ByteHouse

**目标：** 新 ingest 直接写 ByteHouse，不写 LanceDB。

1. 验证 Phase 4 工作正常后，切换 `LKM_BACKEND=bytehouse` 为默认
2. `import_lance.py` 通过 StorageManager 自动走 ByteHouse 路径，无需改动
3. 全量回归测试

### Phase 6: LanceDB 异步 dump（冷备）

**目标：** 保留 LanceDB 文件作为离线备份。

1. `scripts/dump_bytehouse_to_lance.py` — 从 ByteHouse 全量导出到 LanceDB
2. 按 package_id 分片，每个 package 一个 LanceDB fragment
3. 支持增量（只 dump 上次 dump 后变化的 package）
4. 离线运行（cron 或手动）

### Phase 7: 删除 LanceContentStore 的写路径（清理）

**目标：** 代码瘦身。

1. 标记 `LanceContentStore` 为 deprecated（保留读 API 给 dump 任务用）
2. 移除 `StorageManager` 里的 lance backend 选项
3. 移除已经不用的 lance index 构建脚本

## 不在范围内

- BP / clustering / curation 的存储改动（这些不读 LKM 表）
- LanceDB 文件格式优化
- 跨数据中心复制策略

## 风险与缓解

| 风险 | 缓解 |
|------|------|
| ByteHouse schema 不支持 LanceDB 的某些类型 | Phase 1 单元测试覆盖每种字段类型 |
| 12M 行 backfill 中途失败 | 断点续传基于 package_id |
| 双写期间数据不一致 | 不做双写，直接 backfill 后切换 |
| ByteHouse 存储成本 | 估算：12M × 1KB = 12GB，可控 |
| 接口变化破坏现有 caller | 通过 Protocol 抽象保证签名不变，pytest 全量回归 |

## 验收标准

- [ ] Phase 1: ByteHouseLkmStore 单元测试 + 集成测试通过
- [ ] Phase 2: 切换 backend=lance / bytehouse 都能跑通现有测试套件
- [ ] Phase 3: backfill 完成，count 对比一致
- [ ] Phase 4: 245k embedding 全量跑通，< 1 小时
- [ ] Phase 5: import_lance 写 ByteHouse 后，新 integrate 正常
- [ ] Phase 6: dump 脚本可运行，LanceDB 文件可读
- [ ] Phase 7: 清理完成，CI 全绿
