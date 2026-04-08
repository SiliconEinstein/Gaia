# Gaia Registry Hole / Bridge Index Design

> **Status:** Proposal
>
> **Date:** 2026-04-08
>
> **Companion docs:** [2026-04-08-gaia-lang-hole-fills-design.md](2026-04-08-gaia-lang-hole-fills-design.md), [2026-04-08-gaia-package-hole-bridge-design.md](2026-04-08-gaia-package-hole-bridge-design.md)
>
> **Depends on:** [2026-04-02-gaia-registry-design.md](2026-04-02-gaia-registry-design.md), [../foundations/ecosystem/04-registry-operations.md](../foundations/ecosystem/04-registry-operations.md)

## 1. Problem

Gaia 的 Official Registry 在当前设计里是一个 GitHub repo，主要记录：

- package identity
- version -> git tag / git sha / ir_hash
- explicit dependencies

这足够支持“已知包名 -> 拉元数据 -> 安装 / 引用”，但不够支持下面这些生态问题：

1. A 包公开了一个可复用的缺口，未来谁能补它？
2. B 包已经知道自己的结论可以填 A 的 hole，如何让别人发现？
3. C 后来发现 “B.result fills A.hole”，如何在不改 A/B 的情况下公开这个关系？
4. 当 package 很多时，如何避免每次查询都扫描整个 registry repo？

本设计不引入 global canonicalization，也不要求运行时数据库。前提保持不变：

- Registry 仍然只是一个 GitHub repo
- package 仍然是 authoring / publishing 的基本单位
- bridge relation 只是显式关系，不是 identity merge 或裁决

## 2. Design Goals

### 2.1 必须满足

1. **GitHub-native**
   一切 source of truth 都是 git 文件，所有变更都通过 PR。

2. **Package-owned authoring**
   作者只需要在 package 或 bridge package 中声明关系，不直接手改全局索引。

3. **Static-query friendly**
   查询 `hole -> fillers`、`claim -> filled holes` 时，客户端不能靠全仓扫描。

4. **No central semantic adjudication**
   Registry 记录谁声明了什么关系，但不在注册阶段裁决“这是否真的是同一个命题”。

5. **Conflict-resistant**
   注册很多 package 后，PR 不能频繁碰撞到同一个全局文件。

### 2.2 明确不做

- 不做 duplicate merge / equivalence merge
- 不做 single official bridge truth
- 不要求桥接关系必须由 source package 作者本人声明
- 不把 fuzzy discovery 变成注册时的硬 gate

## 3. Core Idea

核心分层是：

1. **package 内声明**
   `hole` 和 `bridge relation` 写在 package 里。

2. **registry 内保存 package-local manifests**
   注册时把该版本的 `exports / holes / bridges` 作为静态 manifest 记录下来。

3. **bot 生成 derived indexes**
   merge 后由 GitHub Action 生成全局静态索引文件，供 CLI / 网站 / 人类查询。

一句话：

**package 是写关系的地方，registry 是找关系的地方。**

## 4. Object Model

### 4.1 Exported Hole

`hole` 是作者显式导出的公共缺口，不是自动从所有叶子前提推导出来的。

一个 node 只有同时满足下面条件，才应被导出为 `hole`：

1. 它是某条公开结论链的 load-bearing premise
2. 当前 package 没有在本包内部把它证明完
3. 作者希望未来其他 package 能显式填补它
4. 它的语义足够稳定，值得成为公共接口

因此：

- 不是所有 leaf premise 都是 hole
- hole 是 package API 的一部分
- hole 可以被别的 package import / fill

### 4.2 Bridge Relation

`bridge relation` 是一个显式生态断言：

- 某个 `source claim`
- 可以填补某个 `target hole`
- 这个主张由某个 `declaring package` 给出

它不是新的逻辑 primitive，也不是 global identity claim。它只是一个 package-level relation record。

最小字段：

- `relation_type = "fills"`
- `source_qid`
- `target_hole_qid`
- `declaring_package`
- `declaring_version`
- `strength`
- `justification`

### 4.3 Declaring Package

`bridge relation` 可以来自两类 package：

1. **paper package**
   B 自己知道 `B.result fills A.hole`，于是直接在 B 内声明

2. **bridge package**
   后来 C 发现 `B.result fills A.hole`，由 C 发布一个小 package 专门声明该关系

Registry 不区分“哪类更真”，只记录声明来源。

## 5. Repository Layout

在当前 registry 目录结构基础上，新增两层：

- `packages/<name>/releases/<version>/...`：该 package version 的 source manifests
- `index/...`：bot 生成的全局静态索引

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
│   │       │   ├── holes.json
│   │       │   └── bridges.json
│   │       └── 1.1.0/
│   │           └── ...
│   └── package-b/
│       └── ...
├── index/
│   ├── holes/
│   │   ├── by-package/
│   │   └── by-qid/
│   ├── bridges/
│   │   ├── by-target/
│   │   ├── by-source/
│   │   └── by-declaring-package/
│   └── manifests/
│       └── stats.json
└── .github/workflows/
    ├── register.yml
    └── build-index.yml
```

## 6. Package-Local Source Manifests

这些文件是 source of truth，由 `gaia register` 生成或拷贝到 registry PR 中。作者 PR 只修改自己 package 的目录。

### 6.1 `exports.json`

记录该版本公开导出的 node interface。

```json
{
  "package": "package-b",
  "version": "2.1.0",
  "generated_at": "2026-04-08T12:00:00Z",
  "exports": [
    {
      "qid": "github:package_b::main_result",
      "label": "main_result",
      "type": "claim",
      "content": "B's main theorem.",
      "content_hash": "2fd4e1c67a2d28fced849ee1bb76e7391b93eb12f4f4a0a2b9f7f1c4d5e6a7b8"
    }
  ]
}
```

这里的 `content_hash` 与 IR `Knowledge.content_hash` 保持同格式，使用裸 64 位 hex；只有 `ir_hash` 使用 `sha256:` 前缀。

### 6.2 `holes.json`

只列出作者显式公开的 hole。

```json
{
  "package": "package-a",
  "version": "1.4.0",
  "generated_at": "2026-04-08T12:00:00Z",
  "holes": [
    {
      "qid": "github:package_a::key_missing_lemma",
      "label": "key_missing_lemma",
      "content": "A missing premise required by the main theorem.",
      "content_hash": "7f6a5b4c3d2e1f0099887766554433221100ffeeddccbbaa9988776655443322",
      "required_by": [
        "github:package_a::main_theorem"
      ]
    }
  ]
}
```

约束：

- `holes.json` 中的每个 hole 必须也是该版本的 exported claim
- hole 不能是自动扫描产物，必须来自作者显式标记
- `required_by` 的生成规则与 package-level extraction 保持一致，见 [2026-04-08-gaia-package-hole-bridge-design.md](2026-04-08-gaia-package-hole-bridge-design.md) §5.2.1

### 6.3 `bridges.json`

记录该版本声明的 bridge relations。

```json
{
  "package": "package-b",
  "version": "2.1.0",
  "generated_at": "2026-04-08T12:00:00Z",
  "bridges": [
    {
      "relation_id": "bridge_4a1f9d3c2b7e8f10",
      "relation_type": "fills",
      "source_qid": "github:package_b::main_result",
      "target_hole_qid": "github:package_a::key_missing_lemma",
      "target_package": "package-a",
      "target_version_req": ">=1.4.0,<2.0.0",
      "strength": "exact",
      "justification": "Theorem 3 in package B proves exactly the missing premise exposed by package A.",
      "declared_by_owner_of_source": true
    }
  ]
}
```

第三方 bridge package 也用同样格式，只是：

- `source_qid` 可能是 foreign
- `declared_by_owner_of_source = false`

其中：

- `relation_id` 使用 package-level 规定的稳定 hash 规则，见 [2026-04-08-gaia-package-hole-bridge-design.md](2026-04-08-gaia-package-hole-bridge-design.md) §5.3
- `target_version_req` 来自 declaring package 对 `target_package` 的依赖约束
- `declared_by_owner_of_source = (QID(source_qid).package == declaring_package)`

## 7. Validation Rules

`register.yml` 在现有校验基础上，新增以下机械规则。

### 7.1 `exports.json`

- 每个 `qid` 必须存在于该 package version 的 compiled IR
- 每个导出必须属于本 package namespace
- `exports: []` 是合法的；纯 bridge package 可以没有 exported claims

### 7.2 `holes.json`

- 每个 `hole.qid` 必须出现在 `exports.json`
- 每个 `required_by` 必须是本 package version 中存在的 exported claim
- 同一版本内 `hole.qid` 不可重复

### 7.3 `bridges.json`

- `source_qid` 必须可解析
  - 若属于 declaring package，则必须在该版本 `exports.json` 中
  - 若属于 foreign package，则该 package / version requirement 必须出现在 dependencies 中
- `target_hole_qid` 必须可解析到一个已注册 package 的 exported hole
- `target_version_req` 必须来自对 `target_package` 的依赖约束，并且可满足至少一个已注册版本
- `relation_type` 当前只允许 `fills`
- `strength` 当前只允许 `exact | partial | conditional`
- 对同一 `declaring_package@declaring_version`，重复的 `(source_qid, target_hole_qid)` relation 必须被拒绝

### 7.4 PR Ownership Rule

注册 package version 的 PR：

- **允许**修改 `packages/<self>/**`
- **禁止**手工修改 `index/**`

这样可以避免所有作者 PR 同时争抢全局索引文件。

## 8. Derived Indexes

`index/**` 不是 author-authored source of truth，而是 merge 到 `main` 后由 bot 生成的派生文件。

### 8.1 Hole Index

#### `index/holes/by-package/<package>.json`

```json
{
  "package": "package-a",
  "holes": [
    {
      "qid": "github:package_a::key_missing_lemma",
      "introduced_in": "1.4.0",
      "latest_version": "1.6.0"
    }
  ]
}
```

#### `index/holes/by-qid/<shard>/<encoded-qid>.json`

```json
{
  "qid": "github:package_a::key_missing_lemma",
  "owner_package": "package-a",
  "versions": [
    {
      "version": "1.4.0",
      "content": "A missing premise required by the main theorem.",
      "required_by": ["github:package_a::main_theorem"]
    }
  ]
}
```

### 8.2 Bridge Index

#### `index/bridges/by-target/<shard>/<encoded-hole-qid>.json`

这是最核心的查询入口：`hole -> who claims to fill it`

```json
{
  "target_hole_qid": "github:package_a::key_missing_lemma",
  "bridges": [
    {
      "relation_id": "bridge_4a1f9d3c2b7e8f10",
      "source_qid": "github:package_b::main_result",
      "declaring_package": "package-b",
      "declaring_version": "2.1.0",
      "strength": "exact",
      "declared_by_owner_of_source": true,
      "justification": "..."
    },
    {
      "relation_id": "bridge_95c62be0ad1f4e23",
      "source_qid": "github:bridge_c::adapter_claim",
      "declaring_package": "package-c-bridge",
      "declaring_version": "0.1.0",
      "strength": "conditional",
      "declared_by_owner_of_source": false,
      "justification": "..."
    }
  ]
}
```

#### `index/bridges/by-source/<shard>/<encoded-claim-qid>.json`

反向查询：`claim -> what holes does it claim to fill`

#### `index/bridges/by-declaring-package/<package>.json`

查看某 package 发布过哪些 bridge relations。

## 9. Build Flow

### 9.1 Registration PR

作者或 bot 提交 package version PR 时：

1. 更新 `Package.toml / Versions.toml / Deps.toml`
2. 按 rollout phase 新增 `releases/<version>/...` manifests
3. 不修改 `index/**`

phase 对应关系是：

- **Phase 1**：只提交 `exports.json`
- **Phase 2**：再提交 `holes.json`
- **Phase 3**：再提交 `bridges.json`

package 本地编译可以先行生成后续 phase 的 preview manifests，但 registry 只接收当前 phase 正式支持的文件。

### 9.2 Post-Merge Index Build

`build-index.yml` 在 `main` 上运行：

1. 遍历 `packages/*/releases/*/{holes,bridges}.json`
2. 重建 `index/holes/**`
3. 重建 `index/bridges/**`
4. 更新 `index/manifests/stats.json`
5. 由 bot commit 回 registry repo

这意味着：

- package PR merge 不依赖热点索引文件冲突
- 索引是 deterministic derived artifact
- 任意人都可以在本地重建并审计

## 10. Worked Scenarios

### 10.1 Scenario A: B immediately knows it fills A

前提：

- A 已注册，并公开了 `key_missing_lemma` 这个 exported hole
- B 在自己的 package 里直接声明 `fills(b_result, key_missing_lemma)`

authoring example 见 [2026-04-08-gaia-lang-hole-fills-design.md](2026-04-08-gaia-lang-hole-fills-design.md) §6.1。

那么 registry 层会看到：

1. `packages/package-a/releases/<version>/holes.json`
   含 `github:package_a::key_missing_lemma`
2. `packages/package-b/releases/<version>/bridges.json`
   含 `source_qid = github:package_b::b_result`
   和 `target_hole_qid = github:package_a::key_missing_lemma`
3. bot 生成：
   `index/bridges/by-target/.../github:package_a::key_missing_lemma.json`

该 index 文件中，这条 relation 的：

- `declaring_package = package-b`
- `declared_by_owner_of_source = true`

### 10.2 Scenario B: B did not notice, later C discovers it

前提：

- A 已注册，并公开了 `key_missing_lemma`
- B 已注册，只导出了 `b_result`，但没有 bridge relation
- 后来 C 发布 bridge package，声明 `fills(package_b::b_result, package_a::key_missing_lemma)`

authoring example 见 [2026-04-08-gaia-lang-hole-fills-design.md](2026-04-08-gaia-lang-hole-fills-design.md) §6.2。

那么 registry 层会看到：

1. `packages/package-b/releases/<version>/bridges.json`
   仍然为空
2. `packages/package-c-bridge/releases/<version>/bridges.json`
   含这条 relation
3. bot 重建 `index/bridges/by-target/.../github:package_a::key_missing_lemma.json`

于是最终查询 A 的 hole 时，仍然能看到这条 bridge，只是：

- `declaring_package = package-c-bridge`
- `declared_by_owner_of_source = false`

这里不需要修改 A 或 B 的 registry 目录。

### 10.3 Boundary Condition: A did not export a hole

如果 A 没有在自己的 package manifests 中公开某个 hole：

- registry 不会为它建立 `index/holes/by-qid/...`
- B 或 C 也不能把指向它的关系注册成正式 bridge relation

所以 registry 只索引：

- 明确公开的 hole interfaces
- 明确声明的 fills relations

不会自动把任意 premise 升格成公共 hole。

## 11. Why This Works on a GitHub Repo

### 11.1 思想实验 A: 1000 个 packages

如果没有全局静态索引：

- 查询一个 hole 是否被填，需要扫所有 package manifests

这对人类和 CLI 都很差。

有 `index/bridges/by-target/<hole>.json` 后：

- 只要一次精确 fetch

所以这个规模下，静态派生索引已经值得做。

### 11.2 思想实验 B: 5 万个 packages

如果每个注册 PR 都直接改一个全局 `bridges.json`：

- 热门 hole 会让 PR 冲突频发
- bot 和人类都很难稳定合并

所以全局 bridge index 不能是 PR-authored 文件，只能是 post-merge derived artifact。

### 11.3 思想实验 C: 20 万条 bridge relations

如果只有单个总文件：

- diff 很大
- 下载成本高
- GitHub API 单文件读取变笨重

所以索引必须分片。推荐：

- 按 encoded qid 的 hash prefix 做二级 shard
- 单文件只服务一个 key 的精确查询

这样 GitHub repo 仍然能承载这个业务逻辑，因为它处理的是：

- 很多小的静态文件
- 低冲突写入
- 高频精确读取

而不是动态 join 查询。

### 11.4 思想实验 D: “帮我发现可能能填这个 hole 的包”

这是 discovery，不是 registry source-of-truth。

正确做法是：

- 离线 job 跑 embedding / text match / dependency heuristics
- 把结果写成 suggestion artifacts 或 GitHub issues
- 由人或 agent 再决定是否写成正式 bridge relation

不应该把这类 fuzzy logic 塞进注册主路径。

## 12. Query Model

在 GitHub-backed registry 下，推荐的读取模式是：

1. **精确定位 package**
   继续走 `packages/<name>/...`

2. **精确定位 hole**
   读取 `index/holes/by-qid/...`

3. **精确定位 bridge target**
   读取 `index/bridges/by-target/...`

4. **精确定位 bridge source**
   读取 `index/bridges/by-source/...`

不推荐：

- 运行时扫描全仓
- 在客户端做跨 package join
- 把 GitHub code search 当主要 API

GitHub code search 可以作为人类 fallback，不应成为 CLI 的基础协议。

## 13. Migration Path

建议分三步落地。

### Phase 1

- 仅支持 `exports.json`
- 为未来 `holes` / `bridges` 留目录结构
- local compiler MAY already emit preview `holes.json` / `bridges.json`，但 registry 不消费

### Phase 2

- 支持 `holes.json`
- 生成 `index/holes/**`

### Phase 3

- 支持 `bridges.json`
- 生成 `index/bridges/**`
- 提供 CLI / 网页查询

这样不会一次把 package DSL、registry CI、discovery、网站全部绑死。

## 14. Decisions

1. **需要 bridge layer，但不需要第二个 registry**
   仍然是一个统一 GitHub repo。

2. **bridge relation 来源在 package，查询不靠扫 package**
   关系写在 package manifests 中，读取走 derived indexes。

3. **所有全局索引必须是 bot 生成，不允许作者 PR 直接改**
   否则规模一上来一定产生 merge hotspot。

4. **hole 是显式公共接口，不是自动叶子前提枚举**
   否则 registry 会充满 package 内部建模细节，无法作为生态接口。

5. **registry 记录声明，不裁决真理**
   多个 package 可以同时声称填同一个 hole。

## 15. Open Questions

1. `strength = partial / conditional` 时，是否需要结构化 `conditions` 字段？
2. bridge package 是否应该有更轻量的模板与 semver 规则？
3. registry 是否需要额外的 `suggestions/` 目录来承接未确认 discovery 结果？
