# Package Version Management 与 Storage Identity 整合方案

## 目的

这份文档用于和 PR 117 的 owner 对齐两个已经分别成形、但尚未完全统一的设计方向：

1. PR 117 的 package version management 设计
2. storage v2 的 package commit / knowledge identity / chain snapshot 设计

目标不是直接给出实现细节，而是先明确：

- 哪些部分已经一致
- 哪些部分存在根本冲突
- 最终应该采用什么统一模型
- 这个统一模型对应的表结构与接口边界是什么

## 背景

### PR 117 已明确的方向

PR 117 的版本管理文档已经明确了以下原则：

1. package 版本采用 semver，由系统根据 diff 自动推导
2. knowledge 没有独立数字版本，使用 content hash 表示变化
3. dependencies 精确 pin，不使用 range
4. major 版本允许新旧版本共存

这套设计解决的是：

- 用户如何发布
- package 对外如何表达版本
- 下游依赖如何锁定
- review / BP 如何根据版本级别路由

### storage v2 这边已经明确的方向

storage v2 这边已经澄清了几个核心点：

1. 逻辑引用不应直接写 hash，而应继续使用逻辑名
2. knowledge 的不可变实体身份应与 package publish 身份分离
3. chain 不需要独立实体版本，但必须存在于某个 package snapshot 中
4. visibility 不应靠修改 knowledge row 本身来实现，而应通过 package snapshot membership 实现

这套设计解决的是：

- 数据库内部应该如何组织 identity
- graph/vector 应该依附哪个层级
- 历史快照如何保持可重现

## 当前分歧的本质

当前并不是“一个方案对、一个方案错”，而是两个方案分别站在不同层次上定义版本：

- PR 117 主要定义的是对外的 package version 语义
- storage v2 主要定义的是内部存储和快照 identity 语义

真正需要统一的是：

**系统内部到底以 semver 为主 identity，还是以 commit hash 为主 identity。**

这决定了后面所有表结构和读取接口的形态。

## 已经可以直接整合的部分

以下内容可以视为已经达成一致，不需要再争论：

### 1. Knowledge 没有独立数字版本

这一点 PR 117 和 storage 设计是一致的。

正确表达应为：

- knowledge 的逻辑 identity 是 `package_name + knowledge_name`
- knowledge 的实体变化通过 `knowledge_hash` 表示
- 不再引入独立的 `knowledge_version` 计数器作为主 identity

### 2. Chain 没有独立实体版本

这一点也已经一致：

- chain 的变化通过 package revision 表达
- chain 不需要自己的 version counter
- chain 只在某个 package snapshot 中有意义

### 3. Dependencies 必须精确 pin

这和 snapshot 可重现性完全一致。

无论最终内部主 identity 选 semver 还是 commit hash，都应保持：

- 依赖必须能唯一解析到一个不可变 package snapshot

### 4. 历史版本必须可共存、可查询

无论是 PR 117 的 major coexistence，还是 storage 设计中的 immutable snapshot，最终都要求：

- 旧版本不能被新版本覆盖
- 历史版本必须能重放和查询

## 需要统一的关键设计决策

## 1. Package 的主 identity 到底是什么

这是最核心的问题。

目前存在两种候选方案：

### 方案 A：以 semver 为主 identity

即：

- package 唯一身份 = `package_name + semver`

优点：

- 对用户最直观
- lock file 直接保存 semver 即可
- 文档和 CLI 语义简单

缺点：

- 不容易表达“同一个 semver 对应哪个具体源码状态”
- 不利于和 Git / review pipeline / reproducibility 做强绑定
- 并发 publish、重试 publish、未发布 commit 都会比较难建模

### 方案 B：以 commit hash 为内部主 identity，semver 为外部发布标签

即：

- 内部唯一身份 = `package_name + commit_hash`
- 对外版本标签 = `semver`
- 系统保证每个 committed semver 唯一映射一个 commit hash

优点：

- 和 Git、review pipeline、build artifact、snapshot 重放天然一致
- 失败重试、并发提交、临时 preparing 状态都更容易建模
- 内部 identity 不会和用户展示版本纠缠

缺点：

- 文档层和实现层需要明确区分 “外部版本” 与 “内部主键”
- lock file 需要回答是存 semver 还是 commit hash，或者两者都存

### 建议

建议采用方案 B：

- **内部存储主 identity 使用 `(package_name, commit_hash)`**
- **外部发布语义继续使用 `package_name @ semver`**

也就是说：

- semver 是 publish label
- commit hash 是 immutable snapshot identity

两者的关系应定义为：

- 每个 committed `package_name @ semver` 唯一映射到一个 `commit_hash`
- 一个 `commit_hash` 在 committed 状态下最多对应一个 semver

## 2. Knowledge 的 identity 应如何表达

建议统一成三层：

### 逻辑 identity

- `package_name + knowledge_name`

用于作者写 DSL、module export、chain step 引用。

### 实体 identity

- `knowledge_hash`

用于去重、不可变实体存储、embedding 复用。

### 发布绑定

在某个 package snapshot 中，逻辑 knowledge 名实际绑定到哪个实体 hash，需要一层显式 binding：

- `(package_name, commit_hash, knowledge_name) -> knowledge_hash`

这是最终必须补上的结构。

## 3. Chain 的 identity 应如何表达

chain 只有发布版本，没有实体版本。

因此 chain 的 identity 应该是：

- `(package_name, commit_hash, chain_name)`

它是一个 snapshot object，不是一个独立演化的 immutable entity。

## 统一后的最终模型

## 1. Package 层

### 内部 identity

- `package_name`
- `commit_hash`

### 对外 version label

- `semver`

### 关系

- `(package_name, semver) <-> (package_name, commit_hash)` 一对一映射，仅对 committed revision 成立

## 2. Knowledge 层

### 逻辑 identity

- `package_name + knowledge_name`

### 实体 identity

- `knowledge_hash`

### 绑定关系

- `(package_name, commit_hash, knowledge_name) -> knowledge_hash`

## 3. Chain 层

### 逻辑 identity

- `package_name + chain_name`

### snapshot identity

- `(package_name, commit_hash, chain_name)`

## 最终建议的表结构

下面是整合后的推荐最小 schema。

## 1. `package_revisions`

表示 package 的内部不可变 revision。

字段：

- `package_name`
- `commit_hash`
- `semver`
- `parent_commit_hash`
- `status`
- `submitted_at`
- `manifest_json`

主键：

- `(package_name, commit_hash)`

唯一约束：

- `(package_name, semver)` 在 `committed` 状态下唯一

状态建议：

- `preparing`
- `reviewed`
- `committed`
- `failed`
- `archived`

说明：

- `archived` 可选，仅用于 active graph / archive 分层
- 不建议用它表达“逻辑上被推翻”，那仍然应由 BP 处理

## 2. `knowledge_entities`

表示不可变 knowledge 实体。

字段：

- `knowledge_hash`
- `type`
- `content`
- `prior`
- `keywords_json`
- `metadata_json`
- `created_at`

主键：

- `knowledge_hash`

说明：

- 只表达实体内容
- 不表达 package 可见性

## 3. `knowledge_bindings`

表示 package revision 中逻辑 knowledge 名到实体 hash 的绑定。

字段：

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`
- `module_name`
- `is_exported`

主键：

- `(package_name, commit_hash, knowledge_name)`

辅助索引：

- `(package_name, commit_hash, knowledge_hash)`

## 4. `module_snapshots`

字段：

- `package_name`
- `commit_hash`
- `module_name`
- `role`
- `imports_json`
- `chain_names_json`
- `export_names_json`

主键：

- `(package_name, commit_hash, module_name)`

## 5. `chain_snapshots`

字段：

- `package_name`
- `commit_hash`
- `chain_name`
- `module_name`
- `type`
- `steps_source_json`
- `steps_resolved_json`
- `chain_hash`

主键：

- `(package_name, commit_hash, chain_name)`

说明：

- `steps_source_json` 保存逻辑引用
- `steps_resolved_json` 保存解析后的 `knowledge_hash`

## 6. `probability_records`

字段：

- `package_name`
- `commit_hash`
- `chain_name`
- `step_index`
- `value`
- `source`
- `recorded_at`

说明：

- append-only

## 7. `belief_snapshots`

字段：

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`
- `belief`
- `bp_run_id`
- `computed_at`

说明：

- append-only

## 8. `resources`

字段：

- `resource_id`
- `type`
- `format`
- `storage_backend`
- `storage_path`
- `metadata_json`

主键：

- `resource_id`

## 9. `resource_attachments`

字段：

- `resource_id`
- `package_name`
- `commit_hash`
- `target_type`
- `target_name`
- `role`
- `description`

主键建议：

- `(resource_id, package_name, commit_hash, target_type, target_name, role)`

## Graph / Vector 的整合方案

## Vector Store

Vector store 应按 immutable entity 存。

推荐 key：

- `knowledge_hash`

理由：

- embedding 是 knowledge 内容的派生物
- 相同内容不应重复计算、重复存储
- package commit 只决定“是否可见”，不决定 embedding identity

## Graph Store

Graph store 更适合作为 package revision snapshot 图。

推荐节点 identity：

- package revision node: `(package_name, commit_hash)`
- knowledge snapshot node: `(package_name, commit_hash, knowledge_name)`
- chain snapshot node: `(package_name, commit_hash, chain_name)`

同时 knowledge snapshot node 上携带：

- `knowledge_hash`

这样做可以同时满足：

- snapshot 可重现
- graph 可按 commit 查询
- 相同 knowledge entity 可被多个 snapshot 复用

## 最终接口建议

## Package Revision APIs

- `write_package_revision(package_revision)`
- `commit_package_revision(package_name, commit_hash, semver)`
- `get_package_revision(package_name, commit_hash)`
- `get_package_revision_by_semver(package_name, semver)`
- `get_latest_committed_package_revision(package_name)`
- `list_package_revisions(package_name)`

## Knowledge Entity APIs

- `write_knowledge_entities(entities)`
- `get_knowledge_entity(knowledge_hash)`
- `get_knowledge_entities(knowledge_hashes)`

## Knowledge Binding APIs

- `write_knowledge_bindings(bindings)`
- `resolve_knowledge_name(package_name, commit_hash, knowledge_name)`
- `list_knowledge_bindings(package_name, commit_hash)`
- `list_knowledge_history(package_name, knowledge_name)`

## Chain Snapshot APIs

- `write_chain_snapshots(chains)`
- `get_chain_snapshot(package_name, commit_hash, chain_name)`
- `list_chain_snapshots(package_name, commit_hash, module_name=None)`

## Review / Inference APIs

- `write_probability_records(records)`
- `get_probability_history(package_name, commit_hash, chain_name, step_index=None)`
- `write_belief_snapshots(snapshots)`
- `get_belief_snapshot(package_name, commit_hash, knowledge_name)`

## Publish / Build APIs

- `ingest_package_revision(package_revision, modules, knowledge_entities, bindings, chains, embeddings)`
- `compute_manifest_hashes(package_dir)`
- `derive_semver_bump(previous_revision, current_manifest)`
- `bind_semver_to_commit(package_name, semver, commit_hash)`

## 统一后的工作流

### Build

1. 读取源码中的逻辑 knowledge / chain / module
2. 计算每个 knowledge 的 canonical hash
3. 输出 manifest：`knowledge_name -> knowledge_hash`
4. 与上一个 committed revision 比较，推导 semver bump

### Publish

1. 创建 `package_revisions(status='preparing')`
2. upsert `knowledge_entities`
3. 写入 `knowledge_bindings`
4. 写入 `module_snapshots`
5. 写入 `chain_snapshots`
6. 写 graph snapshot
7. 写 vector embeddings
8. 写 review / inference 结果
9. 绑定 semver 与 commit hash
10. 标记 package revision 为 `committed`

### Dependency Resolution

建议采用双层模型：

- 用户/lockfile 层保存 `package_name @ semver`
- build/runtime 内部解析到具体 `commit_hash`

也就是说：

- 外部 pin semver
- 内部 resolve commit hash

这样兼顾：

- 人类可读性
- 内部不可变 identity
- 重放与审计能力

## 还需要继续讨论的未定义项

以下问题在 PR 117 中仍未完全定义，需要在讨论中确认：

### 1. `semver` 与 `commit_hash` 的一一映射规则

必须明确：

- committed 后是否保证 `(package_name, semver)` 唯一映射到一个 `commit_hash`
- 同一个 commit 是否允许重新绑定不同 semver

建议答案：

- committed 状态下必须一对一

### 2. `knowledge_hash` 的计算域

需要明确哪些字段参与 hash：

- `type`
- `content`
- `prior`
- `keywords`
- 其他 metadata

如果这点不定义清楚：

- patch / minor / major 分类会不稳定
- 去重也会不稳定

### 3. Patch 的判定标准

PR 117 目前把 “prior adjustment” 放进 patch，但如果 prior 参与 knowledge_hash，则 manifest diff 也会变化。

需要明确：

- knowledge_hash 是“全文语义实体 hash”
- 还是“内容 hash”
- patch/minor/major 是根据另一个 change classifier 判断

建议：

- `knowledge_hash` 负责实体不可变性
- semver classifier 负责变更等级判定
- 两者不要强行耦合

### 4. Major coexistence 的 graph 连接语义

PR 117 说 major old/new exports 会自动建立 factor，但还没定义：

- 旧 export 与新 export 如何配对
- rename 时怎样识别同一逻辑对象
- 一个 package 多 export 时如何批量生成连接

这需要后续单独设计。

## 推荐的统一结论

建议和 PR 117 owner 讨论后，把统一方案定为：

1. **对外版本语义保留 PR 117 的 semver 体系**
2. **内部主 identity 采用 `package_name + commit_hash`**
3. **knowledge 不使用独立数字版本，只使用 `knowledge_hash`**
4. **chain 没有独立实体版本，只存在于 package revision snapshot 中**
5. **必须引入 `knowledge_bindings` 层，不能继续让 knowledge row 同时承担 entity 和 membership**
6. **lockfile 对用户暴露 semver，但系统内部必须能解析到 commit hash**

## 为什么这份整合方案更稳

这样统一之后：

- PR 117 想保留的 semver / publish / dependency 语义都还在
- storage 侧需要的 immutable snapshot / binding / reproducibility 也能成立
- graph/vector 的可见性不再依赖脆弱的字段过滤
- 历史 package revision 不会被新 publish 污染
- 同一个 knowledge 内容可以天然复用 embedding 和实体存储

## 最后一句话

推荐把整个系统拆成三层去理解：

- **对外发布层：** `package_name @ semver`
- **内部快照层：** `package_name + commit_hash`
- **实体内容层：** `knowledge_hash`

这三层一旦明确，后面的表结构、接口和 publish pipeline 就都能落稳。
