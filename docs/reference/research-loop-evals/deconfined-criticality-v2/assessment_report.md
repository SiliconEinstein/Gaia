# Research Assessment

- schema_version: 1
- focus: continuous_vs_weak_first_order
- snippets: 70
- paper_leads: 57
- relations: 11
- relation_mix: opposes: 3, qualifies: 3, supports: 3, undercuts: 2

## Review Summary

当前证据更支持一个谨慎结论：deconfined criticality 是解释二维 Néel-VBS 转变的重要理论框架，并且在若干 sign-problem-free 模型中有正面数值和对称性信号；但对最核心的方格 J-Q/SU(2) 类模型，证据包尚不足以把热力学极限连续 DQCP 判为已确立事实。弱一阶转变、有限尺寸慢漂移、模型依赖性和 monopole/IR flow 未定性仍是主要反证或限定。

## Review Sections

### 1. 支持连续 DQCP 的证据簇

证据包中最强的正面材料来自方格 J-Q/SU(N) 类 sign-problem-free lattice 模型和 NCCP1 field theory 的对应关系。相关 snippets 把 AF/VBS 或 Néel/VBS 转变描述为超越 Landau-Ginzburg 的候选连续转变，涉及 deconfined spinons、emergent gauge symmetry、unusual critical exponents，并且有 QMC 观察被概括为支持 DQCP scenario。emergent symmetry、VBS anisotropy 的危险无关性以及高阶对称性信号，也构成连续临界点的重要正面诊断。

### 2. 弱一阶解释和有限尺寸问题

反方向证据集中在 J-Q 模型热力学极限未定、weakly first-order transition 的信号在常规 observables 中非常小、以及 running exponent/finite-size scaling 可能误导。尤其是 targeted expand 中关于弱一阶转变的 snippet 指出，partition-function derivative 中的大体积解析背景会掩盖小的 singular jump，这解释了为什么弱一阶可以长时间伪装成连续临界。因而，仅凭有限尺寸上看起来平滑的 scaling 或近似 collapse，不足以排除弱一阶。

### 3. emergent symmetry 的诊断力边界

emergent SO(5)、O(4)、U(1) 或相关 symmetry enhancement 是 DQCP 研究的中心信号，但证据包也提醒它不是充分条件。近似 SO(2) symmetry 与弱一阶转变 masquerading as deconfined criticality 的例子说明，symmetry enhancement 需要和 critical exponent drift、Binder cumulant、energy histogram、domain-wall/interface tension、monopole relevance 等诊断联合评估。

### 4. 模型依赖性和理论桥接

不同 microscopic models 的证据不是同质的：square-lattice J-Q、honeycomb JQ、Kagome/easy-plane、Shastry-Sutherland、S=3/2 和 SU(N) 模型可能对应不同转变阶数、不同 VBS pattern 和不同 symmetry constraints。NCCP1、easy-plane duality、QED3、anomaly matching 等理论材料为解释 emergent symmetry 和候选 fixed point 提供约束，但不能替代对具体 lattice transition order 的数值和原文级别证据核查。

### 5. 当前 evidence packet 的结论

如果要给出工作性判断，当前最稳妥的表述是：DQCP 是一个有强理论动机和若干正面数值信号的候选 universality scenario；但在关键 SU(2) lattice realizations 中，连续性与弱一阶之间仍存在未解决 tension。下一步不应继续泛泛搜索 deconfined criticality，而应围绕 J-Q/SU(2) transition order、emergent symmetry 是否足以区分连续/弱一阶、以及 NCCP1 fixed point/monopole relevance 的理论约束做 focused assessment。

## Limitations

- 本轮仍主要基于 LKM snippets，没有逐篇抽取原始 critical exponent、Binder cumulant、energy histogram 或 scaling collapse 图。
- SO5 query 引入了化学 SO5 自由基等 retrieval noise；assessment 已避开这些 refs，但下一轮 query 需要更强领域锚定。
- NCCP1/duality 证据有明显 paper overlap bias，大量来自同一 review-like paper lead。
- 尚未系统覆盖 conformal bootstrap、CFT fixed point existence bounds、monopole scaling dimension 等理论约束。

## Next Queries

- J-Q model weakly first order Binder cumulant energy histogram deconfined criticality
- NCCP1 monopole scaling dimension Neel VBS deconfined critical point
- SO5 emergent symmetry DQCP conformal bootstrap critical exponents
- square lattice J-Q deconfined criticality critical exponent drift

## Relations

| type | claim | rationale | status | promotion_hint | source_refs |
| --- | --- | --- | --- | --- | --- |
| supports | 方格 J-Q/SU(N) 类 sign-problem-free lattice 模型中的若干 QMC 结果支持 Néel-VBS 转变存在 DQCP 解释。 | scan 与 expand 都检索到周期方格 J-Q 模型的基态 valence-bond QMC 观察，被概括为支持反铁磁到 VBS 转变的 deconfined quantum-criticality scenario。 | candidate | infer | snippet:snippet_20, snippet:snippet_40 |
| supports | NCCP1/DQCP 框架为 Néel-VBS 转变提供了超越 Landau-Ginzburg 范式的连续临界理论候选。 | 证据包中多处把 AF/VBS 或 Néel/VBS 转变与 deconfined spinons、emergent gauge symmetry、NCCP1 field theory 和非传统 critical exponents 联系起来。 | candidate | infer | snippet:snippet_7, snippet:snippet_33 |
| supports | emergent symmetry 与 VBS anisotropy 的危险无关性为连续 DQCP 提供了重要但非决定性的正面信号。 | 证据包显示 Z4/VBS anisotropy 是否危险无关、临界点是否出现高阶 emergent symmetry，是判断 DQCP 的核心诊断之一。 | candidate | infer | snippet:snippet_6, snippet:snippet_11, snippet:snippet_38 |
| opposes | 现有 evidence packet 不支持把方格 J-Q 模型的热力学极限性质直接判定为已经确立的连续 DQCP。 | 多个 snippets 明确指出 J-Q 模型在 J/Q 约 0.045 附近的热力学极限性质尚未定论，可能是连续 DQCP，也可能是弱一阶转变。 | candidate | none | snippet:snippet_27, snippet:snippet_44 |
| opposes | 弱一阶转变可以在常规 observables 中表现得很像连续 DQCP，因此有限尺寸临界标度本身不足以排除弱一阶解释。 | targeted expand 检索到弱一阶和 DQCP 争议中常规 observables 的奇异 jump 会被大体积解析项掩盖，使弱一阶信号很小；这直接反对过早将平滑 finite-size behavior 解释为连续转变。 | candidate | contradict | snippet:snippet_41, snippet:snippet_42 |
| opposes | 早期把某些具体模型视为 DQCP realization 的主张已被后续研究或诊断要求削弱。 | 证据包指出先前关于 J-K 模型实现 DQCP 的说法需要同时展示 spin/VBS sector 临界性、emergent symmetry 和 compatible exponents，而已有结果对这种直接实现提出了问题。 | candidate | none | snippet:snippet_1, snippet:snippet_4 |
| qualifies | DQCP 是否连续高度依赖 microscopic lattice model、VBS pattern、spin 表示和相邻相结构，不能从一个模型无条件外推到整个领域。 | honeycomb JQ、S=3/2、J1-J2-J3、Shastry-Sutherland、Kagome/easy-plane 等结果显示，不同模型中的转变阶数、临界信号和相邻相组织并不自动相同。 | candidate | question | snippet:snippet_5, snippet:snippet_21, snippet:snippet_25, snippet:snippet_28, snippet:snippet_43, snippet:snippet_45 |
| qualifies | emergent symmetry 是强诊断信号，但不能单独作为连续转变的充分条件。 | 证据包中出现了近似 SO(2) symmetry 与弱一阶转变伪装成 deconfined criticality 的警示，也出现了 SO(5)/O(4) anisotropy 相关理论约束，说明 symmetry enhancement 需要与 scaling 和 drift 诊断联合解释。 | candidate | question | snippet:snippet_16, snippet:snippet_38, snippet:snippet_39, snippet:snippet_56 |
| qualifies | NCCP1/duality/anomaly 结构更像是约束和解释候选机制，而不是直接解决 lattice transition order 的经验判据。 | duality 结果为 easy-plane NCCP1、QED3、self-duality 和 anomaly matching 建立理论桥接，但 SU(2) NCCP1 自对偶和具体 lattice fixed point 的存在仍需要额外论证。 | candidate | question | snippet:snippet_30, snippet:snippet_35, snippet:snippet_36, snippet:snippet_37 |
| undercuts | finite-size scaling 的慢漂移和 running exponent 诊断不足，会削弱仅凭有限尺寸数值外推得出连续 DQCP 的论证力度。 | J-Q 模型中 running exponent、transition coupling 附近的有限尺寸估计，以及 weakly first-order signatures 被掩盖的机制，共同表明方法层面的判据需要更严格。 | candidate | obligation | snippet:snippet_23, snippet:snippet_26, snippet:snippet_41, snippet:snippet_42, snippet:snippet_44 |
| undercuts | monopole relevance 和未知 IR flow 会削弱从 continuum deconfined field theory 直接推出 lattice 连续临界点的推理。 | 证据包指出建立 Neel-VBS deconfined criticality 需要知道 monopole operators 是否相关；若 monopoles relevant，会恢复 confinement 并推动 VBS 或其他有序态。 | candidate | obligation | snippet:snippet_51, snippet:snippet_53 |

## Candidate Obligations

| kind | content | source_refs |
| --- | --- | --- |
| extract_primary_numerics | 拉取并逐篇核查方格 J-Q/SU(2) 关键论文中的 critical exponents、system sizes、Binder cumulant、energy histogram、running exponent 和 transition coupling drift。 | snippet:snippet_23, snippet:snippet_26, snippet:snippet_42, snippet:snippet_44 |
| resolve_method_diagnostic | 评估哪些 diagnostics 能区分真正连续 DQCP 与弱一阶伪临界，包括 finite-size drift、latent heat proxy、domain-wall/interface tension、running exponent 和 symmetry histogram。 | snippet:snippet_41, snippet:snippet_42 |
| expand_theory_constraints | 补充 conformal bootstrap、NCCP1 fixed point existence、SO(5)/O(4) anisotropy relevance 和 monopole scaling dimension 的理论约束。 | snippet:snippet_38, snippet:snippet_39, snippet:snippet_51, snippet:snippet_56 |
