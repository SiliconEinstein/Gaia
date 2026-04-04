# M6c — Graph Health: Conflict Detection + Structural Audit

> **Status:** Placeholder
> **Date:** 2026-04-04
> **依赖:** M6 (Semantic Discovery) + M7 (Global BP, for conflict detection)

## 概述

M6c 负责 global FactorGraph 的健康检查，包含两个独立的子任务：

1. **Conflict Detection** — 从 BP 推理结果中发现矛盾信号
2. **Structural Audit** — 检查图的结构完整性

从原 `2026-03-31-m6-curation.md` 拆出，M6 只保留 embedding + clustering，M6b 做关系分析，M6c 做图健康检查。

---

## 1. Conflict Detection

**依赖：** M7 Global BP（需要 BP 运行后的诊断数据）

**BP 诊断信号：**
- 振荡（`direction_changes` 高）→ variable 从图的不同部分接收矛盾证据
- 高残差（`max_residual` 大）→ BP 未收敛，可能存在结构冲突
- 语义矛盾：M6b 已经标记的 contradiction + BP 信念值一高一低的 pair

**输出：**
```python
@dataclass
class ConflictReport:
    oscillating_variables: list[dict]    # gcn_id + direction_changes
    high_residual_variables: list[dict]  # gcn_id + residual value
    semantic_conflicts: list[dict]       # 高相似 + prior 差异大
```

## 2. Structural Audit

**无额外依赖，可随时运行。**

**检查项：**
- **孤立 variable**：无任何 factor 连接的 gcn_id（Neo4j 查询）
- **悬空 factor**：premise 或 conclusion 指向不存在 variable 的 gfac_id
- **未解析跨包引用**：integrate 时 pending 的 cross-ref
- **参数缺失**：有 factor 但无对应 FactorParamRecord
- **Prior 缺失**：public variable 无 PriorRecord

**输出：**
```python
@dataclass
class AuditReport:
    orphan_variables: list[str]
    dangling_factors: list[str]
    unresolved_cross_refs: list[dict]
    missing_params: list[str]
    missing_priors: list[str]
    summary: dict[str, int]
```

---

## 实现文件结构

```
gaia/lkm/core/
    conflict_detection.py     # BP 诊断信号分析
    structural_audit.py       # 图结构完整性检查
```

---

## 备注

详细实现 spec 将在 M7 (Global BP) 完成后补充。Structural Audit 可以提前实现（不依赖 BP），Conflict Detection 必须等 M7。
