# Graph IR 编译器

> **Status:** Current canonical

本文档描述驱动 `gaia build` 的 Graph IR 编译管线。Graph IR 模式定义参见 [../graph-ir/overview.md](../graph-ir/overview.md)。

## 概览

编译器是一条确定性管线，将 Typst 源码转换为 Graph IR。它产生因子图中间表示，不涉及 LLM 调用、搜索或概率分配。

```
Typst source  ->  Typst loading  ->  Raw graph  ->  Local canonical graph  ->  Local parameterization
```

每一步添加一个标识层。原始图保留精确的源码可追溯性。局部规范图允许包内合并。局部参数化分配默认概率值。

## 步骤一：Typst 加载

参见 `libs/lang/typst_loader.py`。

Typst 加载器运行 `typst query` 从编译后的 Typst 文档中提取 `gaia-node` figure：

```bash
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-node")'
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-ext")'
```

这会产生一个包含 `nodes`、`factors`、`constraints`、`package` 和 `version` 的字典。

## 步骤二：原始图编译

参见 `libs/graph_ir/typst_compiler.py:compile_v4_to_raw_graph()`。

编译器将加载器输出处理为 `RawGraph`：

1. **知识节点**：每个非外部节点成为一个 `RawKnowledgeNode`。v4 类型映射解析 `setting`、`question`、`claim`、`action`。关系节点（`contradiction`、`equivalence`）从约束映射获取其类型。

2. **外部节点**：来自 `gaia-bibliography` 的节点成为带有 `ext:package/node` ID 的 `RawKnowledgeNode`，保留跨包引用。

3. **推理因子**：每个 `from:` 参数生成一个类型为 `infer` 的 `FactorNode`，将前提节点链接到结论。

4. **约束因子**：带有 `between:` 的 `#relation` 声明生成 `contradiction` 或 `equivalence` 因子。

因子类型定义参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)。

## 步骤三：局部规范化

参见 `libs/graph_ir/build_utils.py:build_singleton_local_graph()`。

目前实现单例规范化：每个原始节点精确映射到一个 `LocalCanonicalNode`，不进行合并。原始到局部的映射记录在 `CanonicalizationLogEntry` 中以便审计。

规范化标识模型参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)。

## 步骤四：局部参数化

参见 `libs/graph_ir/build_utils.py:derive_local_parameterization_from_raw()`。

为本地 BP 导出概率覆盖层：

- **节点先验**：如果存在显式元数据则使用，否则按类型取默认值（`setting` = 1.0，其他 = 0.5）。
- **因子参数**：`infer`、`abstraction` 和 `reasoning` 因子默认 `conditional_probability = 1.0`。

参数化通过 `graph_hash` 绑定到特定图。

参数化模型参见 [../graph-ir/parameterization.md](../graph-ir/parameterization.md)。

## 节点标识

三种 ID 方案，均为确定性生成：

| ID 类型 | 格式 | 生成方式 |
|---------|--------|------------|
| `raw_node_id` | `raw_{sha256[:16]}` | SHA-256 of `(package, version, module, name, type, kind, content, parameters)` |
| `local_canonical_id` | `lcn_{sha256[:16]}` | SHA-256 of the raw_node_id |
| `factor_id` | `f_{sha256[:16]}` | SHA-256 of `(kind, module, name[, suffix])` |

外部节点使用 `ext:{package}/{node}` 格式而非基于哈希的 ID。

全局规范 ID（`gcn_`）参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)。

## 代码路径

| 组件 | 文件 |
|-----------|------|
| Typst 加载器 | `libs/lang/typst_loader.py` |
| 原始图编译器 | `libs/graph_ir/typst_compiler.py` |
| 局部规范化 | `libs/graph_ir/build_utils.py` |
| Graph IR 模型 | `libs/graph_ir/models.py` |
| CLI 集成 | `libs/pipeline.py:pipeline_build()` |

## 当前状态

编译器支持 v3 和 v4 Typst 包。完整管线（加载、编译、规范化、参数化）由 `gaia build` 和 `gaia infer` CLI 命令以及服务器摄入管线驱动。测试覆盖位于 `tests/libs/graph_ir/`。

## 目标状态

Graph IR 编译器已趋于稳定，无重大变更计划。单例局部规范化未来可能支持包内语义合并，但这不是优先事项。
