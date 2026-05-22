# References / Citation / Provenance 系统收敛设计

> **Status:** Target design
> **Date:** 2026-05-23
> **Scope:** Gaia Lang DSL + Compiler + CLI + 用户文档 + Skill 契约
> **Depends on:** [2026-04-09-references-and-at-syntax.md](2026-04-09-references-and-at-syntax.md), [2026-04-02-gaia-lang-v5-python-dsl-design.md](2026-04-02-gaia-lang-v5-python-dsl-design.md), [2026-04-04-compile-readme-design.md](2026-04-04-compile-readme-design.md)

## 0. 摘要与定位

一句话：**核心语法不动；把围绕它的那一圈 `refs` / `provenance` / `source_refs` /
`source_paper` / `metadata.figure` 收敛成一个连贯、有单一真源、编译器可校验的模型,
并补上用户文档。**

本 spec 不重新设计 `@` / `[@key]` 统一语法。那套设计
（[2026-04-09 spec](2026-04-09-references-and-at-syntax.md)）经过深思熟虑，
**且已经实现**（见 §1）。本 spec 处理的是它周围的「边缘」——同一件「引用 / 来源」
被表达在五六个互不相通的地方，其中只有一个被编译器真正校验。

本 spec 与 2026-04-09 spec 的关系：2026-04-09 定义 body 内引用标记的语法与解析；
本 spec 把所有**非 body-marker** 的引用 / 来源 / provenance 机制收敛进同一个模型，
并把 2026-04-09 spec 实现清单里一直没落实的两项（用户文档、渲染管线）补齐。

## 1. 现状核查：核心语法已实现，渲染管线未实现

2026-04-09 spec 头部标注 **Status: Target design**。核查源码后必须更正这个印象：
**核心解析 / 校验链路已经实现并接入编译器**，只有渲染管线（§5.4）和用户文档仍是
target。

实现位于 `gaia/engine/lang/refs/`（不是 spec 实现清单写的 `gaia/lang/refs/`——
代码树已重组到 `gaia/engine/` facade 之下；`gaia/lang/refs/` 现在只剩一个空的
`__pycache__`）：

| 模块 | 文件 | 状态 |
|---|---|---|
| Marker 提取器 | `gaia/engine/lang/refs/extractor.py` | 已实现：`_BARE_AT_RE` / `_BRACKET_GROUP_RE` / `_INNER_KEY_RE`，`extract()` 返回 `ExtractionResult`（`extractor.py:34-149`） |
| 三态 resolver | `gaia/engine/lang/refs/resolver.py` | 已实现：`resolve()` 三态、`check_collisions()` fail-fast、`validate_groups()` 同质组校验（`resolver.py:22-100`） |
| `references.json` loader | `gaia/engine/lang/refs/loader.py` | 已实现：CSL-JSON schema 校验、key grammar、`_CSL_TYPES` 白名单（`loader.py:73-194`） |
| 编译器接入 | `gaia/engine/lang/compiler/compile.py` | 已实现：`_collect_refs_from_text()`（`compile.py:572-614`）、`_ReferenceScanner`（`compile.py:1458-1724`） |

编译器确实做了 2026-04-09 spec 承诺的事：

- `references.json` 经 `load_references()` 加载并接入 `compile_package_artifact(references=...)`
  （`packaging.py:423-427`，`compile.py:2032-2051`）。
- 编译入口跑一次全局 `check_collisions(label_to_id, self.references)`
  （`compile.py:1486`）——label / citation key 冲突 → 硬错误。
- 每个 bracket group 过 `validate_groups()`——混合类型组 → 硬错误（`compile.py:589`）。
- strict 形式 `[@key]` 未命中 → `ReferenceError`，opportunistic `@key` 未命中 →
  静默字面量（`compile.py:599-608`）。
- 命中的 marker 写入 `metadata["gaia"]["provenance"]` 的 `cited_refs` /
  `referenced_claims`（`compile.py:1701-1724`）。
- 扫描范围覆盖 strategy reason、本地 knowledge content、action rationale
  （`compile.py:1553-1620`）；foreign 节点不被重扫，bridge reason 只 validate
  不 accumulate——与 2026-04-09 spec §3.1 的 scanning scope 一致。

测试覆盖：`tests/gaia/lang/refs/test_extractor.py`、`test_resolver.py`、
`test_loader.py`，以及 end-to-end `tests/gaia/lang/compiler/test_refs_integration.py`。

**但渲染管线（2026-04-09 spec §5.4）未实现**：

- 全仓库 `gaia/` 下无任何 `citeproc` 引用；`pyproject.toml` 不含 `citeproc-py`
  或 `bibtexparser` 依赖。
- 任何渲染路径（`gaia/cli/commands/render.py`、`_github.py`、`_detailed_reasoning.py`、
  `_obsidian.py`）都不读 `cited_refs` / `referenced_claims` / `source_refs` /
  `figure` / `caption`。
- 例包 `examples/mendel-v0-5-gaia` / `examples/galileo-v0-5-gaia` 均无
  `references.json`，也不用 `[@key]` 引文。
- 没有 `gaia cite import` 子命令（`gaia/cli/commands/` 下无 `cite.py`）。
- `gaia lint --refs` 不存在。

**结论：核心扎实、且已落地——`@` / `[@key]` 解析与校验是真模型，不用动。**
真正未完成的是 (a) 渲染消费端，(b) 用户文档，(c) 围绕核心的那一圈平行机制。
本 spec 处理 (b)(c)，并把 (a) 的实现交接给本 spec 的实现清单（§7）。

## 2. 三个真问题 + 一个次要问题（逐条以源码定位）

### 2.1 问题一：引用机制碎片化

「引用 / 来源 / provenance」散在至少六处，语义重叠、互不相通，作者要在多个地方
重复表达同一个引用：

| 机制 | 定义位置 | 谁写 | 谁读 | 编译器校验？ |
|---|---|---|---|---|
| `[@key]` / `@key`（body marker） | `gaia/engine/lang/refs/extractor.py` | 作者在 content / reason / rationale 里写 | 编译器（解析+校验+写 provenance），渲染端**目前无人读** | **是**——extract → validate_groups → resolve → strict-miss error |
| `metadata["gaia"]["provenance"]`（`cited_refs` / `referenced_claims`） | 编译器写入，`compile.py:1701-1724` | 编译器（从 body marker 派生） | LKM / 跨包查询**目前无消费者**（`gaia/engine/inquiry/`、`search/` 均不读） | 派生产物，本身不被独立校验 |
| `refs` typed metadata（figure / equation / citation） | **仅** skill 契约 `~/.claude/skills/gaia-package/references/emit-mapping.md` §1a | 作者手写 `claim(refs=(...))` | 渲染端**无人读**；编译器**完全不看** | **否**——见 §2.2 |
| `observe(source_refs=[...])` | DSL `gaia/engine/lang/dsl/support.py:106-223` | 作者写在 `observe()` 上 | 编译器原样拷进 IR（`compile.py:1036-1038`），渲染端无人读 | **否**——纯字符串 list，不 resolve、不查 `references.json` |
| `source_paper` kwarg | **仅** skill 契约 emit-mapping §0 | 作者手写 `claim(source_paper="Liu2015")` | 无消费者 | **否**——只是普通 `**metadata` 条目 |
| `claim(provenance=[...])` kwarg | DSL `gaia/engine/lang/dsl/knowledge.py:110-124`，IR `PackageRef`（`gaia/engine/ir/knowledge.py:68-72`） | 作者 | 编译器 → IR `Knowledge.provenance` | 部分——`PackageRef` 是 pydantic 模型，但语义是**包版本依赖**，不是文献引用 |
| `metadata={"figure":..., "caption":...}` | skill 契约提及的渲染元数据 | 作者 | 渲染端（设想中），目前无人读 | **否** |

**碎片化的直接后果**：光是「citation 一件事」就可能写在三处——
body 里的 `[@Liu2015]`、`refs` 里的 `{"type":"citation","key":"Liu2015"}`、
`source_paper="Liu2015"`。三处指向同一篇论文，三种拼写形态，无任何一处保证三者一致。
作者要重复表达，工具要在三处之间猜测真源。

**额外的命名陷阱**：`claim(provenance=...)` 的 `provenance` 与
`metadata["gaia"]["provenance"]` 同名但语义完全不同——前者是**包版本依赖**
（`PackageRef = {package_id, version}`，`gaia/engine/ir/knowledge.py:68-72`），
后者是**引文 / 知识引用记录**。这个 collision 本身就是碎片化的症状。

### 2.2 问题二：`refs` 处于「半成品」状态

`refs`（figure / equation / citation 三型 typed pointer）**只定义在 skill 契约**
`~/.claude/skills/gaia-package/references/emit-mapping.md` §1a。该契约自己写明：

> Gaia's `claim(...)` primitive accepts arbitrary `**metadata` kwargs and stores
> them in the `Knowledge.metadata` dict — it does **not** validate kwarg names.

也就是说 `refs` 是无人执行的自由 `**metadata`。核查编译器：`gaia/` 全仓库无任何
代码读 `refs`、检查它的三型白名单、或拒绝 `{"type":"section",...}`。`claim()` 的
签名（`gaia/engine/lang/dsl/knowledge.py:110-124`）把所有未识别 kwarg 收进
`**metadata` 后经 `_flatten_metadata` 原样存进 `Knowledge.metadata`。

后果：写错 `type`、写 `{type:"section",...}`、写 `{type:"figure"}` 漏 `id`——
全部静默通过。skill 契约里那张「Only three type values are allowed」的表是
**无人强制的建议**。

这是最糟的中间态：**既不是真模型（编译器不认），又被当契约用（skill 写得像规范）。**

### 2.3 问题三：文档漂移

整套引用系统的文档**不在用户会看的地方**：

- 完整设计在 spec `docs/specs/2026-04-09-references-and-at-syntax.md`，且标注
  仍是「Target design」（实际核心已实现，标注本身已过时）。
- `refs` typed pointer 在 skill 契约 `emit-mapping.md` 里。
- 用户文档 `docs/for-users/language-reference.md`（942 行）**没有任何**
  `@` / `[@key]` / `references.json` / citation / `refs` 章节。全文唯一与「来源」
  相关的出现是 `observe()` 示例里的 `source_refs=["Drozdov 2015"]`
  （`language-reference.md:211`）——而且那是个自由字符串，连 citation key 都不是。

2026-04-09 spec §10 实现清单最后一项「更新文档」写的是
`docs/foundations/gaia-lang/`，但该目录也未补；而且作者实际查的是
`docs/for-users/language-reference.md`。**作者要用的东西，在作者会看的地方查不到。**

### 2.4 次要问题：figure / equation ref 脱离来源就有歧义

`refs` 里的 `{"type":"figure","id":"Fig. 4"}` 单独看是无主的——「哪篇论文的
Fig. 4」？claim 一旦进了跨包知识图（LKM 层、registry），编号就悬空了：同一个图
编号在不同 source paper 里指向完全不同的图。本质上 figure / equation 引用必须和
来源论文绑成一个 `(source, figure-id)` 对才有意义。

## 3. 设计原则与不变量

1. **核心语法冻结。** `@` / `[@key]` 统一语法、CSL-JSON `references.json`、
   citeproc-py 委托、strict / opportunistic 不对称、collision fail-fast——
   全部保留，本 spec 不改一个字符。
2. **单一 canonical 真源。** 每一类引用恰有一个权威表达位置。其余位置要么
   被淘汰，要么从 canonical 派生（编译器自动生成，作者不手写）。
3. **编译器可校验。** 凡是被称作「契约」「whitelist」的东西，编译器必须执行它；
   否则不准叫契约。
4. **来源绑定。** figure / equation 这类「论文内定位」必须和 source 绑定，
   不允许出现无主编号。
5. **作者只写一遍。** 同一个引用，作者在源码里只表达一次。结构化列表、provenance
   metadata、渲染产物全部从那一次表达派生。

## 4. 改进 A–E：逐条决议

### 4.1 A — citation 收敛到单一 canonical：body 内 `[@key]`

**决议：以 body 内 `[@key]`（指向 `references.json`）为 citation 的唯一真源。**

- citation 的权威表达 = claim / note / question 的 `content`、strategy 的 `reason`、
  action 的 `rationale` 里写的 `[@key]` / `@key` marker。这是编译器**已经**校验、
  且渲染管线**将要**消费的形态。
- 需要结构化 citation 列表时（例如渲染 References 段、LKM provenance 查询），
  从 body marker **派生**——即编译器写入的 `metadata["gaia"]["provenance"].cited_refs`。
  这条链路已经实现（`compile.py:1701-1724`），本 spec 不新增。
- **淘汰 `source_refs`。** `observe(source_refs=[...])` 的自由字符串列表是一条
  平行机制：不 resolve、不查 `references.json`、无校验。作者要表达「这个观测来自
  Drozdov 2015」，应在 `observe(..., rationale="测得 Tc ... [@Drozdov2015]")`
  的 rationale 里用 `[@key]`——rationale 已经被 `_collect_action_rationale_refs`
  扫描并写入 provenance（`compile.py:1599-1620`）。`source_refs` 参数进入
  deprecation：保留一个发布周期、发 `DeprecationWarning`、文档标注，下个 major 删除。
- **`source_paper` 降格为派生 / 可选。** 见 §4.2 与 §5。

### 4.2 B — figure / equation ref 的身份决议（关键分叉）

maintainer 给了两条路：**升级**（做成编译器校验的一等公民、和 `source_paper`
绑定）vs **降级**（丢掉 equation 型、figure-id 只进 audit log）。

**决议：降级。丢弃 `equation` ref 型；`figure` ref 不升级为一等 DSL 构造，
figure 定位信息归并进 §4.3 的 figure 对象（绑定 source），其余纯定位信息进
audit log。**

理由：

1. **equation 指针近乎无用。** skill 契约 §1a 自己写明 claim body 必须自包含——
   「`refs` is metadata; it does not absolve the body of self-containment.
   The body must still inline what the equation states」。equation 的内容
   本来就要 inline 进 body（用 `$...$` math，`language-reference.md:134`
   已说明 content 支持 markdown math）。一个内容已经 inline、又指向一个悬空
   编号的指针，没有承载。直接丢掉。
2. **升级为一等公民的成本不匹配收益。** 升级意味着：新 DSL 构造 / 新 IR 字段 /
   编译器校验 type 白名单 / 与 `source_paper` 做引用完整性检查 / 渲染端嵌图。
   但核查显示**渲染端目前根本不消费 figure**，也没有「provenance 查询按 figure
   过滤」的真实需求。为一个无下游消费者的构造引入一等公民级机制，是过度工程。
3. **figure 仍有合法承载——但承载在「图」上，不在「指针」上。** 真正有意义的
   figure 用例是渲染嵌图（贴 artifact 路径 + caption）。那属于 §4.3 的 figure
   对象——一个绑定了 source、带 artifact 路径和 caption 的结构，编译器校验。
   单纯的「Fig. 4 编号」不构成嵌图，它只是 audit 痕迹：claim 的内容根植于哪张图。
   audit 痕迹归 `mapping_audit.md`（skill 已有此文件），不进可执行 DSL。
4. **消除次要问题（§2.4）。** 降级后不再有无主的 `{"type":"figure","id":"Fig. 4"}`
   进入 IR / 跨包图。需要嵌图的，走 §4.3 的 source-bound figure 对象；只是定位
   的，进 audit log。两条路都不产生悬空编号。

**净效果**：`refs` 的三型 typed pointer 全部退场——`citation` 型被 §4.1 的
`[@key]` 取代，`equation` 型丢弃，`figure` 型并入 §4.3 的 figure 对象或降为
audit log。`refs` 这个 metadata 字段本身被淘汰（见 §4.5）。

### 4.3 C — 合并 figure 的表示：单一 source-bound figure 对象

现状 figure 信息散在三处：`refs` 里的 figure 编号、`metadata.figure` 的 artifact
路径、`metadata.caption`。**决议：收成一个 figure 对象，绑定到 source。**

定义一个新的 DSL 构造 `figure(...)`（一等 Knowledge 的轻量伴生，或直接是一种
Note 子型——实现时择优），字段：

```python
fig_3 = figure(
    source="Liu2015",          # 必填:绑定到 references.json 的 citation key
    label="Fig. 3",            # 必填:论文内编号(消除歧义,(source, label) 唯一)
    path="figures/liu2015_fig3.png",  # 可选:渲染嵌图用的 artifact 相对路径
    caption="Fibonacci scaling of ...",  # 可选:渲染用 caption
)
```

- `(source, label)` 对消除了 §2.4 的悬空编号歧义。
- `source` 必须 resolve 到 `references.json` 的某个 key——编译器校验，未命中
  → 硬错误（与 `[@key]` strict-miss 同款）。
- claim 引用 figure：在 body 里写 `[@fig_3]`（`fig_3` 进 label 表，走现有
  knowledge-ref 通道），或在 `background=[fig_3]` 里挂。无需新语法。
- 渲染端读 `path` / `caption` 嵌图。无 `path` 时 figure 对象退化为一个纯
  audit 锚点，仍合法。

这样三个字段收成一个对象，且不再脱离 source。

### 4.4 D — 把引用章节写进 `docs/for-users/language-reference.md`

**决议：在 `language-reference.md` 新增「References and Citations」一节**，
覆盖：

- `[@key]`（strict）vs `@key`（opportunistic）的语义与不对称；
- `references.json` 的位置、CSL-JSON 格式、最小字段要求；
- knowledge ref（`[@local_label]`）vs citation（`[@Bell1964]`）的区分与统一查表；
- collision fail-fast、homogeneous-group 规则各一个简短示例；
- `figure(...)` 对象（§4.3）；
- 一个「don't」小节：不要用 `source_refs`（已 deprecated）、不要把 citation
  写进 `claim(provenance=...)`（那是包依赖）。

2026-04-09 spec §10 把文档任务指到 `docs/foundations/gaia-lang/`——本 spec
更正：主战场是 `docs/for-users/language-reference.md`，因为那才是作者查阅的入口。
`docs/foundations/` 可保留一个深入链接。

同时把 2026-04-09 spec 的 Status 从「Target design」更新为「Implemented (core);
rendering pipeline tracked by 2026-05-23-references-system-consolidation.md」。

### 4.5 E — `refs` 的归宿：淘汰，不保留

maintainer 给的条件是「`refs` 若保留 → 编译器必须校验它」。

**决议：不保留 `refs` metadata 字段。** 经 §4.1（citation → `[@key]`）、
§4.2（equation 丢弃、figure 降级）、§4.3（figure → `figure()` 对象）之后，
`refs` 的三型已无一幸存。继续保留一个空壳 `refs` 字段没有意义。

因此：

- skill 契约 `emit-mapping.md` §1a「The `refs` metadata field」整节删除。
- skill 契约 §0「Shared metadata kwargs」表里 `refs` 行删除。
- `claim(...)` 不新增 `refs` 校验——因为不再有 `refs`。
- 编译器对 `claim()` 的 `**metadata` 增加一条**保留键拒绝**：如果 metadata 里
  出现 `refs`、`source_refs`、`source_paper` 这些已淘汰 / 已迁移的键，编译器
  发 `DeprecationWarning`（一个发布周期后升级为错误），并在消息里指向
  `[@key]` / `figure()` / `rationale` 的替代写法。这就是把「whitelist」从
  无人执行的建议变成编译器执行的契约——只不过执行的方式是**拒绝旧形态**，
  而不是校验一个保留下来的半成品。

## 5. 目标收敛模型

收敛后，引用 / 来源 / provenance 只有**三种 canonical 表达**，各有单一真源，
全部编译器可校验：

| 引用种类 | 单一 canonical 真源 | 编译器校验 | 派生产物 |
|---|---|---|---|
| **文献引用（citation）** | body 内 `[@key]` / `@key`，key 指向 `references.json` | extract → validate_groups → resolve → strict-miss error（已实现） | `metadata["gaia"]["provenance"].cited_refs`；渲染 References 段 |
| **本包 / 跨包知识引用（knowledge ref）** | body 内 `[@label]` / `@label`，label 指向 compile-closure label 表 | 同上 | `metadata["gaia"]["provenance"].referenced_claims`；渲染锚点链接 |
| **论文图表（figure）** | `figure(source=, label=, path=, caption=)` 对象；body 内 `[@fig_label]` 引用它 | `source` resolve 到 `references.json`；`(source, label)` 唯一；type 字段不存在所以无非法 type | 渲染嵌图；audit 锚点 |

**退场机制**：`refs` metadata（淘汰）、`source_refs`（deprecated → 删除）、
`equation` ref（丢弃）、`metadata={"figure":...,"caption":...}`（并入 `figure()`）。
`source_paper`：不再是独立的权威字段——一个 claim 引用了哪篇论文，由它 body 里
的 `[@key]` 决定；skill 若仍需一个「主来源」标签用于审计，可保留为纯 audit
metadata，但不进 canonical 模型，也不被工具当真源。

**保留但澄清**：`claim(provenance=[PackageRef])`——这是包版本依赖，**不是**
文献引用，与本收敛模型正交。文档（§4.4）必须明确二者区别，消除 §2.1 的命名陷阱。

### 5.1 Before / After：一个 citation

**Before**（碎片化，同一篇论文写三处）：

```python
liu2015_c1 = claim(
    r"The system exhibits Fibonacci-scaling emergence (see Fig. 3).",
    source_paper="Liu2015",
    refs=(
        {"type": "citation", "key": "Liu2015"},
        {"type": "figure", "id": "Fig. 3"},
        {"type": "equation", "id": "Eq. (5)"},
    ),
)
```

`source_paper` 无人校验；`refs` 无人校验；`Fig. 3` 编号悬空；`Eq. (5)` 指针
无承载；citation 写了两遍（`source_paper` + `refs`）。

**After**（单一真源，编译器校验）：

```python
# references.json 里有 "Liu2015" 条目(CSL-JSON)
fig_3 = figure(source="Liu2015", label="Fig. 3",
               path="figures/liu2015_fig3.png",
               caption="Fibonacci scaling of the order parameter.")

liu2015_c1 = claim(
    r"The system exhibits Fibonacci-scaling emergence, where the order "
    r"parameter follows $\phi^n$ for mode index $n$ [@Liu2015]. "
    r"See [@fig_3].",
    background=[fig_3],
)
```

citation 只在 body `[@Liu2015]` 表达一次（编译器校验、会渲染、写 provenance）；
equation 内容 inline 进 body（`$\phi^n$`）；figure 是 source-bound 对象，
`[@fig_3]` 走 knowledge-ref 通道。无悬空编号、无平行机制。

### 5.2 Before / After：一个 figure

**Before**（三个字段，无主）：

```python
weak_pt = claim(
    r"Static screening assumption may fail at high density.",
    claim_kind="weak_point",
    refs=({"type": "figure", "id": "Fig. 4"},),
    metadata={"figure": "fig4.png", "caption": "Screening length vs density"},
)
```

`Fig. 4` 不知是哪篇论文的；`refs.figure` 和 `metadata.figure` 两个字段都叫
figure 却一个存编号一个存路径；全部无校验。

**After**（一个 source-bound 对象）：

```python
fig_4 = figure(source="Liu2015", label="Fig. 4",
               path="figures/liu2015_fig4.png",
               caption="Screening length vs density.")

weak_pt = claim(
    r"Static screening assumption may fail at high density, where the "
    r"screening length drops below the inter-particle spacing [@fig_4].",
    claim_kind="weak_point",
    background=[fig_4],
)
```

### 5.3 Observe 的 source：Before / After

**Before**：`observe(T_c, value=..., source_refs=["Drozdov 2015"])`——
自由字符串，不校验、不 resolve、渲染端无人读。

**After**：

```python
measured_tc = observe(
    T_c, value=q(203, "K"), error=q(5, "K"),
    rationale="Reported superconducting transition temperature [@Drozdov2015].",
)
```

`[@Drozdov2015]` 在 rationale 里被 `_collect_action_rationale_refs` 扫描
（`compile.py:1599-1620`），resolve 到 `references.json`，写入目标 claim 的
`provenance.cited_refs`。单一真源、编译器校验。

## 6. 迁移与向后兼容

收敛模型对现有 `@label`、`[@key]`、`references.json` 用法**完全不破坏**——这些
是 §3 原则 1 冻结的核心。破坏面只在被淘汰的边缘机制，且全部走一个发布周期的
deprecation：

| 旧机制 | 迁移路径 | 时间表 |
|---|---|---|
| `observe(source_refs=[...])` | 改写为 rationale 里的 `[@key]` | v0.6.x 发 `DeprecationWarning`；v0.7 删除参数 |
| `claim(refs=(...))` | citation → body `[@key]`；equation → inline；figure → `figure()` 对象 | v0.6.x：编译器对 metadata 里出现 `refs` 发 `DeprecationWarning`；v0.7 升级为错误 |
| `claim(source_paper=...)` | body `[@key]`（权威）；若需 audit 标签，留作纯 audit metadata | v0.6.x 文档标注「非 canonical」；不强制删除（无害的 audit metadata） |
| `metadata={"figure":..., "caption":...}` | `figure(source=, label=, path=, caption=)` 对象 | 随 `refs` 一起 deprecate |

**现有 `@label` 用法**：2026-04-09 spec §8 的迁移保证继续有效——现有 strategy
reason 里的 `@label`（含 cross-package import 的 foreign label）继续 resolve，
本 spec 不动这条链路（`compile.py` 的 `label_to_id` 行为不变）。

**现有已发布 package**：例包（mendel / galileo）均无 `references.json`、无
`[@key]`、无 `refs`——收敛对它们零影响。唯一接触点是 mendel 的
`observe(source_refs=[...])`（`examples/mendel-v0-5-gaia/.../__init__.py:116`），
随 `source_refs` deprecation 一并迁移，作为迁移示例。

**`gaia author claim --metadata` 的现存缺陷**：核查发现
`gaia/cli/commands/author/claim.py:117` 把 `--metadata '{...}'` 渲染为
`claim(metadata={...})`（**嵌套**，不 spread 成 kwargs）。这意味着 author CLI
本就无法正确 emit `claim(refs=(...))` 这种直接 kwarg；它只能靠
`_flatten_metadata`（`knowledge.py:103-107`）单键解包的偶然行为把
`metadata={"refs":...}` 还原。收敛后 `refs` 退场，这个偶然依赖也随之消失——
author CLI 不需要为 `refs` 做任何特殊处理，反而是个简化。`figure()` 作为新
DSL 构造，若需 author CLI 支持，应有独立的 `gaia author figure` 子命令
（本 spec 列入清单 §7，不强制 PR 1 完成）。

## 7. 实现清单

按 PR 切分，PR 1 是收敛 + 文档（不依赖渲染管线），PR 2 是渲染管线落地。

### PR 1 — 收敛与文档（无网络副作用、无新依赖）

引擎 / 编译器：

- [ ] `gaia/engine/lang/dsl/` 新增 `figure(...)` DSL 构造（§4.3）：
      `source` / `label` / `path` / `caption` 字段；导出到 `gaia.engine.lang`。
- [ ] `gaia/engine/ir/knowledge.py` —— 为 figure 增加 IR 表示（轻量 Knowledge
      子型或 Note 变体），含 `source` / `label` / `path` / `caption`。
- [ ] `gaia/engine/lang/compiler/compile.py` —— figure 校验：`source` 必须
      resolve 到 `references.json`（未命中 → `ReferenceError`）；
      `(source, label)` 在包内唯一（重复 → 错误）。
- [ ] `gaia/engine/lang/compiler/compile.py` —— `**metadata` 保留键拒绝：
      metadata 出现 `refs` / `source_refs` / `source_paper`（在非 audit 语境）
      时发 `DeprecationWarning`，消息指向替代写法。
- [ ] `gaia/engine/lang/dsl/support.py` —— `observe(source_refs=...)` 标注
      deprecated，发 `DeprecationWarning`，文档引导改用 rationale `[@key]`。

CLI：

- [ ] `gaia/cli/commands/author/` —— 新增 `gaia author figure` 子命令（可选，
      可延后至 PR 2）。
- [ ] `gaia/cli/commands/author/observe.py` —— `--source-refs` flag 标注
      deprecated。

Skill 契约：

- [ ] `~/.claude/skills/gaia-package/references/emit-mapping.md` —— 删除 §1a
      「The `refs` metadata field」整节；§0「Shared metadata kwargs」表删除
      `refs` 行；`source_paper` 行改注「audit-only，非 canonical；citation
      走 body `[@key]`」；§1 / §2 代码示例移除 `refs=(...)`。
- [ ] skill 契约新增一节说明 `figure()` 对象与 body `[@key]` citation。

用户文档（本 spec 的核心交付之一）：

- [ ] `docs/for-users/language-reference.md` —— 新增「References and Citations」
      节（§4.4 列出的全部要点）。
- [ ] `docs/for-users/language-reference.md:211` —— `observe()` 示例去掉
      `source_refs=`，改用 rationale `[@key]`。
- [ ] `docs/specs/2026-04-09-references-and-at-syntax.md` —— Status 从「Target
      design」更新为「Implemented (core)」并交叉链接本 spec。

测试：

- [ ] `tests/gaia/lang/` —— `figure()` 构造单测：source 未命中报错、
      `(source,label)` 重复报错。
- [ ] `tests/gaia/lang/compiler/test_refs_integration.py` —— 扩展：`refs` /
      `source_refs` metadata 触发 `DeprecationWarning`；figure 引用经
      `[@fig_label]` 写入 `referenced_claims`。

### PR 2 — 渲染管线落地（2026-04-09 spec §5.4 的欠账）

- [ ] `pyproject.toml` —— 加 `citeproc-py`（runtime）、`bibtexparser >= 2.0`
      （optional，仅 `gaia cite import`）。
- [ ] `gaia/cli/commands/render.py` 及 `_github.py` / `_obsidian.py` ——
      消费 `metadata["gaia"]["provenance"].cited_refs`，经 citeproc-py 渲染
      citation 文本 + `## References` 段（2026-04-09 spec §5.4 的 4 步管线）。
- [ ] 渲染端消费 `referenced_claims` → 锚点链接；消费 `figure` 对象 → 嵌图。
- [ ] `gaia/cli/commands/cite.py` —— 新增 `gaia cite import`（BibTeX / CSL-JSON
      → `references.json`，2026-04-09 spec §7）。
- [ ] `gaia/engine/lang/refs/styles/*.csl` —— 内置 apa / ieee / nature /
      chicago 样式。
- [ ] `gaia/cli/commands/lint.py` —— `gaia lint --refs`（2026-04-09 spec §8.2）。

## 8. Non-Goals

- 不重新设计 `@` / `[@key]` 语法、CSL-JSON 格式、citeproc-py 委托、collision
  fail-fast——§3 原则 1 冻结。
- 不引入 DOI 自动补全（2026-04-09 spec §6 已论证）。
- 不引入 cross-package reference 语法 `[@pkg::label]`（2026-04-09 spec §9）。
- 不为 figure 设计独立的 bibliography / figure-index 静态页。
- 不改 `claim(provenance=[PackageRef])` 的包依赖语义——只在文档里澄清它与
  citation 的区别。
