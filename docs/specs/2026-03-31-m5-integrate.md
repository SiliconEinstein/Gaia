# M5 — Integrate Spec

> **Status:** Draft
> **Date:** 2026-03-31
> **实现文件:** `gaia_lkm/core/integrate.py`

## 概述

M5 将 local FactorGraph 集成到 global FactorGraph。同步操作，per-package。包含确定性去重（content_hash 精确匹配）和 CanonicalBinding 写入。

M5 依赖 M1（数据模型）+ M2（存储层）+ M3 或 M4（pipeline 产出的 local FactorGraph）。

## 上游参考

- `docs/foundations/lkm/03-lifecycle.md §Integrate`：integrate 流程设计
- `Gaia/docs/foundations/gaia-ir/05-canonicalization.md §2-6`：匹配策略、factor lifting 规则
- `Gaia/docs/foundations/gaia-ir/03-identity-and-hashing.md §3`：content_hash 用途边界

---

## 输入

```python
@dataclass
class IntegrateInput:
    local_variables: list[LocalVariableNode]
    local_factors: list[LocalFactorNode]
    prior_records: list[PriorRecord]       # variable_id 暂为 local QID
    factor_param_records: list[FactorParamRecord]
    param_sources: list[ParameterizationSource]
    package_id: str
    version: str
```

## 输出

```python
@dataclass
class IntegrateOutput:
    bindings: list[CanonicalBinding]           # 所有 local→global 映射
    new_global_variables: list[GlobalVariableNode]  # 本次新建的
    new_global_factors: list[GlobalFactorNode]      # 本次新建的
    updated_global_variables: list[str]             # 本次更新 local_members 的 gcn_ids
    prior_records: list[PriorRecord]                # variable_id 已替换为 gcn_id
    factor_param_records: list[FactorParamRecord]   # factor_id 已替换为 gfac_id
    unresolved_cross_refs: list[dict]               # 无法解析的跨包引用
```

---

## Variable Integrate

对每个 local variable node，按 visibility 分路处理。

### Public Variable（content_hash dedup）

```
for each local_var where visibility == "public":
    1. 查 global_variable_nodes WHERE content_hash = local_var.content_hash
       （走索引，O(1)）
    2. if 命中 existing_gcn:
         - 写 CanonicalBinding(decision="match_existing", binding_type="variable")
         - 将 LocalCanonicalRef 追加到 existing_gcn.local_members
         - 记录 qid_to_gcn[local_var.id] = existing_gcn.id
    3. if 未命中:
         - new_gcn = GlobalVariableNode(id=new_gcn_id(), ...)
         - 写 CanonicalBinding(decision="create_new", binding_type="variable")
         - 记录 qid_to_gcn[local_var.id] = new_gcn.id
```

### Private Variable（直接分配）

```
for each local_var where visibility == "private":
    - new_gcn = GlobalVariableNode(id=new_gcn_id(), visibility="private", ...)
    - 写 CanonicalBinding(decision="create_new", binding_type="variable")
    - 不走 content_hash 查找
    - 记录 qid_to_gcn[local_var.id] = new_gcn.id
```

---

## Factor Integrate

Variable integrate 完成后，用 `qid_to_gcn` 映射将 factor 的 local QIDs 映射为 gcn_ids。

### 跨包引用解析

Factor 的 premises/conclusion 中出现非本包的 QID 时：

1. 查 `canonical_bindings WHERE local_id = cross_pkg_qid`
2. 或查 `global_variable_nodes` 按 content/id 查找
3. **命中** → 使用对应 gcn_id
4. **未命中** → 该 factor 被丢弃，记入 `unresolved_cross_refs`

### 精确结构匹配

```
for each local_factor:
    1. 用 qid_to_gcn 将 premises/conclusion 映射为 gcn_ids
       （如有未解析的引用 → 丢弃该 factor）
    2. 查 global_factor_nodes WHERE
         premises = mapped_premises AND
         conclusion = mapped_conclusion AND
         factor_type = local_factor.factor_type AND
         subtype = local_factor.subtype
    3. if 命中 existing_gfac:
         - 写 CanonicalBinding(decision="match_existing", binding_type="factor")
         - 追加 FactorParamRecord（不同来源对同一推理的参数评估）
    4. if 未命中:
         - new_gfac = GlobalFactorNode(id="gfac_{hash[:16]}", ...)
         - 写 CanonicalBinding(decision="create_new", binding_type="factor")
```

**注意**：`factor_type` 或 `subtype` 不同视为独立 factor，不做匹配。

---

## 参数记录 ID 替换

Pipeline 产出的参数记录中，`variable_id`/`factor_id` 是 local ID。Integrate 时替换为 global ID：

- `PriorRecord.variable_id`: QID → gcn_id（通过 qid_to_gcn 映射）
- `FactorParamRecord.factor_id`: lfac_id → gfac_id（通过 factor binding 映射）

---

## 写入存储

按 M2 storage 的写入协议（`preparing` → 全量写入 → `merged`）执行：

1. 写 local_variable_nodes + local_factor_nodes（LanceDB batch add）
2. 写 canonical_bindings（LanceDB batch add）
3. 写/更新 global_variable_nodes + global_factor_nodes
4. 写 prior_records + factor_param_records + param_sources
5. 写 graph store（Neo4j/Kuzu，可选）

全部成功后标记 `merged`。任何步骤失败保持 `preparing`。

---

## 关键约束

1. **content_hash 查找必须走索引**：O(1)，不允许全表扫描
2. **批量写入**：所有 DB 写操作使用 `table.add(rows)` 批量，不在循环里逐条写
3. **CanonicalBinding 不可变**：写入后不修改
4. **Private variable 不走 dedup**：直接分配新 gcn_id
5. **factor_type/subtype 不同 = 独立 factor**：不做跨类型匹配
6. **未解析引用不阻塞**：记入 unresolved_cross_refs，不中断 integrate

---

## 测试要求

### 单元测试

- `test_variable_dedup_exact_match`：content_hash 匹配时正确绑定
- `test_variable_create_new`：无匹配时正确创建新 global variable
- `test_private_variable_no_dedup`：private variable 直接分配新 ID
- `test_factor_dedup_exact_match`：结构完全匹配时复用已有 global factor
- `test_factor_create_new`：无匹配时创建新 global factor
- `test_cross_package_ref_resolved`：跨包 QID 正确解析
- `test_cross_package_ref_unresolved`：未解析引用正确记入 unresolved_cross_refs
- `test_param_id_replacement`：参数记录 ID 正确替换为 global ID

### 集成测试（真实 LanceDB，tmp_path）

- `test_integrate_full_package`：完整 package 的 integrate 流程
- `test_integrate_second_package_dedup`：第二个包的重复 variable 正确去重
- `test_integrate_idempotent`：同一包重复 integrate 不产生重复记录

放在 `tests/unit/test_integrate.py` 和 `tests/integration/test_integrate.py`。

---

## 实现文件结构

```
gaia_lkm/core/
    __init__.py
    integrate.py         # integrate_package() 主函数
    _variable_dedup.py   # content_hash dedup 逻辑
    _factor_dedup.py     # 精确结构匹配逻辑
    _cross_ref.py        # 跨包引用解析
```
