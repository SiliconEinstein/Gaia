# Gaia Package Hole / Bridge Manifest Design

> **Status:** Proposal
>
> **Date:** 2026-04-08
>
> **Companion docs:** [2026-04-08-gaia-lang-hole-fills-design.md](2026-04-08-gaia-lang-hole-fills-design.md), [2026-04-08-registry-hole-bridge-index-design.md](2026-04-08-registry-hole-bridge-index-design.md)
>
> **Depends on:** [../foundations/gaia-lang/package.md](../foundations/gaia-lang/package.md), [2026-04-02-gaia-registry-design.md](2026-04-02-gaia-registry-design.md)

## 1. Problem

当前 package model 里，public surface 主要只有：

- `__all__`
- compiled IR
- register 时写入的 `Package.toml / Versions.toml / Deps.toml`

这对“普通知识包注册”足够，但对新的 `hole / fills` 生态还差一层 package contract：

1. package 本地如何把 public holes 明确产出成制品？
2. package 本地如何把 fills relations 明确产出成制品？
3. `gaia register` 如何把这些信息安全地带进 registry，而不引入 PR hotspot？

## 2. Design Goals

1. **Keep package as the source unit**
   package 仍然是 authoring、versioning、registration 的基本单位。

2. **Deterministic local artifacts**
   `exports / holes / bridges` 必须能从当前 package source 机械生成。

3. **Registry-ready manifests**
   本地产物应能直接被 `gaia register` 带入 registry。

4. **No new package class required**
   bridge package 仍然是普通 `knowledge-package`，不引入强制的新 package type。

5. **Version-aware**
   manifests 必须和当前 package version 一起发布、一起审计。

## 3. Key Decisions

### 3.1 `.gaia/manifests/` 成为本地产物

推荐在 package 本地新增：

```text
.gaia/
├── ir.json
├── ir_hash
└── manifests/
    ├── exports.json
    ├── holes.json
    └── bridges.json
```

这些文件都是 deterministic derived artifacts，应由 `gaia compile` 生成。

### 3.2 `__all__` 仍然是唯一 public surface

我们不新增 `__holes__` 或 `__bridges__`。

规则保持简单：

- exported = 在 `__all__`
- public hole = exported claim + `proof_state = "hole"`
- bridge relation = local strategy metadata 中声明 `ecosystem_relation.type = "fills"`

### 3.3 Bridge package 不是新的 package type

bridge package 仍然是：

```toml
[tool.gaia]
type = "knowledge-package"
```

它只是一个**用途上的子类**，不是新的协议对象。

原因：

- package lifecycle 不需要分叉
- IR schema 不需要分叉
- register / add / compile / infer 全都可以复用

如果未来确实需要更强的 UX 区分，再加 optional metadata 即可。

## 4. Local Artifact Layout

### 4.1 Current

当前 package 本地产物主要是：

```text
.gaia/
├── ir.json
├── ir_hash
└── reviews/
    └── ...
```

### 4.2 Proposed

扩展为：

```text
.gaia/
├── ir.json
├── ir_hash
├── manifests/
│   ├── exports.json
│   ├── holes.json
│   └── bridges.json
└── reviews/
    └── ...
```

这些 manifests 和 IR 一样，都应该是 git-tracked compiled artifacts。

## 5. Extraction Rules

### 5.1 `exports.json`

记录 package 的公开接口。

建议结构：

```json
{
  "package": "package-b",
  "version": "2.1.0",
  "ir_hash": "sha256:...",
  "generated_at": "2026-04-08T12:00:00Z",
  "exports": [
    {
      "qid": "github:package_b::main_result",
      "label": "main_result",
      "type": "claim",
      "content": "B's main theorem.",
      "content_hash": "sha256:..."
    }
  ]
}
```

提取规则：

- 来自 IR 中 `exported = true` 的 `Knowledge`
- 包含 `claim / setting / question`
- registry 侧目前重点消费 `claim`，但 manifest 保留完整 exported knowledge surface

### 5.2 `holes.json`

记录 package 公开暴露的 holes。

```json
{
  "package": "package-a",
  "version": "1.4.0",
  "ir_hash": "sha256:...",
  "generated_at": "2026-04-08T12:00:00Z",
  "holes": [
    {
      "qid": "github:package_a::key_missing_lemma",
      "label": "key_missing_lemma",
      "content": "A missing premise required by the main theorem.",
      "content_hash": "sha256:...",
      "required_by": ["github:package_a::main_theorem"]
    }
  ]
}
```

提取规则：

- 仅从 IR 中 `exported = true` 的 claim 提取
- 且其 metadata 标记 `proof_state = "hole"`
- `required_by` 由图结构派生，不由作者手填

### 5.2.1 `required_by` 的最小规则

Phase 1 先用最简单的可解释规则：

- 找出所有直接把该 hole 作为 premise 的 local strategies
- 若这些 strategy 的 conclusion 是 exported claim，则记入 `required_by`

以后如果要更强，可以再扩展成“最近 exported downstream claims”。

### 5.3 `bridges.json`

记录 package 当前版本声明的 fills relations。

```json
{
  "package": "package-b",
  "version": "2.1.0",
  "ir_hash": "sha256:...",
  "generated_at": "2026-04-08T12:00:00Z",
  "bridges": [
    {
      "relation_id": "bridge_sha256_...",
      "relation_type": "fills",
      "source_qid": "github:package_b::main_result",
      "target_hole_qid": "github:package_a::key_missing_lemma",
      "strength": "exact",
      "mode": "deduction",
      "declared_by_owner_of_source": true,
      "justification": "Theorem 3 proves exactly the missing lemma in package A."
    }
  ]
}
```

提取规则：

- 扫描 local strategies
- 找出 metadata 中 `ecosystem_relation.type == "fills"` 的 strategy
- 提取其 `conclusion` 作为 `target_hole_qid`
- 提取其唯一 premise 作为 `source_qid`

如果 `fills` 后续允许 richer metadata，则按 metadata 补全 `strength / mode / justification`。

## 6. Package Authoring Conventions

### 6.1 Public hole

作者如果想公开一个可被别人填补的 hole，需要同时做到：

1. 用 `hole(...)` 声明
2. 放进 `__all__`

只做其一都不够：

- 只有 `hole(...)` 没有 export：内部 hole
- 只有 export 没有 `hole(...)`：普通 public claim

### 6.2 Direct fill in a paper package

如果 B 自己知道某个结果 fills A 的 hole，推荐直接写在 B 里。

```python
from gaia.lang import claim, fills
from package_a import key_missing_lemma

b_result = claim("Theorem 3.")
fills(source=b_result, hole=key_missing_lemma, reason="...")
```

这会让：

- IR 中出现 ordinary cross-package strategy
- `.gaia/manifests/bridges.json` 中出现一条 fills relation

### 6.3 Third-party bridge package

如果 C 后来才发现这层关系，C 可以发一个普通 package：

- 引入 A 的 exported hole
- 引入 B 的 exported claim
- 写 `fills(...)`

不要求额外 package type。

## 7. Worked Scenarios

### 7.1 Scenario A: B immediately knows it fills A

package A 编译后，关键本地产物会是：

- `.gaia/manifests/exports.json`：包含 `main_theorem` 和 `key_missing_lemma`
- `.gaia/manifests/holes.json`：包含 `key_missing_lemma`
- `.gaia/manifests/bridges.json`：为空

package B 编译后，关键本地产物会是：

- `.gaia/manifests/exports.json`：包含 `b_result`
- `.gaia/manifests/holes.json`：为空
- `.gaia/manifests/bridges.json`：包含一条 `source_qid = b_result`、`target_hole_qid = key_missing_lemma` 的 relation

这里 `declared_by_owner_of_source = true`，因为 relation 是由 B 自己声明的。

### 7.2 Scenario B: B did not notice, later C discovers it

package B 编译后：

- `.gaia/manifests/exports.json`：包含 `b_result`
- `.gaia/manifests/bridges.json`：为空

package C bridge 编译后：

- `.gaia/manifests/exports.json`：可以为空或只含少量本地 summary nodes
- `.gaia/manifests/holes.json`：通常为空
- `.gaia/manifests/bridges.json`：包含 `source_qid = package_b::b_result`、`target_hole_qid = package_a::key_missing_lemma`

这里 `declared_by_owner_of_source = false`，因为 relation 由第三方声明。

### 7.3 Boundary Condition: A did not export a hole

如果 A 没有公开 hole interface：

- package A 的 `holes.json` 中不会出现该前提
- package B/C 即使写了某种普通 cross-package deduction，也不应进入 `bridges.json`

也就是说，package 层的 bridge manifest 只承认“指向 exported hole 的 fills relation”。

## 8. Package Semantics

### 8.1 Public API

package 的稳定 API 仍然首先由 exported nodes 决定。

因此：

- exported claims / holes 是 import-facing API
- bridge relations 是 discovery-facing public metadata

这两者都公开，但稳定性级别不同。

### 8.2 Semver Guidance

推荐规则：

| Change | Version level | Reason |
|--------|---------------|--------|
| 新增 exported hole | MINOR | 新增公共接口 |
| 修改 / 删除 exported hole 语义 | MAJOR | 破坏 hole API |
| 新增 fills relation | MINOR | 新增公开 relation metadata |
| 修改 / 删除 fills relation | MINOR | 影响 discovery surface，但不破坏 import API |

解释：

- hole 是 package API 的一部分
- fills 更像对外公开的 relation metadata，不建议把它当成 import-breaking API

## 9. `gaia compile` Changes

推荐 `gaia compile` 扩展为：

1. 正常生成 `.gaia/ir.json`
2. 正常生成 `.gaia/ir_hash`
3. 额外生成 `.gaia/manifests/exports.json`
4. 额外生成 `.gaia/manifests/holes.json`
5. 额外生成 `.gaia/manifests/bridges.json`

### 9.1 Why compile, not register

如果等到 `gaia register` 才临时构造这些 manifests，会带来两个问题：

- 作者本地难以预览 package 对外暴露了哪些 holes / bridges
- register 阶段逻辑变重，难以本地审计

而这些文件本质上都只是 IR 和 metadata 的 deterministic projection，所以更适合放在 compile 阶段。

## 10. `gaia check` Changes

推荐新增 package-level 校验：

### 10.1 Hole checks

- every exported hole is a claim
- every exported hole appears in `exports.json`
- every exported hole has at least one downstream local use, unless explicitly suppressed

最后一条是 warning，不是 hard error。因为有些 package 会先发布 hole interface，再等待别人填补。

### 10.2 Bridge checks

- every fills relation has exactly one `source_qid`
- `source_qid` resolves to claim
- `target_hole_qid` resolves to claim
- if target is local and not exported hole, do not emit to bridge manifest
- if target is foreign, dependency resolution must succeed

## 11. `gaia register` Changes

当前 `gaia register` 只准备：

- `Package.toml`
- `Versions.toml`
- `Deps.toml`

推荐扩展为同时携带：

- `packages/<name>/releases/<version>/exports.json`
- `packages/<name>/releases/<version>/holes.json`
- `packages/<name>/releases/<version>/bridges.json`

### 11.1 Register payload shape

计划输出中新增：

```json
{
  "files": {
    "packages/package-a/Package.toml": "...",
    "packages/package-a/Versions.toml": "...",
    "packages/package-a/Deps.toml": "...",
    "packages/package-a/releases/1.4.0/exports.json": "...",
    "packages/package-a/releases/1.4.0/holes.json": "...",
    "packages/package-a/releases/1.4.0/bridges.json": "..."
  }
}
```

这样 register PR 依然是 package-local 的，不直接碰 `index/**`。

## 12. Bridge Package UX

### 12.1 No mandatory local summary claim

bridge package 不强制要求作者额外写一个本地 summary claim。

原因：

- package 的主要公开对象就是 cross-package relation 本身
- 强制再写一个 summary claim 只会制造样板噪声

如果作者愿意写本地 summary claim，用于 README narrative，可以作为可选增强。

### 12.2 Discovery

bridge package 在 registry 中的 discoverability，主要依靠：

- `bridges.json`
- registry 的 derived indexes

而不是依赖 exported claims。

## 13. Why This Package Layer Matters

### 13.1 Thought Experiment: no local manifests

如果 package 本地没有 `exports / holes / bridges` manifests：

- register 时必须重新从 source 和 IR 临时推断
- 作者本地看不到 registry 会看到什么
- registry 和 package 很难保证同一套抽取规则

### 13.2 Thought Experiment: manifests generated at compile time

如果 manifests 是 compile artifact：

- 作者本地可审计
- CI 可重放
- register 只是搬运 deterministic outputs

这更符合当前 Gaia 的 artifact philosophy。

## 14. Decisions

1. **package 继续是唯一发布单位。**
2. **`__all__` 继续是唯一 public interface 开关。**
3. **`.gaia/manifests/` 新增 `exports / holes / bridges`。**
4. **这些 manifests 由 `gaia compile` 生成，而不是 `gaia register` 临时拼。**
5. **bridge package 仍然是普通 `knowledge-package`，不是新的 package type。**

## 15. Open Questions

1. `.gaia/manifests/*.json` 是否也要像 `ir_hash` 一样参与 freshness / check contract？
2. `required_by` 是否需要同时输出直接下游和最近 exported 下游两种视图？
3. 是否需要在 `pyproject.toml` 里加 optional metadata，显式标注 package 的主要用途为 `bridge`？
