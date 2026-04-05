# v6 Phase 3: Gaia Package 结构 — 任意 Python 包 + gaia/ = Gaia Package

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | Gaia package 集成模式 |
| 前置 | Phase 1（Support 继承树）、Phase 2（Runnable） |
| 非目标 | execution cache、`gaia run` artifact protocol |

---

## 1. 目标

让任意已有的 Python 包，只需要加一个 `gaia/` 目录，就能变成 Gaia package：

```
existing_python_package/
  solver.py
  model.py
  tests/
  gaia/               ← 加这个目录
    __init__.py
    claims.py
    supports.py
    bridges.py
```

原有代码不需要改动。Gaia 层只是一个薄适配层。

---

## 2. gaia/ 目录结构

### 2.1 三类适配器

| 文件 | 内容 | 职责 |
|------|------|------|
| `claims.py` | Claim 适配器 | 将包内的概念对象转为 Claim |
| `supports.py` | Support 构造器 | 将包内的函数包装为 Gaia 构造器 |
| `bridges.py` | Bridge 构造器 | 将 execution result 连接到科学结论 |
| `review.py`（可选） | Review sidecar | 包级别的 review 声明 |

### 2.2 claims.py — 将概念转为 Claim

```python
from gaia.lang import claim, setting
from mypackage.model import DEFAULT_MODEL

model_spec = claim(
    "该包使用文档中定义的不可压 NS 模型",
)

mesh_quality = claim(
    "网格通过了质量检查（最小角 > 20°）",
)

cfl_assumption = setting(
    "CFL 数 < 0.5",
)
```

适用于模型定义、数据集描述、网格信息、数值格式假设等概念性对象。

### 2.3 supports.py — 将函数包装为 Gaia 构造器

```python
from gaia.lang import execute, check
from mypackage.solver import run_cfd
from mypackage.tests import run_regression_tests

def pressure_field(*, geometry, bc, solver_validated):
    return execute(
        run_cfd,
        given=[geometry, bc, solver_validated],
        returns="CFD 计算得到压力场 P",
    )

def solver_ok(*, spec, suite_covers_target):
    return check(
        run_regression_tests,
        given=[spec, suite_covers_target],
        returns="求解器在回归测试集上通过了所有精度检查",
    )
```

包装函数返回 Claim，保持 Claim in, Claim out。

### 2.4 bridges.py — 连接到科学结论

```python
from gaia.lang import claim, deduction

match_criterion = claim(
    "压力场与参考解 L2 误差 < 1% 即视为吻合",
)

def target_hypothesis_supported(*, pressure, solver_ok):
    return deduction(
        "模拟结果支持目标假设",
        given=[pressure, solver_ok, match_criterion],
    )
```

Bridge 层是必须的——防止 `execute()` / `check()` 的结果被直接当成科学结论。

---

## 3. Discovery 机制

### 3.1 Convention-based（Phase 3 默认）

CLI 扫描 `<pkg>/gaia/__init__.py`：

```bash
gaia compile mypackage/
```

发现逻辑：
1. 找到 `mypackage/gaia/__init__.py`
2. 导入，收集 Claims 和 Supports
3. 编译为 Gaia IR

无需额外配置。

### 3.2 Entry-point（后续扩展）

用于第三方包或 sidecar 包：

```toml
# mypackage_gaia/pyproject.toml
[project.entry-points."gaia.layers"]
mypackage = "mypackage_gaia:register"
```

Phase 3 不强制要求此机制。

---

## 4. 三种集成模式

### 4.1 In-package（推荐）

你控制源码，直接在包内加 `gaia/`：

```
mypackage/
  solver.py
  gaia/
    claims.py
    supports.py
    bridges.py
```

### 4.2 Sidecar package

原包不动，另建一个 Gaia 适配包：

```
mypackage/            # 第三方，不修改
mypackage_gaia/       # 你的 Gaia 层
  claims.py
  supports.py
```

### 4.3 Workspace bridge

多个包联合：

```
workspace/
  pkg_a/
  pkg_b/
  pkg_ab_gaia/        # 联合 Gaia 层
```

---

## 5. 已有 v5 packages 的迁移

### 5.1 纯 formal/infer 的 v5 package

不需要结构变更。v5 语法在 Phase 1 的双入口下继续可用。可选择用 `gaia migrate v5-to-v6` 转为 v6 语法。

### 5.2 想加 Runnable 的 v5 package

1. 加 `gaia/` 子目录
2. 原 v5 模块保持不变
3. 在 `gaia/supports.py` 中添加 `execute()` / `check()` / `formal_proof()` 包装
4. 在 `gaia/bridges.py` 中添加 bridge 逻辑

两层共存——v5 核心 + v6 execution 层。

### 5.3 示例：galileo

```
# 迁移前（v5）
galileo/
  __init__.py       # claim(), deduction() 调用
  review.py

# 迁移后（v6，可选）
galileo/
  __init__.py       # deduction("C", given=[...]) 调用
  review.py         # review_support() 调用
```

纯语法变更，无结构重组。

---

## 6. API 风格规则

### 6.1 构造器返回 Claim

Gaia 层的所有包装函数返回 `Claim`：

```python
def pressure_field(...) -> Claim: ...
def solver_ok(...) -> Claim: ...
def target_hypothesis_supported(...) -> Claim: ...
```

### 6.2 不做隐式提升

不自动扫描包内函数并推断 Gaia 语义。函数成为 Gaia 层的唯一方式：

- 放在 `gaia/` 目录内
- 或被 Gaia 构造器显式包装

### 6.3 命名建议

| 类型 | 命名风格 | 示例 |
|------|---------|------|
| Claim 适配器 | 名词短语 | `scheme_spec`, `mesh_quality` |
| Runnable 包装 | 结果名词 | `pressure_field()`, `solver_ok()` |
| Bridge 构造器 | 结论短语 | `target_hypothesis_supported()` |

---

## 7. 不在本阶段做的事

- 自动扫描包内函数
- execution cache protocol
- `gaia run` artifact contract
- Runnable 的 IR protected contract
