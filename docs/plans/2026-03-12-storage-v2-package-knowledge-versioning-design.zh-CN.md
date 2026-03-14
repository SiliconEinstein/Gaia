# Storage v2 中 Package Commit 与 Knowledge 身份设计

## 目标

澄清 storage v2 中 package revision、knowledge identity、chain snapshot 和 visibility 的建模方式。

这份文档用于替代当前实现里几种概念混在一起的状态：

- package 级版本
- knowledge 实体版本
- publish 可见性
- graph / vector 的下游索引

目标模型是：

- package revision 用 `package_name + commit_hash` 标识
- knowledge 同时有逻辑名和不可变的实体 hash
- chain 没有独立的实体版本
- 源码中的引用仍然使用逻辑名
- 存储层中的引用在某个 package commit 快照内解析为不可变实体 ID

## 当前实现方式

### 当前已有的机制

当前 `storage_v2` 是围绕 `StorageManager` 和一套 publish state machine 实现的：

1. 先把 package 写成 `preparing`
2. 再写 content
3. 再写 graph
4. 再写 vector
5. 最后把 package 标成 `merged`

最近几次修复已经把 package 行部分改成了 version-aware：

- package 按 `(package_id, version)` 存
- module 和 chain 带 `package_version`
- knowledge 额外带 `source_package_version`

### 当前的 identity 模型

当前代码实际上在使用下面这些身份定义：

- package snapshot: `(package_id, version)`
- module snapshot: `(module_id, package_version)`
- chain snapshot: `(chain_id, package_version)`
- knowledge row: `(knowledge_id, version)`，并额外带 `source_package_version`

这意味着：

- package 被当作一个版本化的发布快照
- chain 被当作 package 作用域下的快照，而不是独立版本化的实体
- knowledge 同时承担了“独立版本实体”和“package 发布快照成员”两种职责

### 当前实现为什么仍然不完整

问题不只是某几个实现 bug，而是当前模型把两种本应分开的语义塞进了同一条 `knowledge` row：

- 实体身份：这条 knowledge 本身是什么
- 发布归属：这条 knowledge 当前属于哪个 package revision

这会带来几个典型问题：

- 新 package publish 可能会覆盖旧的 committed knowledge 的可见性元数据
- package visibility 需要靠过滤 knowledge row 上的字段来推断
- 同一个逻辑 knowledge 在不同 commit 下没有独立的 binding 层
- graph / vector store 无法直接根据显式 membership 做 visibility 判断

一句话说：当前 package revision identity 和 knowledge entity identity 还没有被干净地拆开。

## 设计原则

目标设计应遵守以下原则：

1. 人写代码时始终用逻辑名引用，不直接写 hash。
2. 不可变实体用 hash 或不可变 ID 落库存储。
3. 每个 package commit 都是一个可重现快照。
4. 新 commit 永远不能改变旧 committed 快照的语义。
5. visibility 由 package commit membership 决定，而不是靠修改实体行实现。
6. graph 和 vector store 是 committed snapshot / immutable entity 的索引，不是 source of truth。

## 最终目标模型

### 1. Package Revision Identity

每一次发布的 package revision 用以下字段唯一标识：

- `package_name`
- `commit_hash`

如果需要人类友好的展示版本号，还可以额外有：

- `revision_no`

但真正的存储主身份应该是：

- `(package_name, commit_hash)`

这和实际工作流一致：

- package 的状态来自一个具体 Git commit
- 重新发布就是 ingest 一个新的 commit 快照
- 旧快照必须持续可读

### 2. Knowledge Identity

Knowledge 同时有两层 identity。

#### 逻辑 identity

给作者和语言层使用：

- `package_name + knowledge_name`

这是源码里真正写出来的引用方式。

#### 实体 identity

给存储层做不可变和去重使用：

- `knowledge_hash`

这个 hash 由规范化后的 knowledge 内容和需要参与 identity 的字段共同计算，例如：

- knowledge type
- content
- prior
- keywords
- 其他语义相关元数据

因此：

- 如果内容没有变化，继续复用同一个 `knowledge_hash`
- 如果内容发生变化，就产生一个新的 `knowledge_hash`

### 3. Knowledge 的“版本”

在这个模型下，真正的实体版本其实就是 immutable entity hash。

因此并不一定需要强制保留一个独立的数字 `knowledge_version` 字段作为存储主键，只要：

- 逻辑身份是 `package_name + knowledge_name`
- 实体身份是 `knowledge_hash`

如果后续 UI 或报告需要展示 “v1 / v2 / v3”，可以把数字版本作为派生字段保留，但不建议把它作为主 identity。

### 4. Chain Identity

Chain 没有独立的实体版本。

Chain 只存在于某个 package commit snapshot 中。

它的 identity 应该是：

- `(package_name, commit_hash, chain_name)`

这意味着：

- chain 的变化通过新的 package commit 表达
- 不需要额外引入 `chain_version`
- 每次 package revision 下的 chain snapshot 都可以被完整复现

## 必需的 Binding 层

当前实现中最缺失的一层，是逻辑名和不可变实体之间的显式 binding。

### Knowledge Binding

对每个 package commit，都存一份：

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`

这层表回答的问题是：

“在 package `P` 的 commit `C` 下，逻辑名 `K` 实际绑定到哪个 immutable knowledge entity？”

有了这层之后：

- 老 commit 可以继续保留旧 binding
- 新 commit 可以让同一个逻辑名指向新的实体 hash
- 没变化的 knowledge 自动复用旧 hash

## 最终要支持的表结构

最小可行目标 schema 应该包含如下几张表。

### 1. `package_revisions`

表示一个可发布的 package 快照。

字段：

- `package_name`
- `commit_hash`
- `parent_commit_hash`
- `revision_no`
- `status`
- `submitted_at`
- `manifest_json`

主键：

- `(package_name, commit_hash)`

状态建议：

- `preparing`
- `reviewed`
- `committed`
- `failed`

### 2. `knowledge_entities`

表示不可变的 knowledge 内容实体。

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

- 这是 canonical 的 knowledge 实体存储
- 这张表不承载 package visibility 语义

### 3. `knowledge_bindings`

把某个 package revision 下的逻辑 knowledge 名映射到 immutable knowledge entity。

字段：

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`
- `module_name`
- `is_exported`

主键：

- `(package_name, commit_hash, knowledge_name)`

建议的辅助索引：

- `(package_name, commit_hash, knowledge_hash)`

### 4. `module_snapshots`

表示某个 package revision 下的 module 元数据。

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

### 5. `chain_snapshots`

表示某个 package revision 下的 chain 状态。

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

- `steps_source_json` 保留逻辑引用，也就是 knowledge name
- `steps_resolved_json` 存解析后的 `knowledge_hash`

### 6. `probability_records`

存 review pipeline 生成的 step probability。

字段：

- `package_name`
- `commit_hash`
- `chain_name`
- `step_index`
- `value`
- `source`
- `recorded_at`

主键建议：

- append-only，无需强唯一主键

### 7. `belief_snapshots`

存 inference pipeline 生成的 belief 结果。

字段：

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`
- `belief`
- `bp_run_id`
- `computed_at`

主键建议：

- append-only，无需强唯一主键

### 8. `resources`

资源元数据表，可基本保持不变。

主键：

- `resource_id`

### 9. `resource_attachments`

当 attachment 指向 snapshot 对象时，它也应该带 package revision 语义。

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

## Graph 和 Vector 的建模方式

### Vector Store

Vector store 应该按 immutable knowledge entity 存，而不是按 package revision 存。

推荐 key：

- `knowledge_hash`

原因：

- embedding 是 knowledge 内容的派生物
- 同一个 knowledge entity 可能被多个 package revision 复用
- embedding 应该只算一次、存一份、重复使用

### Graph Store

Graph store 更适合作为 package revision snapshot 图来存。

推荐节点 identity：

- package revision node: `(package_name, commit_hash)`
- knowledge snapshot node: `(package_name, commit_hash, knowledge_name)`
- chain snapshot node: `(package_name, commit_hash, chain_name)`

同时 knowledge snapshot node 上再带：

- `knowledge_hash`

这样可以做到：

- 历史 graph 可重现
- topology query 可以明确地限定在某个 commit snapshot 内
- 同一个 immutable knowledge entity 可被多个 revision 复用

## 最终要支持的接口

API 层应显式分开三类能力：

- package snapshot 读取
- knowledge entity 读取
- logical name resolution

### Package Revision APIs

- `write_package_revision(package_revision)`
- `commit_package_revision(package_name, commit_hash)`
- `get_package_revision(package_name, commit_hash)`
- `get_latest_committed_package_revision(package_name)`
- `list_package_revisions(package_name)`

### Knowledge Entity APIs

- `write_knowledge_entities(entities)`
- `get_knowledge_entity(knowledge_hash)`
- `get_knowledge_entities(knowledge_hashes)`

### Binding APIs

- `write_knowledge_bindings(bindings)`
- `get_knowledge_binding(package_name, commit_hash, knowledge_name)`
- `list_knowledge_bindings(package_name, commit_hash)`
- `resolve_knowledge_name(package_name, commit_hash, knowledge_name)`

### Chain Snapshot APIs

- `write_chain_snapshots(chains)`
- `get_chain_snapshot(package_name, commit_hash, chain_name)`
- `list_chain_snapshots(package_name, commit_hash, module_name=None)`

### Review / Inference APIs

- `write_probability_records(records)`
- `get_probability_history(package_name, commit_hash, chain_name, step_index=None)`
- `write_belief_snapshots(snapshots)`
- `get_belief_snapshot(package_name, commit_hash, knowledge_name)`

### Manager-Level Publish APIs

Manager 层的 publish 流程不应再是“更新一个可变 package row”，而应是“创建一个新的 immutable revision snapshot”：

- `ingest_package_revision(package_revision, modules, knowledge_entities, bindings, chains, embeddings)`
- `retry_package_revision(package_name, commit_hash)`
- `mark_package_revision_failed(package_name, commit_hash, error)`

## 写入流程

### 推荐的 Commit Ingest Flow

1. 插入 `package_revisions(status='preparing')`
2. 对该 commit 下所有 knowledge 做 canonicalize
3. 为每个逻辑 knowledge 计算 `knowledge_hash`
4. upsert `knowledge_entities`
5. 写 `knowledge_bindings`
6. 编译 chain snapshot，并将 `knowledge_name -> knowledge_hash` 解析好
7. 写 `chain_snapshots`
8. 写 graph snapshot
9. 写 vector embeddings，key 用 `knowledge_hash`
10. 写 probabilities 和 beliefs
11. 将 package revision 标成 `committed`

如果失败：

- 新 revision 保持 `preparing` 或标成 `failed`
- 不删除旧的 committed revision
- 不修改历史 binding

## 读取流程

### 读取最新 Package

1. 先 resolve 最新 committed 的 `(package_name, commit_hash)`
2. 再读该 revision 的 module snapshots 和 chain snapshots
3. 通过 `knowledge_bindings` 解析出 knowledge entities

### 读取历史 Package

1. 显式传入 `(package_name, commit_hash)`
2. 只读这个 revision 对应的 snapshot rows

### 读取 Knowledge 历史

1. 按 `(package_name, knowledge_name)` 查询 `knowledge_bindings`
2. 把每个 commit 对应的 binding join 到 `knowledge_entities`

这样就能得到一个逻辑 knowledge 在不同 commit 下的完整历史。

## 当前方案与目标方案的对比

### 当前方案

- package version 只被部分建模
- chain 是 package-scoped
- knowledge 同时承担实体和 membership 两种角色
- visibility 通过过滤下游 content row 上的字段推断

### 目标方案

- package commit snapshot 是发布 identity
- knowledge hash 是 immutable entity identity
- knowledge name 是逻辑 identity
- chain 只作为 package commit snapshot 存在
- visibility 由 committed package revision 和 snapshot membership 决定

## 迁移建议

迁移建议分两阶段。

### Phase 1：先止血

如果短期内还继续沿用当前 schema，至少先做到：

- 所有 snapshot 表都完整 commit-aware
- 新 publish 不能覆盖旧 committed rows
- topology visibility 不能依赖 graph stub 自带字段推断
- knowledge 主表不要继续承担 package membership source of truth 的职责

### Phase 2：迁移到 Binding-Based Design

结构性改造建议：

1. 新增 `package_revisions`
2. 新增 `knowledge_entities`
3. 新增 `knowledge_bindings`
4. 把当前 `knowledge` 表的职责拆成：
   - entity storage
   - binding storage
5. 把 chain 存储改成显式 snapshot 表
6. 更新 graph/vector ingest 流程，让它们消费解析后的 snapshot 数据

## 已确认的设计决策

### 接受

- package identity 是 `package_name + commit_hash`
- package 展示版本号可以是派生的 `revision_no`
- knowledge 的逻辑 identity 是 `package_name + knowledge_name`
- knowledge 的 immutable identity 是 `knowledge_hash`
- chain 没有独立的实体版本
- 源码中的引用保持基于逻辑名
- 存储中的引用在 package revision 内解析成 immutable entity ID

### 拒绝

- 把 `package_name` 单独当作唯一 identity
- 把 `knowledge_name` 单独当作存储主键
- 新 commit 到来时修改旧 committed snapshot 的语义
- 让 graph/vector row 承担 visibility source of truth
- 在没有真实需求前强行为 chain 引入独立版本号

## 总结

最终设计应显式区分三件事：

- 不可变 knowledge entity
- 不可变 package commit snapshot
- 某个 snapshot 中逻辑名到 immutable entity 的 binding

只有把这三层拆开，才能同时得到：

- 可重现的历史
- 安全的重新发布
- 面向作者的逻辑名引用
- 面向存储层的 hash 去重
- 不需要独立 chain version 的 chain snapshot 模型
- 正确的 graph/vector 索引，不发生跨版本污染
