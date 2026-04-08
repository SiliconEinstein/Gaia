# Gaia Registry Public Premise / Bridge Index Design

> **Status:** Proposal
>
> **Date:** 2026-04-08
>
> **Companion docs:** [2026-04-08-gaia-lang-hole-fills-design.md](2026-04-08-gaia-lang-hole-fills-design.md), [2026-04-08-gaia-package-hole-bridge-design.md](2026-04-08-gaia-package-hole-bridge-design.md)
>
> **Depends on:** [2026-04-02-gaia-registry-design.md](2026-04-02-gaia-registry-design.md), [../foundations/ecosystem/04-registry-operations.md](../foundations/ecosystem/04-registry-operations.md)

## 1. Problem

在新的 package 设计里：

- `hole` 不再是作者显式 source marker
- 而是某个 release 上编译出来的 `public premise` 角色

这会直接改变 registry 要存什么、索引什么：

1. 不能只存 “exported holes”
   因为 hole 身份可能跨版本变化
2. 不能只让 bridge relation 指向 `target_hole_qid`
   因为 QID 相同并不保证 interface 状态相同
3. 不能把 package manifests 简化成 `exports / holes / bridges`
   因为 `premises` 才是 bridge 目标验证的真正 source of truth

因此，registry 需要从旧的：

- package-local hole list
- static hole -> fillers index

升级成：

- versioned public premise snapshots
- hole history
- bridge relations keyed by target interface snapshot

## 2. Design Goals

1. **GitHub-native**
   source of truth 仍然全部是 git 文件，通过 PR 维护。

2. **Release-scoped semantics**
   registry 必须保留“某个 qid 在某个 release 上扮演什么接口角色”。

3. **No second registry**
   仍然只有一个 registry repo，不拆独立 bridge registry。

4. **Static query friendliness**
   查询不能靠扫描所有 package manifests，必须有 bot 生成的静态索引。

5. **Historical correctness**
   A 的 hole 在新版本消失后，旧 bridge 仍应作为历史记录保留。

## 3. Core Idea

registry 继续保持三层：

1. **package-local manifests**
   - 注册 PR 只提交自己 package release 的 manifests

2. **derived indexes**
   - merge 后由 bot 生成

3. **query layer**
   - CLI / Web 只查静态索引，不全仓扫描

但 source manifests 现在变成：

- `exports.json`
- `premises.json`
- `holes.json`
- `bridges.json`

其中：

- `premises.json` 是 interface source of truth
- `holes.json` 只是 `premises.json` 的 `local_hole` 子集

## 4. Object Model

### 4.1 Exported Node

`exports.json` 记录作者显式导出的节点。

它回答：

- “这个 release 想公开哪些节点？”

它不回答：

- 哪些节点是 public premises
- 哪些节点是 holes

### 4.2 Public Premise Snapshot

`premises.json` 里的每一条记录，都是一个 **release-scoped premise interface snapshot**。

它回答：

- 某个 qid 在这个 release 上是不是 public premise
- 如果是，它的角色是什么
- 它的 interface identity 是什么

最小字段：

- `qid`
- `role`
  - `local_hole`
  - `foreign_dependency`
- `interface_hash`
- `required_by`
- `exported`

### 4.3 Hole History

`holes.json` 不是单独的语义来源，只是为 discovery 优化的 subset。

hole 的真正语义应通过：

- `premises.json` 中 `role == "local_hole"`

来判定。

这样同一个 qid 才能自然经历：

- `A@1.0.0`: `local_hole`
- `A@1.1.0`: no longer public premise
- `A@1.2.0`: `foreign_dependency`

### 4.4 Bridge Relation

bridge relation 是显式生态断言：

- 某个 source claim
- fills 某个 target premise snapshot

最小字段：

- `source_qid`
- `source_content_hash`
- `target_qid`
- `target_resolved_version`
- `target_interface_hash`
- `target_role`
- `declaring_package`
- `declaring_version`

它不是：

- global canonicalization
- semantic adjudication
- “这两个 claim 永远等价”的官方结论

## 5. Repository Layout

推荐目录：

```text
gaia-registry/
├── packages/
│   ├── package-a/
│   │   ├── Package.toml
│   │   ├── Versions.toml
│   │   ├── Deps.toml
│   │   └── releases/
│   │       ├── 1.0.0/
│   │       │   ├── exports.json
│   │       │   ├── premises.json
│   │       │   ├── holes.json
│   │       │   └── bridges.json
│   │       └── ...
│   └── package-b/
│       └── ...
├── index/
│   ├── premises/
│   │   ├── by-package/
│   │   └── by-qid/
│   ├── holes/
│   │   ├── by-package/
│   │   └── by-qid/
│   ├── bridges/
│   │   ├── by-target-qid/
│   │   ├── by-target-interface/
│   │   ├── by-source-qid/
│   │   └── by-declaring-package/
│   └── manifests/
│       └── stats.json
└── .github/workflows/
    ├── register.yml
    └── build-index.yml
```

## 6. Package-Local Source Manifests

### 6.1 `exports.json`

与 package layer 一致，记录该 release 的 author-declared exports。

### 6.2 `premises.json`

这是 registry 验证 bridge target 的核心文件。

示例：

```json
{
  "package": "package-a",
  "version": "1.4.0",
  "ir_hash": "sha256:...",
  "premises": [
    {
      "qid": "github:package_a::key_missing_lemma",
      "role": "local_hole",
      "content_hash": "7f6a5b...",
      "interface_hash": "sha256:...",
      "exported": false,
      "required_by": [
        "github:package_a::main_theorem"
      ]
    }
  ]
}
```

### 6.3 `holes.json`

`holes.json` 只保留 `premises.json` 中 `role == "local_hole"` 的条目。

它的主要价值是：

- 让 CLI / Web 快速发现“当前 release 上有哪些 local holes”

### 6.4 `bridges.json`

bridge relation 示例：

```json
{
  "package": "package-b",
  "version": "2.1.0",
  "ir_hash": "sha256:...",
  "bridges": [
    {
      "relation_id": "bridge_4a1f9d3c2b7e8f10",
      "relation_type": "fills",
      "source_qid": "github:package_b::b_result",
      "source_content_hash": "88aa77...",
      "target_qid": "github:package_a::key_missing_lemma",
      "target_package": "package-a",
      "target_dependency_req": ">=1.4.0,<2.0.0",
      "target_resolved_version": "1.4.0",
      "target_role": "local_hole",
      "target_interface_hash": "sha256:...",
      "strength": "exact",
      "mode": "deduction",
      "declared_by_owner_of_source": true,
      "justification": "Theorem 3 proves A's missing lemma."
    }
  ]
}
```

## 7. Validation Rules

### 7.1 `premises.json`

`register.yml` 应新增：

- premise `qid` 必须存在于 compiled IR closure 中
- `role == "local_hole"` 时，qid 必须属于当前 package
- `role == "foreign_dependency"` 时，qid 必须属于 foreign package
- `interface_hash` 必须与 registry 当前 schema version 的计算规则一致

### 7.2 `holes.json`

- 每个 hole 必须在同版本 `premises.json` 中存在
- 且其 role 必须是 `local_hole`
- 同一版本内不可重复

### 7.3 `bridges.json`

- `source_qid` 必须可解析
- 若 source 属于 declaring package，则必须在本 release 的 `exports.json` 中
- 若 source 属于 foreign package，则必须可由依赖约束解析
- `target_qid` 必须可解析到某个 package release 的 `premises.json`
- `target_resolved_version` 必须真实存在
- `target_interface_hash` 必须与该 release 上的 premise snapshot 一致
- `target_role` 当前只允许 `local_hole`
- `target_dependency_req` 必须来自 declaring package 对 target package 的依赖约束

### 7.4 PR Ownership Rule

作者 PR：

- **允许**改 `packages/<self>/**`
- **禁止**手改 `index/**`

所有 `index/**` 都由 merge 后 bot 生成。

## 8. Derived Indexes

### 8.1 `index/premises/by-package/<package>.json`

按 package 查看各 release 的 premise snapshots。

```json
{
  "package": "package-a",
  "versions": {
    "1.4.0": {
      "premises": [
        {
          "qid": "github:package_a::key_missing_lemma",
          "role": "local_hole",
          "interface_hash": "sha256:..."
        }
      ]
    }
  }
}
```

### 8.2 `index/premises/by-qid/<shard>/<encoded-qid>.json`

按 qid 查看跨版本 interface history。

```json
{
  "qid": "github:package_a::key_missing_lemma",
  "history": [
    {
      "package": "package-a",
      "version": "1.4.0",
      "role": "local_hole",
      "interface_hash": "sha256:..."
    },
    {
      "package": "package-a",
      "version": "1.5.0",
      "role": "foreign_dependency",
      "interface_hash": "sha256:..."
    }
  ]
}
```

### 8.3 `index/holes/by-qid/<shard>/<encoded-qid>.json`

只索引 hole history：

```json
{
  "qid": "github:package_a::key_missing_lemma",
  "hole_versions": [
    {
      "version": "1.4.0",
      "interface_hash": "sha256:..."
    }
  ]
}
```

### 8.4 `index/bridges/by-target-qid/<shard>/<encoded-qid>.json`

按 target qid 聚合所有 bridge declarations。

```json
{
  "target_qid": "github:package_a::key_missing_lemma",
  "bridges": [
    {
      "declaring_package": "package-b",
      "declaring_version": "2.1.0",
      "source_qid": "github:package_b::b_result",
      "target_resolved_version": "1.4.0",
      "target_interface_hash": "sha256:..."
    }
  ]
}
```

### 8.5 `index/bridges/by-target-interface/<shard>/<interface-hash>.json`

这是“当前这个具体 hole snapshot 有哪些 fillers”最稳的查询入口。

```json
{
  "target_interface_hash": "sha256:...",
  "target_qid": "github:package_a::key_missing_lemma",
  "bridges": [
    {
      "declaring_package": "package-b",
      "declaring_version": "2.1.0",
      "source_qid": "github:package_b::b_result",
      "relation_id": "bridge_4a1f9d3c2b7e8f10"
    }
  ]
}
```

## 9. Query Semantics

### 9.1 “A 这个 hole 现在谁能填？”

正确流程不是：

- 只按 `target_qid` 查 bridge

而是：

1. 先查 `premises/holes` index，定位 A 最新 release 上该 qid 是否仍是 `local_hole`
2. 若是，拿到当前 `interface_hash`
3. 再查 `index/bridges/by-target-interface/<interface_hash>.json`

这样才能避免旧 bridge 被错误地投射到新 release。

### 9.2 “历史上谁填过这个 qid？”

查：

- `index/bridges/by-target-qid/<qid>.json`

这给的是历史视角，不是 current compatibility 视角。

### 9.3 “B 的某个结果被拿去填了哪些 holes？”

查：

- `index/bridges/by-source-qid/<qid>.json`

## 10. Scenario Walkthroughs

### 10.1 Scenario A: B 直接声明 fills A 的缺口

registry 中会出现：

- `packages/package-a/releases/1.4.0/premises.json`
  - `key_missing_lemma`, role=`local_hole`
- `packages/package-b/releases/2.1.0/bridges.json`
  - 指向 `A@1.4.0` 的 interface snapshot

如果 `A@1.5.0` 把它内部证明掉：

- `index/premises/by-qid/...` 会反映 role 改变
- `index/bridges/by-target-qid/...` 仍保留历史 bridge
- `index/bridges/by-target-interface/...` 不会把 `A@1.5.0` 和旧 bridge 混起来

### 10.2 Scenario B: C 作为第三方 bridge package

C 发布 `bridge-package` 后：

- source of truth 仍然是 `packages/bridge-package/releases/.../bridges.json`
- derived indexes 会把这条关系同时挂到：
  - target qid 视图
  - target interface 视图
  - source qid 视图
  - declaring package 视图

A 和 B 本身都不需要修改。

## 11. Non-Goals

- 不做 global canonicalization
- 不在 registry 层裁决“哪个 bridge 才是真的”
- 不要求 hole 身份跨版本稳定
- 不让作者 PR 直接维护全局索引文件
