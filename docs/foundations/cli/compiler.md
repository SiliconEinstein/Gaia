# Gaia IR 编译器

> **Status:** Current canonical for Gaia Lang v5 Phase 1
>
> **Canonical spec:** [../../specs/2026-04-02-gaia-lang-v5-python-dsl-design.md](../../specs/2026-04-02-gaia-lang-v5-python-dsl-design.md)

本文档描述当前 `gaia compile` 的工作方式。当前编译器面向 Python DSL package，而不是旧的 Typst `gaia build` 管线。

## 概览

`gaia compile` 是一条确定性编译路径：

```text
Python package source
  -> load package metadata
  -> execute Gaia DSL declarations
  -> collect runtime objects
  -> build LocalCanonicalGraph
  -> write .gaia/ir.json + .gaia/ir_hash
```

编译器只产出结构，不做本地推理、数据库写入或 registry 注册。

## 步骤一：加载包元数据

编译器读取 `pyproject.toml`，获取：

- `project.name`
- `project.version`
- `[tool.gaia].namespace`
- `[tool.gaia].uuid`

然后解析 Python import package，当前支持两种布局：

- `<repo>/<import_name>/`
- `<repo>/src/<import_name>/`

## 步骤二：执行 DSL 声明

编译器导入包模块并执行模块顶层 DSL 声明。

执行期间会注册：

- `Knowledge`
- `Strategy`
- `Operator`

这些运行时对象由内部 collector 收集，作为后续 lowering 的输入。作者不需要也不能显式声明 `Package(...)`。

## 步骤三：构建 graph closure

编译器会递归遍历：

- 包内显式声明的知识对象
- strategy 的前提、背景、结论
- nested `sub_strategies`
- strategy 内嵌 `formal_expr` 使用到的 helper operator / knowledge
- operator 的变量与辅助结论
- 外部引用形成的必要 closure

目标不是保留“执行痕迹”，而是产出一个自洽、可验证、可复编译的 package-local graph。

## 步骤四：降低到 Gaia IR

输出对齐现有 `gaia.ir.LocalCanonicalGraph`：

- 顶层字段采用 `namespace` / `package_name` / `knowledges`
- `steps` 使用当前 `Step` schema
- `formal_expr` 使用当前 `FormalExpr` schema
- `ir_hash` 使用 `sha256:` 前缀

编译器还负责：

- 对 named strategies 调用 `gaia.ir.formalize`，生成 canonical `formal_expr`
- 保证 QID 形状合法
- 为 foreign knowledge 生成可验证的引用
- 将最终结构序列化到 `.gaia/ir.json`

当前 `.gaia/ir.json` 是纯 `LocalCanonicalGraph` dump，不再混入 Lang 专用的顶层 `package` 或 per-knowledge `is_input` 字段。

## 步骤五：图哈希

`.gaia/ir_hash` 是对最终 IR JSON 的确定性内容哈希。

它的作用是：

- 给 `gaia check` 提供一致性边界
- 给 `gaia register` 提供注册时的内容身份
- 让 registry CI 可以重新编译并比对产物

## 代码路径

| 组件 | 文件 |
|------|------|
| 编译命令 | `gaia/cli/commands/compile.py` |
| 包加载辅助 | `gaia/cli/_packages.py` |
| 编译器 | `gaia/lang/compiler/compile.py` |
| 运行时对象 | `gaia/lang/runtime/` |
| IR schema | `gaia/ir/` |

## Historical Note

旧的 Typst loader、`gaia build`、raw graph、local parameterization 等内容仍保留在仓库中，主要作为早期实验和背景材料。它们不是当前 Gaia Lang v5 Phase 1 编译器的 canonical contract。
