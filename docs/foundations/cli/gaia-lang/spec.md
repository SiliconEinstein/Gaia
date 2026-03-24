# 语言规范

> **Status:** Current canonical

本文档概述 Gaia Language v4 Typst DSL —— 知识包的创作界面。完整细节参见 `docs/archive/foundations-v2/language/gaia-language-spec.md`。

## 概览

Gaia Language v4 是一种基于 Typst 的 DSL。作者将知识包编写为标准 Typst 文档；编译器通过 `typst query` 提取结构化知识图。该语言提供五个声明函数以及一个跨包参考文献机制。

## 声明

所有声明都会生成带有隐藏元数据的 `figure(kind: "gaia-node")` 元素，从而可以通过单次查询进行提取。

| 函数 | 用途 | 参数 |
|---|---|---|
| `#setting[content]` | 上下文假设 | 仅内容主体 |
| `#question[content]` | 开放性问题 | 仅内容主体 |
| `#claim[content][proof]` | 可判真的断言 | `from:`（前提）、`kind:`（子类型） |
| `#action[content][proof]` | 程序性步骤 | `from:`（前提）、`kind:`（子类型） |
| `#relation[content][proof]` | 结构性约束 | `type:`（"contradiction" 或 "equivalence"）、`between:`（端点） |

可选的第二个内容块 `[proof]` 包含带有 `@ref` 交叉引用的自然语言证明理由。

## 关键参数

**`from:`** —— 一个标签引用元组，声明承载性前提：
```typst
#claim(from: (<setting.vacuum_env>, <obs.measurement>))[conclusion][proof]
```
单元素元组需要尾随逗号：`from: (<label>,)`。

**`between:`** —— `#relation` 上的必需参数，命名两个被约束的节点：
```typst
#relation(type: "contradiction", between: (<claim_a>, <claim_b>))[description]
```

**`kind:`** —— `#claim` 和 `#action` 上的可选科学子类型（如 `"observation"`、`"hypothesis"`、`"python"`）。记录证据类型；不改变 Graph IR 拓扑结构。

## 标签

标签遵循 `<filename.label_name>` 约定：
```typst
#setting[...] <setting.vacuum_env>
#claim[...]   <reasoning.main_conclusion>
```

`filename.` 前缀是为了在模块间保持唯一性的命名约定。文内引用使用 `@label` 语法。

## 跨包引用

外部知识通过 `gaia-deps.yml` 声明并用 `#gaia-bibliography` 注册：

**`gaia-deps.yml`：**
```yaml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
  content: "In a vacuum, objects of different weights fall at the same rate."
```

**用法：**
```typst
#gaia-bibliography(yaml("gaia-deps.yml"))
#claim(from: (<local_derivation>, <vacuum_prediction>))[...][...]
```

`#gaia-bibliography` 创建隐藏的 `figure(kind: "gaia-ext")` 元素，使外部标签可被 Typst 的引用系统和提取管线解析。

## 提取

Graph IR 通过 Typst 的内置查询机制提取：

```bash
# Local nodes
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-node")'

# External references
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-ext")'
```

Python 加载器（`libs/lang/typst_loader.py::load_typst_package_v4`）将查询结果处理为 `{package, version, nodes, factors, constraints, dsl_version: "v4"}`。

## 包布局

支持两种布局：

**Vendored（新包的默认布局，由 `gaia init` 创建）：**
```
my_package/
  typst.toml          # manifest: name, version, entrypoint
  lib.typ             # entrypoint: #import "_gaia/lib.typ": *
  _gaia/              # vendored runtime (copied by gaia init)
    lib.typ
    ...
  motivation.typ      # module file
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

**仓库相对路径（Gaia 仓库内的 fixtures 和开发用途）：**
```
my_package/
  typst.toml          # manifest: name, version, entrypoint
  lib.typ             # entrypoint: #import "/libs/typst/gaia-lang-v4/lib.typ": *
  motivation.typ      # module file
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

推荐独立包使用 vendored 布局。仓库相对路径布局用于 `tests/fixtures/` 和 Gaia 仓库内的开发工作流。

## 运行时库

位于 `libs/typst/gaia-lang-v4/`。导出内容：

| 符号 | 来源 | 用途 |
|---|---|---|
| `setting`, `question`, `claim`, `action`, `relation` | `declarations.typ` | 声明函数 |
| `gaia-bibliography` | `bibliography.typ` | 跨包引用注册 |
| `gaia-style` | `style.typ` | 文档展示规则和视觉样式 |

## 源码

- `libs/typst/gaia-lang-v4/` —— 运行时 Typst 函数定义
- `libs/lang/typst_loader.py` —— Python 提取加载器
- `docs/archive/foundations-v2/language/gaia-language-spec.md` —— 完整规范
- `docs/archive/foundations-v2/language/gaia-language-design.md` —— 设计原理
