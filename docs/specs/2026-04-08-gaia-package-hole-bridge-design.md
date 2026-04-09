# Gaia Package Public Premise / Bridge Manifest Design

> **Status:** Proposal
>
> **Date:** 2026-04-08
>
> **Companion docs:** [2026-04-08-gaia-lang-hole-fills-design.md](2026-04-08-gaia-lang-hole-fills-design.md), [2026-04-08-registry-hole-bridge-index-design.md](2026-04-08-registry-hole-bridge-index-design.md)
>
> **Depends on:** [../foundations/gaia-lang/package.md](../foundations/gaia-lang/package.md), [2026-04-02-gaia-registry-design.md](2026-04-02-gaia-registry-design.md)
>
> **Supersedes:** the earlier hole / bridge package proposal merged via PRs #362 and #364. Open implementation PRs #365 / #366 / #367 target the superseded design and should be replaced rather than merged as-is.

## 1. Problem

如果 Lang 层把 `hole` 改成“编译器自动推出的 release-scoped public premise role”，那么 package 层也必须随之改变：

1. 不能再把 `holes.json` 设计成“作者显式 export 的 hole”
2. 必须区分：
   - author-declared exports
   - compiler-derived public premises
   - local holes
   - bridge relations
3. bridge relation 不能只记录 `target_hole_qid`
   因为 target 是否还是 hole，会随着 release 改变

因此，package contract 需要从：

- `exports / holes / bridges`

升级成：

- `exports / premises / holes / bridges`

## 2. Design Goals

1. **Keep package as the source unit**
   package 仍然是 authoring、compile、versioning、registration 的基本单位。

2. **Compiler-derived public premise surface**
   `premises.json` 必须完全从 package source + dependency interfaces 机械推导。

3. **Release-scoped bridge targets**
   `bridges.json` 必须记录 target interface snapshot，而不是漂浮的 hole symbol。

4. **Manifest-level separation of roles**
   `exported conclusion`、`public premise`、`local hole`、`foreign dependency` 必须在 manifests 里清晰区分。

5. **No extra source-level package class**
   bridge package 仍然是普通 `knowledge-package`。

## 3. Key Decisions

### 3.1 `.gaia/manifests/` 扩展为四个文件

推荐 layout：

```text
.gaia/
├── ir.json
├── ir_hash
└── manifests/
    ├── exports.json
    ├── premises.json
    ├── holes.json
    └── bridges.json
```

其中：

- `exports.json`
  - 作者显式 export 的公开节点
- `premises.json`
  - 从 exports 的依赖闭包中自动推出的 public premises
- `holes.json`
  - `premises.json` 中 `role == "local_hole"` 的子集
- `bridges.json`
  - 当前 package release 声明的 fills relations

### 3.2 `__all__` 仍是 source-level public surface

本设计不新增：

- `__holes__`
- `__premises__`
- `__bridges__`

因为：

- premise surface 是编译派生物
- bridge surface 来自 strategies
- source 层只需维护一个作者显式导出的 public surface

### 3.3 `hole` 不再由 source marker 决定

package manifests 不再以：

- `metadata["gaia"]["role"] == "hole"`

作为 hole 的根本来源。

如果源码里保留 `hole()` sugar，它最多只能作为 authoring hint。真正进入 `holes.json` 的条件是：

- 该 claim 落在 exported claim 的 public premise closure 中
- 且在当前 release 上角色为 `local_hole`

## 4. Manifest Schemas

### 4.1 `exports.json`

记录作者显式导出的节点。

```json
{
  "manifest_schema_version": 1,
  "package": "package-a",
  "version": "1.4.0",
  "ir_hash": "sha256:...",
  "exports": [
    {
      "qid": "github:package_a::main_theorem",
      "label": "main_theorem",
      "type": "claim",
      "content": "Main theorem.",
      "content_hash": "2fd4e1..."
    }
  ]
}
```

提取规则：

- 直接来自 IR 中 `exported = true` 的 knowledge
- 仍保留 `claim / setting / question`
- `content_hash` 使用 IR 的 node-level hash

### 4.2 `premises.json`

记录 exported claims 的 release-scoped public premise interface。

```json
{
  "manifest_schema_version": 1,
  "package": "package-a",
  "version": "1.4.0",
  "ir_hash": "sha256:...",
  "premises": [
    {
      "qid": "github:package_a::key_missing_lemma",
      "label": "key_missing_lemma",
      "content": "A missing lemma.",
      "content_hash": "7f6a5b...",
      "role": "local_hole",
      "interface_hash": "sha256:...",
      "exported": false,
      "required_by": [
        "github:package_a::main_theorem"
      ]
    }
  ]
}
```

字段约束：

- `role`
  - `local_hole`
  - `foreign_dependency`
- `interface_hash`
  - package/manifest 层派生字段，不进入 Gaia IR
- `exported`
  - 当且仅当该 claim 同时出现在同版本的 `exports.json` 中时为 `true`
  - `false` 表示它只是被派生为 public premise，不是作者显式导出的 public conclusion
- `required_by`
  - 当前 release 上最接近的 exported claims roots

### 4.3 `holes.json`

`holes.json` 是 `premises.json` 的 convenience subset：

```json
{
  "manifest_schema_version": 1,
  "package": "package-a",
  "version": "1.4.0",
  "ir_hash": "sha256:...",
  "holes": [
    {
      "qid": "github:package_a::key_missing_lemma",
      "label": "key_missing_lemma",
      "content": "A missing lemma.",
      "content_hash": "7f6a5b...",
      "interface_hash": "sha256:...",
      "required_by": [
        "github:package_a::main_theorem"
      ]
    }
  ]
}
```

提取规则：

- 来自 `premises.json`
- 只保留 `role == "local_hole"` 的条目

### 4.4 `bridges.json`

bridge relation 必须绑定 target interface snapshot。

```json
{
  "manifest_schema_version": 1,
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

相比旧设计，关键变化是：

- `target_hole_qid` -> `target_qid`
- 新增 `target_resolved_version`
- 新增 `target_interface_hash`
- `target_role` 是编译时验证结果，不来自 source marker

其中 `target_resolved_version` 的定义是：

- compile 当前环境里实际 import 解析到的 dependency release version

而不是：

- 满足约束的最新 registry version
- 满足约束的最低 version
- 作者手工填写的任意版本号

## 5. Derivation Rules

### 5.1 Export Roots

Phase 1 先把所有 exported claims 当作 export roots。

如果未来需要把“公开结论”和“公开 supporting claim”再细分，可以在 manifest 层继续加 role，但不影响 premise derivation 的核心协议。

### 5.2 Public Premise Discovery

对每个 export root：

1. 找出其 local supporting strategies
2. 递归向上遍历这些 strategy 的 `premises`
3. 遇到没有 local support 的 claim 时停止
4. 生成一个 public premise record

分类：

- local claim -> `local_hole`
- foreign claim -> `foreign_dependency`

### 5.3 `required_by`

`required_by` 不应是整张图上所有下游节点，而应保持为稳定的 interface summary。

Phase 1 规则：

- 对每个 public premise，自底向下做 BFS
- 遇到 exported claim root 时停止该分支
- 记录这些“最接近的下游 exported roots”
- 去重后排序输出

注意：

- `required_by` 不进入 `interface_hash`
- 否则新增一个 exported conclusion 就会让所有旧 bridge 全部失效
- 这是一种有意的简化；代价是同一 premise 在不同 release 上服务于不同 exported roots 集合时，仍可能被视为同一接口

### 5.4 `interface_hash`

`interface_hash` 推荐由下面字段 canonicalize 后求 hash：

- `qid`
- `content_hash`
- `role`
- `parameters`
- `manifest_schema_version`

明确不包含：

- `required_by`
- `generated_at`
- `package version`

原因：

- 这是 premise interface 的 identity hash
- 不是 whole-release hash
- 更不应该被无关展示字段污染

这里的 `manifest_schema_version` 指的是 manifest 协议版本，而不是：

- `gaia-lang` 的包版本
- Gaia IR schema 版本
- package 自己的 semver

当前固定定义为：

- `manifest_schema_version = 1`

并且应写入所有 package-level manifests 的顶层。

变化矩阵：

| 变化 | `interface_hash` 是否变化 |
|------|---------------------------|
| claim content 改动 | 变化 |
| claim parameters 改动 | 变化 |
| role 从 `local_hole` 变为 `foreign_dependency` | 变化 |
| `required_by` 改动 | 不变化 |
| `manifest_schema_version` bump | 变化 |
| `gaia-lang` 升级 | 不变化 |
| Gaia IR 升级 | 不变化 |

Trade-off:

- `required_by` 被排除在 `interface_hash` 之外，避免“新增一个 exported conclusion 就让所有 bridge 全部 stale”
- 代价是同一 premise 在不同 release 上被更多 exported roots 复用时，仍可能被看作同一接口
- Phase 1 接受这个 trade-off；若未来发现 bridge 语义漂移是实际问题，可新增 `context_hash` 或更显式的 root-targeting relation

### 5.5 Dependency Manifest Resolution

当 package compile 遇到：

```python
fills(source=..., target=foreign_claim)
```

时，必须读取 dependency 的 compiled premise interface manifests。

Phase 1 规则：

1. 先根据当前 Python import 实际解析到的 dependency module 定位安装路径
2. 若该 dependency 是 editable/source install，则优先使用该 source tree 下的：
   - `.gaia/manifests/premises.json`
   - `.gaia/manifests/holes.json`
3. 若该 dependency 是 wheel/site-packages install，则读取对应安装目录中的同名 manifest

缺失策略：

- 如果 dependency manifest 不存在，compile 应 hard error
- 错误消息应明确要求作者先在 dependency package 上运行 `gaia compile`

staleness 策略：

- compile 应把 dependency manifest 的 `ir_hash` 与该 dependency 当前 source/build 的 compile 结果对比
- 若 manifest stale，应 hard error，而不是静默写入过期的 `target_interface_hash`

兼容旧包策略：

- 对于 manifest schema 引入前发布的旧 package，需要显式迁移后才能作为 `fills` target
- Phase 1 不做“无 manifest 时降级 warning”或“自动编译 dependency”

### 5.6 `relation_id`

`relation_id` 推荐定义为：

```text
relation_id = "bridge_" + sha256(
  declaring_package + "|" + declaring_version + "|" +
  source_qid + "|" + source_content_hash + "|" +
  target_qid + "|" + target_interface_hash + "|" +
  relation_type
)[:16]
```

这样：

- target interface 变了，relation_id 会变
- source 内容变了，relation_id 也会变

## 6. Validation Rules

### 6.1 `premises.json`

- 每个 premise 必须是 claim
- 同一 `(qid, role, interface_hash)` 不可重复
- `role == "local_hole"` 时，qid 必须属于当前 package
- `role == "foreign_dependency"` 时，qid 必须属于 foreign package

### 6.2 `holes.json`

- 每个 hole 必须在 `premises.json` 中存在
- 且其 `role == "local_hole"`
- `interface_hash` 必须与 `premises.json` 对应条目一致

### 6.3 `bridges.json`

- `source_qid` 必须可解析
- `source_content_hash` 必须与 source node 匹配
- `target_qid` 必须可解析
- `target_dependency_req` 必须来自 declaring package 的依赖约束
- `target_resolved_version` 必须是 compile 时实际验证到的版本
- `target_interface_hash` 必须与 target release 的 `premises.json` / `holes.json` 对应
- `target_role` 当前必须是 `local_hole`
- 同一 package version 内，重复 `(source_qid, target_qid, target_interface_hash)` 必须报错

### 6.4 Phase Rollout

PR 369 的 redesign 之后，旧的 phased rollout 计划已经不再适用。

在当前设计里，四份 manifest 共同组成 release-scoped package interface：

- `exports.json`
  - author-declared public surface
- `premises.json`
  - compiler-derived public premise interface
  - 是 hole classification 和 bridge target validation 的 source of truth
- `holes.json`
  - `premises.json` 中 `role == "local_hole"` 的 convenience subset
- `bridges.json`
  - 本 release 声明的 fills relations

因此当前 contract 应对齐为：

- `gaia compile`
  - 生成全部四份 manifest
- `gaia register`
  - 一次性上传全部四份 manifest 到 `packages/<name>/releases/<version>/`
- registry index builder
  - 以 `premises.json` 为 source of truth
  - 派生 `index/premises/**`、`index/holes/**`、`index/bridges/**`

原因：

- 没有 `premises.json`，registry 无法验证 bridge target 的 interface snapshot
- `holes.json` 只是 `premises.json` 的 filter view，单独 phase 化没有技术意义
- `bridges.json` 的 target validation 依赖同版本的 `premises.json`

## 7. Scenario Walkthroughs

### 7.1 Scenario A: B 直接声明 fills A 的缺口

A 源码：

```python
from gaia.lang import claim, deduction

main_theorem = claim("Main theorem.")
key_missing_lemma = claim("A missing lemma.")

deduction(
    premises=[key_missing_lemma],
    conclusion=main_theorem,
)

__all__ = ["main_theorem"]
```

编译 A 后：

- `exports.json`
  - `main_theorem`
- `premises.json`
  - `key_missing_lemma`, role=`local_hole`
- `holes.json`
  - `key_missing_lemma`

B 源码：

```python
from gaia.lang import claim, fills
from package_a import key_missing_lemma

b_result = claim("Theorem 3.")

fills(source=b_result, target=key_missing_lemma, reason="...")

__all__ = ["b_result"]
```

编译 B 时：

- 从依赖接口中读到 `package_a@1.4.0`
- 确认 `key_missing_lemma` 在该 release 上是 `local_hole`
- 生成一条带 `target_resolved_version` 和 `target_interface_hash` 的 bridge

### 7.2 Scenario B: C 做第三方 bridge package

C 可以是 zero-local package：

```python
from gaia.lang import fills
from package_a import key_missing_lemma
from package_b import b_result

fills(source=b_result, target=key_missing_lemma, reason="...")
```

编译后：

- `exports.json` 可以为空
- `premises.json` 可以为空
- `bridges.json` 仍然合法
- `declared_by_owner_of_source = false`

## 8. Compatibility Notes

### 8.1 Earlier `hole()`-driven extraction

如果已有实现基于：

- exported claim + `metadata["gaia"]["role"] == "hole"`

来生成 `holes.json`，应视为 prototype。

迁移方向应是：

- 新增 `premises.json`
- 先从 dependency closure 自动推出 premise role
- `holes.json` 退化成 `premises.json` 的 subset
- 删除 `hole()` 作为主线 source primitive

### 8.2 Why `target_dependency_req` and `target_resolved_version` must coexist

只写 dependency range 不够，因为：

- `>=1.4.0,<2.0.0` 可能覆盖多个 release
- 而 hole 身份可能只在其中某些 release 上成立

所以：

- `target_dependency_req` 表示作者声明的兼容范围
- `target_resolved_version` 表示当前 compile 实际验证到的 release

二者缺一不可。
