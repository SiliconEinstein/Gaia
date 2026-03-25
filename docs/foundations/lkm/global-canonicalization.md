# Global Canonicalization

> **Status:** Current canonical

Global canonicalization 将 local canonical node（包作用域）映射到 global canonical node（跨包）。这使得全局知识图谱能够识别不同包中语义等价的命题指向同一 claim。

关于规范化身份模型（raw、local canonical、global canonical），参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)。

## 规范化的作用

当一个新包被摄入时，它的每个本地节点要么：

- **match_existing**：绑定到表达相同命题的现有 GlobalCanonicalNode。
- **create_new**：为此前未见的命题创建新的 GlobalCanonicalNode。

节点规范化之后，本地 factor 被提升到全局图，通过将 local canonical ID 替换为 global canonical ID 实现，包括解析 `ext:` 跨包引用。

## Pipeline

参见 `libs/global_graph/canonicalize.py:canonicalize_package()`。

```
Input:
  LocalCanonicalGraph  (from gaia build)
  LocalParameterization
  GlobalGraph  (current global state)

Steps:
  1. Filter to canonicalizable types (default: claims only)
  2. For each local node, find best match in global graph
  3. If match >= threshold -> bind to existing global node
  4. If no match -> create new global node
  5. Lift local factors to global IDs (resolve lcn_ and ext: references)

Output:
  CanonicalizationResult:
    bindings: list[CanonicalBinding]
    new_global_nodes: list[GlobalCanonicalNode]
    matched_global_nodes: list[str]
    global_factors: list[FactorNode]
    unresolved_cross_refs: list[str]
```

## 匹配策略

参见 `libs/global_graph/similarity.py:find_best_match()`。

### Embedding 相似度（主要方法）

当提供 EmbeddingModel 时，引擎：
1. 批量 embed 查询内容和所有候选内容。
2. 计算查询 embedding 与每个候选之间的 cosine similarity。
3. 返回超过阈值的最佳匹配。

### TF-IDF 回退

当没有可用的 embedding 模型时，引擎使用 scikit-learn 的 `TfidfVectorizer` 计算两两 cosine similarity。这种方法较慢且精度较低，但不需要外部 API。

### 匹配阈值

默认阈值为 `0.90`（见 `canonicalize.py:MATCH_THRESHOLD`）。匹配必须超过此阈值才会被接受。

## 过滤规则

在相似度计算之前，候选项会被过滤：

- **类型匹配必需**：只有 `knowledge_type` 相同的候选项才有资格。
- **某些类型需要 kind 匹配**：`question` 和 `action` 类型还需要 `kind` 匹配。
- **关系类型排除**：`contradiction` 和 `equivalence` 是包内关系，永远不会跨包匹配。

## 仅 Claim 默认策略

默认情况下，只有 `claim` 节点会被规范化。这可以通过 `canonicalizable_types` 参数配置（通常在 `pipeline.toml` 中设置）。

理由是：claim 是具有真值的命题，参与 BP 并从跨包身份中获益。Setting 定义上下文；question 构建探究框架；action 描述流程——这些通常是包特定的。

## Factor 提升

节点规范化之后，本地 factor 被改写为全局 ID：

1. 从 binding 构建 `lcn_ -> gcn_` 映射。
2. 从全局节点元数据（`source_knowledge_names`）构建 `ext: -> gcn_` 映射。
3. 对每个本地 factor，解析所有 premise、context 和 conclusion ID。
4. 含有未解析引用的 factor 被丢弃（记录在 `unresolved_cross_refs` 中）。

关于 factor node schema，参见 [../graph-ir/graph-ir.md](../graph-ir/graph-ir.md)。

## 代码路径

| 组件 | 文件 |
|------|------|
| 规范化入口 | `libs/global_graph/canonicalize.py:canonicalize_package()` |
| 相似度匹配 | `libs/global_graph/similarity.py:find_best_match()` |
| Global node 模型 | `libs/storage/models.py:GlobalCanonicalNode` |
| Canonical binding 模型 | `libs/storage/models.py:CanonicalBinding` |
| Pipeline 集成 | `scripts/pipeline/canonicalize_global.py` |

## 当前状态

规范化引擎在仅 claim 默认模式下可用，支持 embedding 和 TF-IDF 相似度。Factor 提升可解析本地和跨包引用。该引擎由服务端摄入 pipeline 调用，并在 `tests/libs/global_graph/` 中有测试覆盖。

## 目标状态

规范化引擎已稳定。潜在的小改进包括：当多个本地节点合并为一个全局节点时更智能地选择代表性内容，以及缓存 embedding 以避免重复计算。
