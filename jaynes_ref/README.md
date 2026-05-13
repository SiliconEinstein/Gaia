# jaynes_ref — 严格 Jaynes 概率推断参考实现

本目录实现 E. T. Jaynes《Probability Theory: The Logic of Science》(PTLoS)
的命题逻辑子集的**精确推断**,不使用 Belief Propagation 或任何近似算法。
所有结果由 2^n 状态枚举直接给出,用于作为 `gaia.bp` 的 golden reference。

## 1. 五类信息(Jaynes information class taxonomy)

| 类别 | 含义 | 数据字段 | PTLoS 对应 |
|---|---|---|---|
| I  | 逻辑必然(δ 断言、硬观测)            | `hard_evidence`  | §2.1 desiderata 命题 |
| II | 似然(soft evidence, LR form)        | `likelihoods`    | §4.1 Bayes 规则 |
| III| 条件概率表(CPT)                     | `cpts`           | §4.3 multiplication rule |
| IV | 软先验(class-IV unary, Cromwell ε) | `unary_priors`   | §11.4 continuous-parameter prior |
| V  | MaxEnt 自由                          | 变量在 `variables` 但其他字段均无记录 | §11.1 insufficient reason |

## 2. 五条 desiderata(D1–D5)

- **D1** 唯一信息源:同一变量的信念不能由多条独立通道同时指定
- **D2** 信息独立性:逻辑等价命题不能在 I 中重复编码
- **D3** 不替作者填默认信息:未声明的命题保持 class V 自由,不被 0.5 unary 硬写
- **D4** 逻辑断言用 δ:I 类信息势函数严格 {0, 1},不软化
- **D5** Z 不静默:配分函数为零 → raise,不接受无意义的归一

守卫实现在 `desiderata.py` + `information.py` + `dedup.py`。

## 3. 核心推断流程

```
InformationSet → enumerate 2^n → log w(x) 累加 → Z = Σ exp(log w) → P(x) = w/Z → marginals
```

## 4. 目录结构

```
jaynes_ref/
├── __init__.py             导出核心 API
├── information.py          InformationSet + 结构校验(D1)
├── constraints.py          LogicalConstraint + CPT + Likelihood + 7 个 factory
├── exact.py                精确枚举推断(Z=0 raise,D5)
├── desiderata.py           D1–D5 完整守卫 + Cromwell clamp
├── dedup.py                D2 L1 结构去重(canonical key)
├── adapter.py              LocalCanonicalGraph → InformationSet
├── queries.py              MAP / entropy / KL / 边际 / 互信息(natural log)
├── maxent.py               Newton 法求 Lagrange 乘子 + inject_marginal_priors
├── ap_distribution.py      A_p 元分布(PTLoS Ch.18)
├── decision.py             Bayes 最优决策 + 0-1/quadratic/asymmetric loss
└── tests/                  单元测试(109 passing)
```

## 5. 信息流(Layer 0 完整闭环)

```
原始信息       → InformationSet
                      ↓
              MaxEnt(矩约束)
                      ↓        ← inject_marginal_priors 写回 class IV
              A_p 元先验
                      ↓        ← predictive_probability 写入 class IV
              精确推断(exact.infer)
                      ↓
              查询(MAP / 边际 / 互信息 / KL)
                      ↓
              Bayes 决策(bayes_action + loss)
```

## 6. 与 gaia.bp 的关系

- `jaynes_ref` 不依赖 `gaia.ir` 或 `gaia.bp` 内部(只通过 adapter 读 IR)
- 通过 `adapter.from_local_graph` 接受 `LocalCanonicalGraph` 输入,用于交叉验证
- 不以性能为目标,n>20 请继续用 BP
- `tests/test_cross_bp.py` 已发现一例 V10 候选:BP 对 `metadata['prior'] ∈ {0, 1}` 经 Cromwell 衰减泄漏

## 7. 测试统计

| 套件 | tests |
|---|---|
| test_information     | 13 |
| test_constraints     | 15 |
| test_exact           | 12 |
| test_desiderata      |  9 |
| test_dedup           |  8 |
| test_adapter         |  8 |
| test_cross_bp        |  5 |
| test_queries         | 13 |
| test_maxent          |  9 |
| test_ap_distribution |  9 |
| test_decision        |  8 |
| **合计**             | **109** |
