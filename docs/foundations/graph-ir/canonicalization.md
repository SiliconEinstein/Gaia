# 规范化

> **Status:** Current canonical

规范化是跨 Graph IR 三个身份层映射 knowledge 节点的过程：从 raw 节点到 local canonical 节点（包内），以及从 local canonical 节点到 global canonical 节点（跨包）。

## Local 规范化

**范围**：单个包，在 `gaia build` 期间执行。

Local 规范化在包范围内将 raw 节点划分为语义等价组。每个 raw 节点恰好映射到一个 local canonical 节点。

### 自动单例模式

默认的 `gaia build` 创建一个简单的规范化映射，其中每个 raw 节点成为其自身的 local canonical 节点（1:1 映射）。这是一个有效的规范化——单例映射始终是可接受的。

### Agent 辅助聚类

一个可选的 agent skill 可以检查 raw graph 并对语义相似的节点进行聚类。例如，两个措辞略有不同但含义相同的 raw 节点可以合并为一个 local canonical 节点。Agent 产生：

- 合并后的 `local_canonical_graph.json`
- 记录哪些 raw 节点被合并及原因的 `canonicalization_log.json`

### 规范化日志

```
CanonicalizationLog:
    entries: list[CanonicalizationEntry]

CanonicalizationEntry:
    raw_node_ids:          list[str]    # raw nodes in this group
    local_canonical_id:    str          # assigned local canonical ID
    merge_reason:          str | None   # why these were merged (agent explanation)
```

日志提供可审计性：审查者可以检查节点被合并的原因，并对不正确的分组提出质疑。

## Global 规范化

**范围**：跨包，在 LKM 审查/集成期间执行。

Global 规范化将 local canonical 节点映射到 global canonical 节点。当新包被摄入时，其每个 local 节点要么：

- **match_existing**：绑定到表达相同命题的现有 `GlobalCanonicalNode`。
- **create_new**：为这个前所未见的命题创建新的 `GlobalCanonicalNode`。

这使得全局知识图谱能够识别来自不同包的语义等价命题指向同一知识。

### 匹配策略

相似度引擎支持两种模式：

**Embedding 相似度（主要）**：批量嵌入查询和候选内容，计算余弦相似度，返回超过阈值的最佳匹配。

**TF-IDF 回退**：当没有 embedding 模型可用时，使用 scikit-learn 的 `TfidfVectorizer` 进行成对余弦相似度计算。较慢且精度较低，但无需外部 API。

默认匹配阈值为 `0.90`。匹配必须超过此阈值才能被接受。

### 过滤规则

在相似度计算之前，会先过滤候选者：

- **要求类型匹配**：仅具有相同 `knowledge_type` 的候选者才有资格。
- **某些类型要求 kind 匹配**：`question` 和 `action` 类型还额外要求匹配 `kind`。
- **排除 relation 类型**：`contradiction` 和 `equivalence` 是包内 relation，永远不会跨包匹配。

### 仅 claim 默认规则

默认情况下，仅 `claim` 节点参与规范化。Setting、question 和 action 保持包内局部，除非通过 `canonicalizable_types` 配置显式包含。理由：claim 是参与 BP 的真值可判命题，能从跨包身份统一中受益。

### Factor 提升

节点规范化完成后，local factor 使用全局 ID 进行重写：

1. 从绑定中构建 `lcn_ -> gcn_` 映射。
2. 从全局节点元数据（`source_knowledge_names`）构建 `ext: -> gcn_` 映射。
3. 对每个 local factor，解析所有 premise、context 和 conclusion ID。
4. 含未解析引用的 factor 被丢弃（记录在 `unresolved_cross_refs` 中）。

服务器端实现细节见 `../lkm/global-canonicalization.md`。

## 源代码

- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
