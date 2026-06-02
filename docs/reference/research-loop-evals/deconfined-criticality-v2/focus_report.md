# Research Focus Synthesis

- schema_version: 1
- language: zh

## Focuses

| id | priority | readiness | status | question | coverage | evidence_refs | suggested_queries |
| --- | --- | --- | --- | --- | --- | --- | --- |
| continuous_vs_weak_first_order | high | ready_for_assess | candidate | 二维量子反铁磁中的 Néel-VBS 转变究竟能否实现连续的 deconfined quantum critical point，还是许多数值信号更应解释为弱一阶转变？ | {"missing": ["需要更多原始论文级别的 critical exponent 数值和 finite-size scaling 图表"], "paper_leads": 8, "snippets": 9, "strength": "multiple direct snippets cover both sides of the controversy"} | snippet:snippet_1, snippet:snippet_20, snippet:snippet_23, snippet:snippet_24, snippet:snippet_26, snippet:snippet_27, snippet:snippet_33 |  |
| emergent_symmetry_and_anisotropy | high | ready_for_assess | candidate | emergent SO(5)/O(4)/U(1) 对称性在 DQCP 中是连续临界点的强证据，还是也可能出现在弱一阶或伪临界流中？ | {"missing": ["需要补充 conformal bootstrap 或 anomaly matching 对 emergent symmetry 的约束"], "paper_leads": 5, "snippets": 7, "strength": "contains direct positive and cautionary evidence"} | snippet:snippet_6, snippet:snippet_11, snippet:snippet_16, snippet:snippet_33, snippet:snippet_38, snippet:snippet_39 |  |
| nccp1_duality_field_theory_bridge | high | needs_expand | candidate | NCCP1、easy-plane NCCP1 与 N_f=2 QED3 等 duality/anomaly 结构，能在多大程度上解释或约束 lattice DQCP 的 emergent symmetry 与 universality？ | {"missing": ["需要更多独立 paper leads，避免被单篇 duality review 主导"], "paper_leads": 4, "snippets": 10, "strength": "many snippets from one review-like paper plus several lattice/duality papers"} | snippet:snippet_30, snippet:snippet_31, snippet:snippet_32, snippet:snippet_35, snippet:snippet_36, snippet:snippet_37, snippet:snippet_39 | NCCP1 self-duality anomaly SO(5) deconfined criticality; QED3 easy-plane NCCP1 deconfined critical point bootstrap |
| microscopic_model_dependence | medium | needs_expand | candidate | DQCP 的连续性和 emergent symmetry 是否依赖具体 microscopic lattice model、spin 表示、VBS pattern 或相邻相，而不是一个普适的单一 universality class？ | {"missing": ["需要按模型整理 transition order、symmetry signal 和 critical exponents"], "paper_leads": 9, "snippets": 8, "strength": "broad but shallow coverage across models"} | snippet:snippet_5, snippet:snippet_11, snippet:snippet_21, snippet:snippet_25, snippet:snippet_28 | kagome lattice continuous easy-plane deconfined critical transition; honeycomb JQ model Neel VBS first order deconfined criticality; spin 3/2 Neel VBS transition deconfined criticality |

## Rationales

### continuous_vs_weak_first_order

Landscape 中同时出现了支持 J-Q/SU(N) 模型连续 DQCP 的证据、用 running exponent 和有限尺寸效应诊断弱一阶的证据，以及明确承认热力学极限性质未定的结论。这是 deconfined criticality 领域最核心的评估问题。

### emergent_symmetry_and_anisotropy

检索结果把 emergent symmetry、VBS anisotropy 的危险无关性、Kagome/easy-plane 模型中的高阶对称性信号、以及近似 SO(2) 对称性伴随弱一阶转变的反例放在同一张图里，适合评估对称性信号的诊断力。

### nccp1_duality_field_theory_bridge

Landscape 中集中出现了 NCCP1 自对偶、easy-plane duality、QED3 映射、anomaly 以及 lattice-current model 到 self-dual EP-NCCP1 的精确映射。这是从数值现象走向理论解释的关键 focus。

### microscopic_model_dependence

检索结果横跨 square-lattice J-Q、honeycomb generalized Heisenberg、Kagome、XY four-spin、SU(N)、S=3/2 与 QSL/材料语境，显示模型依赖性可能是理解争议的关键。

## Coverage Gaps

| kind | description | evidence_refs |
| --- | --- | --- |
| retrieval_noise | broad scan 中混入了高能 deconfined phase、SO5 化学自由基、黑洞/全息等与凝聚态 DQCP 不同语境的结果；后续 query 需要保留 deconfined criticality、Néel、VBS、NCCP1 等锚点。 | snippet:snippet_0, snippet:snippet_12, snippet:snippet_13, snippet:snippet_17 |
| missing_theory_constraints | 当前 landscape 对 conformal bootstrap、CFT fixed point existence、critical exponent bounds 等理论约束覆盖不足，这会影响对连续 DQCP 是否存在的判断。 | snippet:snippet_33, snippet:snippet_38, snippet:snippet_39 |
| paper_overlap_bias | NCCP1/duality 相关 snippets 大量来自同一 paper lead，适合做理论桥接 focus，但进入 assessment 前应扩充独立 paper leads。 | paper:867771342743667572, snippet:snippet_30, snippet:snippet_35, snippet:snippet_38 |

## Notes

- 这次 focus synthesis 没有使用 aspirin 专用术语，核心聚类来自 deconfined criticality 自身的理论/数值争议。
- 第一轮 broad scan 的 lexical 策略成功避免了完全超时，但引入了 retrieval noise；后续 expand 应更精确地锚定 Néel-VBS、NCCP1、DQCP。
- 优先 assessment focus 建议选择 continuous_vs_weak_first_order，因为它同时拥有支持、反对、限定和方法性削弱证据。
