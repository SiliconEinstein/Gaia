# CLI 生命周期

> **Status:** Current canonical for Gaia Lang v5 Phase 1
>
> **Canonical spec:** [../../specs/2026-04-02-gaia-lang-v5-python-dsl-design.md](../../specs/2026-04-02-gaia-lang-v5-python-dsl-design.md)

Gaia Lang v5 当前作者侧 CLI 很小，只覆盖 source release 的三个阶段：

```text
author source
  -> gaia compile
  -> gaia check
  -> git push + git tag
  -> gaia register
```

## `gaia compile [path]`

输入：

- `pyproject.toml`
- Python package source
- 模块顶层声明的 Knowledge / Strategy / Operator

输出：

- `.gaia/ir.json`
- `.gaia/ir_hash`

做的事：

- 加载包元数据
- 执行 Python DSL 声明
- 计算 knowledge closure
- 产出可由当前 `gaia.ir` schema 接受的 `LocalCanonicalGraph`

不做的事：

- 不推理
- 不上传 GitHub
- 不写 registry metadata

## `gaia check [path]`

输入：

- package source
- `.gaia/ir.json`
- `.gaia/ir_hash`

输出：

- 成功或失败的本地验证结果

做的事：

- 检查 `.gaia` 产物和当前源码是否一致
- 验证 IR schema 和引用合法性
- 验证包级 identity 字段
- 验证注册前提是否满足

不做的事：

- 不创建 tag
- 不提交 registry PR
- 不生成安装产物

## `gaia register [path]`

输入：

- 已通过 `gaia check` 的 package
- pushed GitHub repo
- pushed git tag
- local registry checkout 或可创建 PR 的 GitHub 环境

输出：

- registry metadata 变更
- 可选的 registry PR

做的事：

- 读取 `repo + tag + git_sha + ir_hash + deps`
- 更新 `Package.toml` / `Versions.toml` / `Deps.toml`
- 可选地推送 branch 并创建 registry PR

不做的事：

- 不直接“发布 wheel”
- 不提供 install-by-name
- 不替 registry CI 做最终接受判断

## 当前边界

当前 Gaia Lang v5 Phase 1 CLI 不包含：

- `gaia init`
- `gaia build`
- `gaia infer`
- `gaia publish`
- `gaia publish --local`

这些名字出现在仓库里的旧文档中时，应视为历史设计或旧实验，而不是当前 author-side CLI contract。
