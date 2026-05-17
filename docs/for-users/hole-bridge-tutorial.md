# How to connect packages with holes and bridges

> **Gaia version:** 0.5.x
> **Author:** @SiliconEinstein
> **Date:** 2026-05-01

当你的 package 依赖另一个 package 中尚未证明的前提时，使用 hole/bridge 机制跨包补洞。

## 前提

- 已完成 [Quick Start](quick-start.md)，会写单个 package
- 了解 `claim` 和 `derive`（或 `deduction`）的基本用法
- 本地已安装 `gaia-lang >= 0.5`

## 步骤概览

1. Package A 导出一个结论，其未解析的前提自动成为 `local_hole`
2. Package B 声明 `fills(...)` 指向该 hole
3. 按顺序注册到 registry

## Gaia 自动做了什么

你**不需要**手动标记 hole。

当一个 package 导出结论时，`gaia build compile` 会自动计算依赖闭包：

- 未解析的本地 claim 前提 → `local_hole`
- 未解析的外部 claim 前提 → `foreign_dependency`

结果写入以下文件：

- `exports.json`
- `premises.json`
- `holes.json`
- `bridges.json`

其中 `holes.json` 是 `premises.json` 中 `role = "local_hole"` 的子集。

## 步骤 1：Package A — 产生一个 hole

`pyproject.toml`：

```toml
[project]
name = "paper-a-gaia"
version = "1.0.0"
dependencies = [
  "gaia-lang>=0.5",
]

[tool.gaia]
namespace = "github"
type = "knowledge-package"
uuid = "11111111-1111-1111-1111-111111111111"
```

`src/paper_a/__init__.py`：

```python
from gaia.engine.lang import claim
from gaia.engine.lang.compat import deduction

missing_lemma = claim("A missing lemma.")
main_theorem = claim("A theorem that depends on the missing lemma.")

deduction(
    premises=[missing_lemma],
    conclusion=main_theorem,
)

__all__ = ["main_theorem"]
```

> **为什么用 `compat.deduction`？** `deduction` 是 v5 的 named-strategy 动词；v0.5 中推荐用 `derive(main_theorem, given=[missing_lemma])`，功能等价。这里用 `compat.deduction` 是因为本教程特意展示旧的 authoring 形式如何把未解析前提暴露为 `local_hole`。新 package 应使用 `derive(...)`；详见 [Migration to alpha 0 §Layer 3](../migration.md#layer-3-legacy-dsl-verb-migration)。

编译并检查：

```bash
gaia build compile .
gaia build check .
```

预期结果：

- `exports.json` 包含 `main_theorem`
- `premises.json` 包含 `missing_lemma`，`role = "local_hole"`
- `holes.json` 包含同一个 `missing_lemma`

## 步骤 2：Package B — 填补 hole

Package B 依赖 Package A。

如果 A 尚未注册到 registry，在本地开发时需要先让 B 能 import A：

```bash
cd ../paper-b-gaia
uv add --editable ../paper-a-gaia
```

如果 A 已注册，推荐用 `gaia pkg add paper-a-gaia`——它会安装 pinned 版本并缓存 release beliefs。

`pyproject.toml`：

```toml
[project]
name = "paper-b-gaia"
version = "1.0.0"
dependencies = [
  "gaia-lang>=0.5",
  "paper-a-gaia>=1.0.0,<2.0.0",
]

[tool.gaia]
namespace = "github"
type = "knowledge-package"
uuid = "22222222-2222-2222-2222-222222222222"
```

`src/paper_b/__init__.py`：

```python
from gaia.engine.lang import claim
from gaia.engine.lang.compat import fills
from paper_a import missing_lemma

bridge_result = claim("A result that establishes the missing lemma.")

fills(
    source=bridge_result,
    target=missing_lemma,
    reason="This result proves the lemma required by package A.",
)

__all__ = ["bridge_result"]
```

编译并检查：

```bash
gaia build compile .
gaia build check .
```

预期结果：

- `exports.json` 包含 `bridge_result`
- `bridges.json` 包含一条 `fills` 关系，指向：
  - A 的 `target_qid`
  - A 的 `target_interface_hash`
  - 解析出的依赖版本

## 步骤 3：注册到 registry

先注册 A，再注册 B：

```bash
gaia pkg register /path/to/paper-a
gaia pkg register /path/to/paper-b
```

顺序不能反——因为 B 的 bridge manifest 记录了 A 的 `target_resolved_version`，registry 验证时需要 A 已存在。

## 重要约束

`fills(target=...)` 是**对依赖包已编译 manifest 的验证**：

1. A 必须先编译
2. B 必须解析到 Gaia 验证的同一个包
3. 目标 claim 必须出现在 A 的 `premises.json` 中
4. 其 role 必须是 `local_hole`

如果 A 的当前 release 不再暴露该 premise 为 hole，B 的编译会失败。

## 结果

成功后在 registry 中可以看到：

注册 A 后：

- `packages/paper-a/releases/1.0.0/premises.json`
- `packages/paper-a/releases/1.0.0/holes.json`

注册 B 后：

- `packages/paper-b/releases/1.0.0/bridges.json`

Index build 后：

- `index/premises/by-qid/...`
- `index/holes/by-qid/...`
- `index/bridges/by-target-qid/...`
- `index/bridges/by-target-interface/...`

## 常见问题

**Q: B 编译时报错 "target claim not found in premises"**

A 必须先编译。B 的 `fills` 验证的是 A 已编译的 manifest interface，不是源码 import。

**Q: A 更新后 B 的 bridge 失效了**

如果 A 的新版本不再暴露该 premise 为 `local_hole`，B 的编译会失败。这是设计如此——stable contract 是特定 release 中的特定 `qid` + `interface_hash` + `local_hole` role，不是 "这个符号永远是个 hole"。

**Q: 源码里 `from paper_a import missing_lemma` 够不够？**

不够。Gaia 不信任 Python import 本身——编译时会重新验证 target 是否匹配 A 的 manifest interface。Import 只是让你在源码里拿到引用，真正的合约是编译产物。
