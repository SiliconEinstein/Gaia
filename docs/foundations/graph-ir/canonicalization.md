# 规范化

> **Status:** Target design — 基于两层身份体系重新设计

规范化是将 local canonical 节点映射到 global canonical 节点的过程——从包内身份到跨包身份。

## 概述

当新包被发布时，其每个 local canonical 节点要么：

- **match_existing**：绑定到表达相同命题的现有 GlobalCanonicalNode
- **create_new**：为前所未见的命题创建新的 GlobalCanonicalNode

## 参与规范化的节点类型

**所有知识类型都参与全局规范化：** claim、setting、question、template。

理由：

- **claim**：跨包身份统一是 BP 的基础——不同包对同一命题的推理应汇聚到同一节点
- **setting**：不同包可能描述相同的背景（如"密度泛函理论"），统一后可被多个推理引用
- **question**：同一科学问题可能被多个包提出，统一后可关联不同包的回答
- **template**：相同的命题模式（如 `∀x. metal(x) → conducts(x)`）应跨包共享

## 匹配策略

### Embedding 相似度（主要）

批量嵌入查询和候选内容，计算余弦相似度，返回超过阈值的最佳匹配。

### TF-IDF 回退

当没有 embedding 模型可用时，使用 TF-IDF 成对余弦相似度。较慢且精度较低，但无需外部 API。

### 匹配阈值

默认匹配阈值为 `0.90`。匹配必须超过此阈值才能被接受。

### 过滤规则

在相似度计算之前，先过滤候选者：

- **要求类型匹配**：仅相同 `type` 的候选者才有资格（claim 只匹配 claim，template 只匹配 template）
- **Template 额外规则**：除内容相似度外，还需比较自由变量结构（`parameters` 字段）

## Factor 提升

节点规范化完成后，local factor 使用全局 ID 进行重写：

1. 从 CanonicalBinding 构建 `lcn_ → gcn_` 映射
2. 从全局节点元数据构建 `ext: → gcn_` 映射（跨包引用解析）
3. 对每个 local factor，解析所有 premise、context 和 conclusion ID
4. 含未解析引用的 factor 被丢弃（记录在 `unresolved_cross_refs` 中）

## GlobalCanonicalNode 的内容引用

Global 节点**不存储 content**。它通过 `representative_lcn` 引用一个 local canonical 节点来获取内容（见 [knowledge-nodes.md](knowledge-nodes.md) §2）。

当多个 local 节点映射到同一 global 节点时：

1. 选择一个作为 `representative_lcn`（代表性节点）
2. 所有映射的 local 节点记录在 `member_local_nodes` 中
3. 内容读取时从 representative 的 local 节点获取

这避免了跨包的长文本重复存储。代表性节点的选择策略是可演进的实现细节。

## 源代码

- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
- `libs/global_graph/similarity.py` -- `find_best_match()`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
