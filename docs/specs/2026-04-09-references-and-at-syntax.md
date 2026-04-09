# References & `@` Syntax Unification Design

> **Status:** Target design
> **Date:** 2026-04-09
> **Scope:** Gaia Lang DSL + Compiler + CLI
> **Depends on:** [2026-04-02-gaia-lang-v5-python-dsl-design.md](2026-04-02-gaia-lang-v5-python-dsl-design.md), [2026-04-04-compile-readme-design.md](2026-04-04-compile-readme-design.md)

## 1. Problem

Gaia 目前没有系统的引文管理，但同时又在 strategy `reason` 字段里支持了一套 `@label` 语法指向本包 knowledge node：

```python
# gaia/lang/compiler/compile.py:177
_AT_LABEL_RE = re.compile(r"@([a-z_][a-z0-9_]*)")
```

这套 `@label` 机制有几个问题：

1. **只在 strategy reason 里工作**，claim / setting / question 的 `content` 里的 `@foo` 不解析，读者写 README 的时候没法跨段落跳转
2. **缺失的文献引用**：作者要引 Bell 1964 时只能往 content 里手搓 `[Bell 1964, Physics.1.195]`，没有统一格式、没有校验、没有渲染
3. **语法边界模糊**：裸 `@` 在长文本里会和 Python decorator（`@dataclass`）、email（`foo@bar.com`）、Twitter handle（`@elonmusk`）等混淆；现状只 warning 不 error，导致警告噪音高、真正的 typo 被淹没
4. **没有 provenance**：作者在 claim 里 mention 了一篇论文，LKM 层无法做 "谁引用了 Bell 1964" 这种跨包查询

本 spec 一次性解决两件事：**引入文献引用系统** + **统一 `@` 语法的严格度**，并且让两者共享同一套语法。

## 2. Design Goals

1. **Unified surface syntax** —— knowledge ref 和 citation 共用一套 grammar，作者不需要学两种
2. **Pandoc-compatible** —— 直接继承 Pandoc citation syntax，作者从 Pandoc/Quarto/Manubot 文档复制过来的引用能直接用
3. **No parser work** —— `[@key]` 的 prefix / locator / suffix parsing 全部委托给 `citeproc-py`
4. **Strict when intent is explicit** —— 作者写了括号就表示"我确定这是引用"，typo 必须 error
5. **Lenient when intent is opportunistic** —— 裸 `@key` 按 Pandoc 习惯处理，查不到就是字面量，不干扰普通文本
6. **Backward compatible** —— 现有 strategy reason 里的 `@label` 写法继续有效，不需要批量迁移
7. **Non-goal: DOI auto-completion** —— 不在 compile 路径引入网络副作用（详见 §6）

## 3. Unified `@` Syntax

### 3.1 核心规则

Gaia 采用 **Pandoc citation syntax 的子集**，resolve 时在一个**统一符号表**里查找：

```
统一符号表 = 当前 package 编译 closure 的 label 表 ⊎ references.json
```

**关键点**：label 表不是"仅本包 local 声明"，而是**当前 compile 单位能看到的所有 knowledge 节点**，**包括从 dependency import 进来的 foreign 节点**。这与 Gaia 现行 compiler 行为一致（`gaia/lang/compiler/compile.py` 里的 `label_to_id` 就是这样构建的），本 spec 不改这一点。

具体示例：作者写 `from package_a import key_missing_lemma` 后，在本包 strategy reason 里写 `@key_missing_lemma` 必须能 resolve 到那个 foreign 节点 —— 这是现有工作流，任何 spec 变更都不得破坏。

#### Scanning scope: local only

**Reference scanning（content 和 reason）只 accumulate provenance 到 local 节点**，从不 accumulate 到 foreign 节点。具体规则：

1. **Foreign knowledge 的 `content` 不会被重新扫描**。Foreign 节点的 content 在 dependency 自己编译时已经被验证过了，它的引用对应 dependency 自己的 references.json。如果 consumer 重新扫，一定会 miss 掉（consumer 的 references.json 通常没有 dep 的 citation key），从而一个 dep 升级引用语法就会打断所有下游 consumer。

2. **Bridge strategy 的 reason 仍然被 validate，但不 accumulate 到 foreign target**。考虑 `fills(source=local_result, target=foreign_lemma, reason="See [@Bell1964]")`：strategy 的 `conclusion` 是 foreign 节点。这时 compile **仍然**会 extract + validate reason 里的 `[@Bell1964]`（mixed group / strict miss 仍会报错），但**不会**把 Bell1964 写到 foreign_lemma 的 provenance metadata 上。理由：
   - Foreign 节点归 dep 作者所有；consumer 的文献选择不应该污染 dep 的 IR metadata
   - 同一个 foreign 节点可能被多个 consumer 从不同角度引用 / bridge，如果每个 consumer 都往上面写自己的 citation，metadata 就会冲突
   - Provenance 查询（"谁引用了 Bell1964？"）会得到错误答案
   - 这是本 spec 的硬性安全不变量：**compile 永远不 mutate foreign 节点的 metadata**

   Bridge reason 里的合法 citation 目前被"丢弃"（只走 validation 不走 accumulation）。未来如果需要给 bridge 保留 provenance，应该存到 local source 或 bridge manifest 里，不应该去动 foreign target。这是 out-of-scope for PR 1。

3. **Label 表包含 foreign 节点是对的**（spec §3.1 头部已说明）—— 为了让**本包**的 content/reason 能引用 foreign label（`[@foreign_lemma]`）。包含 foreign 节点和"扫描 foreign content"是两件事。

两种语法形式，严格度不同：

```
[@xxx]           STRICT reference
                 ├── xxx 在 label 表        → knowledge ref
                 ├── xxx 在 references.json → citation
                 ├── 都不在                  → ERROR
                 └── 两边都在                → ERROR (collision, 详见 §3.5)

@xxx             OPPORTUNISTIC reference (Pandoc narrative form)
                 ├── 在 label 表            → inline knowledge ref
                 ├── 在 references.json     → narrative citation "Bell (1964)"
                 ├── 都不在                  → 字面量，静默放过
                 └── 两边都在                → ERROR (collision, 详见 §3.5)

\@xxx            字面量，强制关闭解析（在裸形式和括号形式**两者内部**都有效）
```

**`\@` 转义在括号组内也工作**：`[\@Bell1964]` 整段都是字面量，`[see @Bell1964 and \@footnote]` 只提取 `Bell1964`，`\@footnote` 留作字面量。这让作者可以在 claim content 里写字面的 `[@key]` 示例来解释引用语法本身，不会触发 strict-miss error。

严格度的不对称来自**作者 intent 是否显式**：括号 = "我明确声明这是引用"，裸形式 = Pandoc opportunistic 渲染。

**Collision 不分 strict/opportunistic**：只要一个 key 同时存在于 label 表和 references.json，无论是 `[@xxx]` 还是 `@xxx`，一律 compile error。这是本 spec 的硬性安全不变量，理由详见 §3.5。

### 3.2 Pandoc metadata syntax 子集

支持的形式：

```
[@key]                              parenthetical
[-@key]                             suppress-author (only year; citations only)
[@key1; @key2; @key3]               multiple grouped
[see @key, p. 5]                    prefix + locator
[see @key, pp. 33-35 and passim]    prefix + locator + suffix
[cf. @a, chap. 4; also @b, §2]      multi-item with metadata per item
@key                                narrative (bare form)
```

Locators 按 Pandoc 标准识别：`p.` `pp.` `chap.` `sec.` `fig.` `vol.` `para.` `art.` `bk.` `ch.` `col.` `fol.` `l.` `line.` `n.` `no.` `op.` `pt.` `r.` `s.` `sub verbo` `v.`

#### Homogeneous-group rule（重要）

**一个 `[...]` 组内的所有 key 必须解析到同一种类型 —— 要么全是 knowledge refs，要么全是 citations，不允许混合。** 混合组 compile error。

理由：

- §5.4 的渲染管线把 knowledge refs 替换成占位符后再交给 citeproc-py。如果一个 Pandoc group 里同时有 knowledge ref 和 citation（比如 `[see @lemma_a; @Bell1964, p. 5]`），占位符替换会把这个 group 切成"半个合法 Pandoc group + 一堆占位符文本"，citeproc-py 无法正确处理 group-level prefix/locator
- 要支持混合组就必须自己写一个完整的 Pandoc group tokenizer（prefix / items / locators / suffixes），这与 §2.3 的"no parser work"目标直接冲突
- 实际语义上混合组没有意义：把"本地 lemma 引用"和"外部文献引用"捆在同一个 `[...]` 里没有表达力优势 —— 作者完全可以拆成两个独立的引用标记

合法 / 非法例子：

```
[@lemma_a; @lemma_b]                  ✓ 同类型（都是 knowledge refs）
[@Bell1964; @CHSH1969]                ✓ 同类型（都是 citations）
[see @Bell1964, p. 5; @EPR1935]       ✓ 同类型，带 prefix/locator
[@lemma_a; @Bell1964]                 ✗ 混合 → ERROR
[see @lemma_a; @Bell1964, p. 5]       ✗ 混合 → ERROR
```

检测时机：compile 时对每个 bracketed group 先抽出所有 key，分别 resolve，若类型不一致就报错：

```
error: mixed-type reference group in <file>:<line>
  [see @lemma_a; @Bell1964, p. 5]
        ^^^^^^^  ^^^^^^^
        knowledge  citation
  a bracketed reference group must contain only knowledge refs or only citations.
  split into two groups:
    [see @lemma_a] [@Bell1964, p. 5]
```

纯 citation 组和纯 knowledge ref 组都可以任意使用 prefix / locator / suffix / multi-item 语法 —— 限制只针对 key 的类型，不限制 Pandoc 的其他结构。

### 3.3 Citation key 合法字符

继承 Pandoc 规则：

```
key ::= [A-Za-z0-9_] [A-Za-z0-9_:.#$%&+?<>~/-]*
        且不能以标点结尾
```

合法例子：

- `smith04` / `Smith2004` / `EPR1935` / `Bell1964`
- `bell_1964` / `bell.1964`
- `arxiv:2401.12345`
- `doi:10.1103/PhysRev.47.777`
- `wiki:quantum_mechanics`
- `10.1103/PhysRev.47.777`（纯 DOI 作为 key）

### 3.4 Knowledge label 约束（不变）

Knowledge label 的合法形态保持现有约束：

```
label ::= [a-z_][a-z0-9_]*
```

这条约束是**协议层面的要求**，不是现状巧合。目的：

- 让 label 在 citation key 命名空间里占据"纯小写蛇形"这个区间，和典型 citation key（含大写/数字/冒号点）命名风格自然区隔
- 避免 `@Bell1964` 同时能解析成 label 和 citation 的歧义来源

如果未来要放宽（比如支持大写开头的 label），必须更新本 spec。

### 3.5 Collision 处理：fail-fast

当一个 key 同时出现在 label 表和 references.json 里，**compile 直接 error**，不再 warning-fallback。

```
error: ambiguous reference key '<key>' in <file>:<line>
  '<key>' exists both as a knowledge label and as a citation key.
  references cannot be silently disambiguated.
  rename one of:
    - the knowledge node labeled '<key>'
    - the entry '<key>' in references.json
```

这条规则不分 strict / opportunistic，也不分 `@xxx` / `[@xxx]` —— **只要冲突存在，compile 就失败**，即使当前文件里没有任何地方引用这个 key。理由：

1. **防止静默语义漂移**。假设作者某天运行 `gaia cite import bell_papers.bib`，导入的 `.bib` 里恰好有一条 key 叫 `bell_lemma`，而本包已经有一个 claim 也叫 `bell_lemma`。在 warning-fallback 规则下，所有现存的 `[@bell_lemma]` 会从"本地锚点链接"**静默**变成"(Bell, 2020) 引文标记"，README 链接全断、provenance metadata 全错、只打印一行容易被忽略的 warning。fail-fast 彻底堵死这条回归路径。

2. **Warning 长期必然被忽略**。任何项目积累 warning 到一定数量后，作者就会系统性地无视它们。依赖 warning 做安全检查是设计漏洞。

3. **Collision 在正常 naming 下极少发生**。label 用小写蛇形、citation key 多数带数字或大写，自然不冲突。真碰上了，修复只需要改一个名字，成本可控。

4. **修复路径清晰**。作者只有两条选项：要么 rename 本地 claim 的 label，要么 rename references.json 里那条 entry 的 key。两条都是纯重命名操作，不涉及语义判断。

5. **CSL-JSON import 的碰撞检测顺便得到保护**。`gaia cite import refs.bib` 在 merge 到 references.json 时做一次 pre-check：若新增的 citation key 会和现有 label 冲突，import 本身就拒绝，提示作者先重命名。这样冲突永远不会污染到 committed 状态。

本 spec 不引入 qualifier 语法（比如 `[@label:foo]` / `[@cite:foo]`），理由是 collision 太罕见，不值得为它增加新的 grammar surface。

### 3.6 Escape

`\@` 强制把 `@` 当字面量：

```
"use the \@dataclass decorator"    → 不解析，渲染为 "use the @dataclass decorator"
"email me at foo\@bar.com"         → 不解析
```

注意：在大多数场景下 opportunistic 规则已经自动放过了这些假阳性，`\@` 是最后的保险。

## 4. `references.json` Format

### 4.1 格式选择：CSL-JSON

存储格式采用 **CSL-JSON**（Citation Style Language JSON），理由：

1. **事实标准** —— Zotero、Mendeley、Paperpile、Pandoc、Quarto、Manubot 全部用它作为交换格式
2. **`citeproc-py` 原生支持** —— 渲染时零解析工作
3. **类型丰富** —— 首等公民级别支持 webpage / software / dataset / preprint / thesis / report / patent 等
4. **比 BibTeX 干净** —— 无 LaTeX 转义、无 `@string` macro、无方言分歧
5. **Zotero 导出直接可用** —— 作者 "Export Items → CSL JSON" 即得

### 4.2 文件位置

```
<package_root>/references.json
```

### 4.3 Schema

顶层是一个以 citation key 为键的 dict（不是数组，因为我们需要按 key 快速查）：

```json
{
  "EPR1935": {
    "type": "article-journal",
    "title": "Can Quantum-Mechanical Description of Physical Reality Be Considered Complete?",
    "author": [
      {"family": "Einstein", "given": "A."},
      {"family": "Podolsky", "given": "B."},
      {"family": "Rosen", "given": "N."}
    ],
    "container-title": "Physical Review",
    "volume": "47",
    "issue": "10",
    "page": "777-780",
    "issued": {"date-parts": [[1935, 5, 15]]},
    "DOI": "10.1103/PhysRev.47.777"
  },
  "Bell1964": {
    "type": "article-journal",
    "title": "On the Einstein Podolsky Rosen Paradox",
    "author": [{"family": "Bell", "given": "J. S."}],
    "container-title": "Physics Physique Fizika",
    "volume": "1",
    "issue": "3",
    "page": "195-200",
    "issued": {"date-parts": [[1964]]},
    "DOI": "10.1103/PhysicsPhysiqueFizika.1.195"
  },
  "HossenfelderBlog2019": {
    "type": "post-weblog",
    "title": "What does it mean for a theory to be falsifiable?",
    "author": [{"family": "Hossenfelder", "given": "Sabine"}],
    "container-title": "Backreaction",
    "URL": "http://backreaction.blogspot.com/2019/...",
    "issued": {"date-parts": [[2019, 3, 14]]},
    "accessed": {"date-parts": [[2026, 4, 9]]}
  },
  "NumpyPackage": {
    "type": "software",
    "title": "NumPy",
    "author": [{"family": "Harris", "given": "Charles R."}],
    "version": "1.26.0",
    "URL": "https://numpy.org"
  }
}
```

**注意**：CSL-JSON 标准顶层是数组，每条带 `id`。我们采用 dict-by-key 形式是为了 O(1) 查表和更清晰的 merge 语义。Import / export 时互相转换。

### 4.4 支持的 CSL type

CSL 1.0.2 全部 type 都支持。Gaia 不做任何 type 限制或类型收窄。常用：

| type | 含义 |
|---|---|
| `article-journal` | 期刊论文 |
| `article` | 通用文章（含 preprint） |
| `paper-conference` | 会议论文 |
| `book` / `chapter` | 书 / 章节 |
| `thesis` | 学位论文 |
| `report` | 技术报告 / 白皮书 |
| `webpage` | 网页 |
| `post-weblog` | 博客文章 |
| `post` | 论坛 / 社交帖子 |
| `software` | 软件 / 库 |
| `dataset` | 数据集 |
| `patent` | 专利 |
| `personal_communication` | 私下交流 |
| `manuscript` | 未发表手稿 |

### 4.5 Validation

Compile 时对 `references.json` 做：

1. 必须是合法 JSON
2. 顶层必须是 object
3. **每个 top-level key 必须匹配 Pandoc `@`-syntax 的 key grammar**（同 §3.3）—— 不能包含空格、不能以标点结尾。否则这条 entry 根本不可能被引用，载入了也是废条目，直接 error
4. 每个 value 必须有 `type` 字段，且 type 必须是 CSL 1.0.2 合法 type
5. 每个 value 必须至少有 `title` 字段（最小可渲染要求）
6. 可选但推荐的字段：`author`、`issued`（出版日期）、`DOI` 或 `URL`

缺失可选字段不 error，只 warning —— CSL 样式会自己处理缺失字段。

**Key grammar 的 fail-fast 很重要**：如果 loader 接受 `"Bell 1964"` 这种带空格的 key，作者在 content 里写 `[@Bell 1964]` 时，extractor 只会抓到 `@Bell`，然后报一个关于 `Bell` 的 "unknown reference key" 错误 —— 作者会非常困惑，因为 `Bell 1964` 确实在 references.json 里。早期 fail 更好。

## 5. Rendering Pipeline

### 5.1 提取（compile 阶段）

Compile 时对每个 Knowledge 的 `content` 字段和每个 Strategy 的 `reason` 字段执行：

```python
# 伪代码
def extract_refs(text: str) -> list[RefMarker]:
    markers = []
    # Pass 1: 找所有 [...] 含 @ 的片段（strict form）
    for match in BRACKETED_RE.finditer(text):
        markers.extend(parse_pandoc_group(match, strict=True))
    # Pass 2: 找所有裸 @key（opportunistic form）
    for match in BARE_AT_RE.finditer(text):
        if not inside_bracket(match) and not escaped(match):
            markers.append(RefMarker(key=match.group(1), strict=False))
    return markers
```

Regex 定义：

```python
# 一个完整的 Pandoc 引用组
_BRACKETED_REF_RE = re.compile(
    r"""
    (?<!\\)            # 前面不能是反斜杠
    \[                 # 左括号
    ([^\[\]]*          # 内部不能嵌套方括号
     @[A-Za-z0-9_]     # 至少有一个 @key
     [^\[\]]*)
    \]
    """,
    re.VERBOSE,
)

# 裸 @key，Pandoc 兼容字符集
_BARE_AT_RE = re.compile(
    r"""
    (?<!\\)            # 前面不能是反斜杠
    (?<![A-Za-z0-9_])  # 前面不能是 word char（排除 email 里的 foo@bar）
    @
    ([A-Za-z0-9_]      # 首字符合法
     [A-Za-z0-9_:.#$%&+?<>~/-]*
     [A-Za-z0-9_])?    # 不能以标点结尾
    """,
    re.VERBOSE,
)
```

**裸 `@` 的 `(?<![A-Za-z0-9_])` 前瞻**：排除 `foo@bar.com` 里的 `@bar`（`o` 是 word char）。这是一个无代价的硬性过滤，和 opportunistic 规则不冲突。

**Group membership invariant**：如果实现把 `ExtractionResult.markers` 在 Pass 2 之后按 source position 排序（便于下游按顺序处理），**必须在 sort 完成后重新计算 `BracketGroup.marker_indices`**。简单的做法：Pass 1 里用 `RefMarker` 对象本身而不是 list 索引记录 group 成员，sort 之后通过 `{id(m): i for i, m in enumerate(markers)}` 重建索引。如果 Pass 1 里记录了数值索引然后又 sort 了 markers，group indices 会在 Pass 2 追加裸 marker 的时候静默失效，导致 `validate_groups` 报 false-positive mixed-group error（或更糟：把真的 mixed group 漏掉）。

### 5.2 Resolve

**Pre-compile 全局 collision 检查**（§3.5 的 fail-fast 在这里实现）：

```python
def check_collisions(
    label_table: dict[str, Knowledge],
    references: dict[str, dict],
) -> None:
    """Must run once per compile, before any marker resolution."""
    collisions = set(label_table) & set(references)
    if collisions:
        raise CompileError(
            f"ambiguous reference keys: {sorted(collisions)}. "
            f"rename one of the conflicting knowledge labels or citation keys."
        )
```

Collision check 通过后，单个 marker 的 resolve 就只剩三状态：

```python
def resolve(
    key: str,
    label_table: dict[str, Knowledge],
    references: dict[str, dict],
) -> Literal["knowledge", "citation", "unknown"]:
    if key in references:
        return "citation"
    if key in label_table:
        return "knowledge"
    return "unknown"
```

注意 `label_table` 此时已经是**当前 package 编译 closure**（含 imported foreign nodes），见 §3.1。

**Homogeneous-group check**（§3.2 的规则在这里实现）：

```python
def validate_group(
    group: BracketedGroup,
    label_table: dict[str, Knowledge],
    references: dict[str, dict],
) -> None:
    """A bracketed group must contain only knowledge refs or only citations."""
    kinds = {resolve(key, label_table, references) for key in group.keys}
    kinds.discard("unknown")  # unknown keys handled separately below
    if kinds == {"knowledge", "citation"}:
        raise CompileError(
            f"mixed-type reference group at {group.location}: "
            f"split into separate bracketed groups."
        )
```

**单个 marker 的 disposition**：

| strict | 结果 | 处理 |
|---|---|---|
| True  | `knowledge` | OK，记入 provenance |
| True  | `citation`  | OK，记入 provenance |
| True  | `unknown`   | **ERROR**，阻断 compile |
| False | `knowledge` | OK，记入 provenance |
| False | `citation`  | OK，记入 provenance |
| False | `unknown`   | 静默，marker 当字面量 |

（`conflict` 已在 pre-compile 阶段 fail，不会走到这里。）

### 5.3 Provenance 记录

Compile 成功的 marker 被写入对应节点的 metadata：

```python
knowledge.metadata["gaia"]["provenance"] = {
    "cited_refs": ["EPR1935", "Bell1964"],           # citation keys
    "referenced_claims": ["main_theorem", "lemma_a"], # knowledge labels
}
```

这给 LKM 层提供了两种跨包查询：

- "哪些 claim 引用了 Bell 1964？"
- "哪些 claim 提到了 main_theorem？"

### 5.4 渲染（README 生成阶段）

`gaia compile --readme` 生成 README.md 时，管线按 "是否在 `[...]` 组内 + 组是哪种类型" 分成三种 substitution class。因为 §3.2 的 homogeneous-group 规则保证**每个 `[...]` 组要么是 pure knowledge，要么是 pure citation**，管线不需要处理"半个 group"或"组内交错"情况。

**Step 1 —— 分类扫描**

对 content / reason 字符串执行一次扫描，把所有引用标记切成三类 token：

- `KR_GROUP`：整个 `[...]` 组，组内所有 key 都是 knowledge ref
- `CITE_GROUP`：整个 `[...]` 组，组内所有 key 都是 citation
- `KR_BARE`：裸 `@key` 且解析成 knowledge ref
- `CITE_BARE`：裸 `@key` 且解析成 citation（opportunistic）

标记之外的文本原样保留。mixed group 和 strict-unknown 在 §5.2 已经被拦截，这里不会出现。

**Step 2 —— 把 knowledge 类的标记替换成占位符**

对 `KR_GROUP` 和 `KR_BARE` 都替换成不可能出现在正文里的占位符，给每个占位符分配一个 id：

```
"As [@lemma_a] shows, and @lemma_b supports it, ..."
→ "As {{GAIA_KR_001}} shows, and {{GAIA_KR_002}} supports it, ..."
```

占位符内容 `{{GAIA_KR_NNN}}` 不含 `@` 和方括号，所以不会被 citeproc-py 误识别为 citation 语法。

**Step 3 —— 把剩下的文本交给 citeproc-py**

此时文本里只剩 `CITE_GROUP` 和 `CITE_BARE`（以及占位符和普通文本）。citeproc-py 完整继承 Pandoc 语法，处理所有 prefix / locator / suffix / multi-item / narrative / parenthetical / suppress-author 变体：

```python
import citeproc
bib = citeproc.CitationStylesBibliography(
    style=citeproc.CitationStylesStyle("apa"),
    source=citeproc.source.json.CiteProcJSON(references_list),
    formatter=citeproc.formatter.html,
)
rendered_text = process_with_citeproc(text_with_placeholders, bib)
```

citeproc-py 吐出：格式化后的 citation 文本 + 最终的 `## References` 段落。占位符原样保留（它们对 citeproc 是普通字符串）。

**Step 4 —— 回填 knowledge ref 占位符**

对每个 `{{GAIA_KR_NNN}}` 占位符，按 Step 1 记录的原始 token 渲染成 Markdown：

- `KR_BARE` (`@lemma_a`) → `[A missing lemma](#lemma_a)`
- `KR_GROUP` (`[@lemma_a; @lemma_b]`) → `([A missing lemma](#lemma_a); [Another lemma](#lemma_b))`
- 带 prefix/locator 的纯 knowledge 组 → 按类似 Pandoc 的方式合成字符串，因为 Gaia 这部分由我们自己渲染，不经过 citeproc

锚点 anchor text 使用 claim 的 `content` 前 N 个字符，或 `title`（如果定义了）。

**为什么这个管线在 homogeneous-group 规则下是安全的**

假设允许混合组，那么 `[see @lemma_a; @Bell1964, p. 5]` 在 Step 2 之后会变成 `[see {{GAIA_KR_001}}; @Bell1964, p. 5]` —— citeproc 看到这是一个以 `[` 开头、内含 `@Bell1964` 的 group，会尝试按 Pandoc group 解析，但 `{{GAIA_KR_001}}` 不是合法 Pandoc 语法，结果未定义（citeproc 可能当 prefix 文本、可能 parse 失败、可能把整段当字面量）。group-level 的 `see` prefix 归哪个 item 也没有合理答案。

homogeneous-group 规则把这种情况在 Step 1 之前就 compile-error 掉，Step 2 面对的每个 `[...]` 组要么整个是 knowledge（直接变占位符），要么整个是 citation（完全不动），citeproc 永远不会收到被占位符污染的 group。这是管线正确性的关键前提。

### 5.5 CSL 样式

默认使用 APA 7th edition。作者可在 `pyproject.toml` 指定：

```toml
[tool.gaia.references]
style = "nature"   # apa | mla | chicago | nature | ieee | ...
```

Gaia 内置打包几个常用样式（`.csl` XML 文件），用户也可以指定路径到自定义样式。

## 6. No DOI Auto-Completion (Rationale)

本 spec **明确不引入** `cite("doi:10.1103/PhysRev.47.777")` 这种"从 DOI 自动补全 CSL-JSON"的特性。理由：

1. **工作流已经解决** —— 做研究的作者几乎都用 Zotero / Mendeley 管文献，DOI lookup 在那边已经发生过，Zotero 的"Export → CSL JSON"直接拿到完整记录
2. **Compile 网络副作用** —— 在 `gaia compile` 路径里调 Crossref API 会引入：
   - 离线 / CI / 防火墙下的失败模式
   - Crossref 限流
   - 可重复性问题（今天 compile 和下个月 compile 可能拿到不同 metadata）
3. **缓存复杂度** —— 要定义缓存 commit 策略、失效规则、冲突处理
4. **额外依赖** —— `manubot` / `habanero` 拉 `requests`/`lxml` 等运行时依赖
5. **只有"少打字"一个收益**，代价远大于收益

如果真有需求，可以提供一个**独立的 authoring-time 命令** `gaia cite add <doi>`，它是一次性网络操作，把结果写入 `references.json`。这样网络副作用被关进显式工具里，不污染 compile 路径。本 spec **不包含** 这个命令的设计，留待独立 spec。

## 7. BibTeX Import (`gaia cite import`)

虽然内部格式是 CSL-JSON，BibTeX 在物理 / 数学 / CS 圈是既成事实（arXiv / APS / Nature / Google Scholar 的"Cite"按钮默认输出 `.bib`），所以提供一个**一次性 import 命令**：

```bash
# 批量导入
gaia cite import refs.bib

# 从 stdin
pbpaste | gaia cite import --stdin --format bibtex

# 从 CSL-JSON 导入（Zotero 导出的合并）
gaia cite import zotero-export.json
```

### 7.1 行为

1. 读 `.bib` 文件，用 `bibtexparser` (v2) 解析
2. 逐条转换成 CSL-JSON（字段映射 + LaTeX 反转义）
3. Merge 到 `references.json`：
   - 新 key → 直接添加
   - 已存在 key → 默认报错，`--force` 覆盖
4. 对字段不全的条目打 warning（"建议补充 author"）

### 7.2 转换的不完美性

`.bib → CSL-JSON` 不是完全无损：

- `@misc` / `@techreport` 到 CSL `type` 的映射有歧义
- 特别奇怪的 LaTeX 宏需要人工修
- 非西文名字（中文 / 日文 / 阿拉伯文）的 family/given 切分可能错

这些都是**一次性代价**：作者 import 后手动修几条就永远干净了。相比在 compile 路径里每次都 parse BibTeX，靠谱得多。

### 7.3 依赖

- `bibtexparser` v2（纯 Python，轻量）
- **只在 CLI 的 `cite import` 子命令里 import**，不污染 compile 路径

## 8. Migration

本 spec 的 grammar 设计保证**现有 strategy reason 里的 `@label` 不需要批量迁移**：

1. 现有 `@label` 继续解析成 "opportunistic reference"
2. Resolve 时查统一符号表 —— 符号表包含**当前 package 编译 closure 的全部 knowledge 节点（含 imported foreign nodes）**，与现有 compiler 的 `label_to_id` 行为一致，详见 §3.1
3. 现有 warning-on-miss 的行为改成 opportunistic 的"静默放过"

**特别重要**：cross-package `@label` 引用必须保持工作。作者写 `from package_a import key_missing_lemma` 然后在 reason 里写 `@key_missing_lemma`，这条语义在本 spec 下**严格不变**，因为符号表继承了现有 compiler 的 closure 行为。

作者可以自愿把现有裸 `@foo` 升级成 `[@foo]` 来获得 strict 语义，但不是强制的。

### 8.1 Compile 行为变化

| 场景 | 旧行为 | 新行为 |
|---|---|---|
| strategy reason 里 `@label`（本地命中） | 记入 provenance | 同上 |
| strategy reason 里 `@label`（imported 命中） | 记入 provenance | 同上 |
| strategy reason 里 `@foo`（未命中） | warning | 静默（符合 opportunistic） |
| claim content 里 `@label`（命中） | 不解析 | opportunistic 解析，记 provenance |
| claim content 里 `@foo`（未命中） | 不解析 | 静默字面量 |
| claim content 里 `[@label]`（命中） | 不解析 | **strict 解析，记 provenance** |
| claim content 里 `[@label]`（未命中） | 不解析 | **strict 解析，ERROR** |
| strategy reason 里 `[@label]`（命中） | 当作字面量 | **strict 解析，记 provenance** |
| strategy reason 里 `[@label]`（未命中） | 当作字面量 | **strict 解析，ERROR** |
| `\@foo` | 不识别，warning | 字面量，不解析 |
| label 与 citation key 冲突 | N/A（旧版无 citation） | **ERROR** (§3.5) |
| 混合类型 bracketed group | N/A | **ERROR** (§3.2) |

**潜在破坏性**：

1. strategy reason 里已有 `[@foo]`（极少见）—— 如果真存在，现在会被 strict 解析；实现时 grep 现有仓库与已发布 package 验证
2. 现有 `@foo`（未命中的裸形式）旧版会产生 warning，新版静默 —— 对 CI 可能是 noise 降低，对依赖 warning 做 typo 审计的作者是信号丢失。缓解：提供 `gaia lint --refs` 命令主动列出未命中（§8.2）
3. 如果现有已发布 package 已经碰巧存在本地 label 与未来导入的 citation key 同名的情况，首次引入 references.json 时会触发 §3.5 collision error；这是**期望行为**，不是回归

### 8.2 辅助 lint 命令

为了帮作者审视现有代码：

```bash
gaia lint --refs
```

扫描所有 `.py` 文件的 claim/setting/question content 和 strategy reason：

1. 列出所有 opportunistic 命中和未命中
2. 对未命中（opportunistic 下会静默放过）的 `@foo`，提示作者："这看起来像一个引用但没找到，是否是 typo？"
3. 可选建议："把 `@foo` 升级成 `[@foo]` 以获得 strict 语义"

这是一个**纯建议工具**，不改代码，不 fail compile。

## 9. Non-Goals

以下**不在本 spec 范围**，留待独立 spec：

- **DOI 自动补全**（详见 §6）
- **Cross-package reference**：`[@other_package::lemma]` 这种跨包引用语法。本 spec 只处理本包 label 和本包 references.json。grammar 保留扩展空间（`::` 已经在 Pandoc 合法字符集里），但语义和 resolver 不在本 spec 定义
- **Narrative rendering for knowledge refs**：Pandoc narrative form `@Bell1964` 对 citation 有 "Bell (1964)" 渲染，对 knowledge ref 只是 "inline link"。本 spec 不定义 knowledge ref 的 narrative vs parenthetical 区分
- **Bibliography 静态网站生成**：本 spec 只管 README 渲染，不涉及独立的 bibliography 页面
- **Citation style 热切换 / 多样式并存**：一次 compile 一种样式
- **Review pipeline 对 citation 的验证**：比如"LKM 层验证这篇 Bell 1964 的 DOI 可访问" —— 不在本 spec

## 10. Implementation Checklist

为后续实现 PR 提供的任务清单：

- [ ] `gaia/lang/refs/extractor.py` —— 统一的 marker 提取器（BRACKETED_REF_RE + BARE_AT_RE），额外记录每个 bracketed group 的 key list 与源位置，供 §5.2 的 `validate_group` 使用
- [ ] `gaia/lang/refs/resolver.py` —— 三状态 resolver（knowledge / citation / unknown）+ `check_collisions` pre-compile check + `validate_group` homogeneous check
- [ ] `gaia/lang/refs/loader.py` —— `references.json` 读取 + schema validation
- [ ] 修改 `gaia/lang/compiler/compile.py`:
  - 删除旧的 `_AT_LABEL_RE` / `_extract_at_labels` / `_validate_at_labels`
  - 符号表沿用现有 `label_to_id`（compile closure，含 imported foreign nodes），**不得**收窄为 local-only
  - 在 compile 入口做一次 global `check_collisions(label_table, references)`，冲突 → error
  - 替换成统一 extractor + resolver 调用
  - 扩大扫描范围到所有 Knowledge content 字段，不仅 strategy reason
  - 每个 bracketed group 过 `validate_group`，混合类型 → error
  - 实现 strict / opportunistic 的不同严格度
  - 在 Knowledge metadata 里写入 `provenance.cited_refs` / `provenance.referenced_claims`
- [ ] 修改 `gaia/cli/commands/cite.py` 的 import 命令：
  - Merge references.json 前 pre-check 新 key 与 label 的冲突，冲突 → 拒绝 import 并提示重命名
- [ ] `gaia/cli/commands/cite.py` —— `gaia cite import` 子命令
- [ ] `gaia/cli/commands/lint.py` —— `gaia lint --refs` 子命令
- [ ] 修改 `gaia/lang/compiler/readme.py`:
  - 集成 `citeproc-py` 渲染管线
  - Knowledge ref 占位符替换流程
  - Bibliography 段落生成
- [ ] 依赖更新 `pyproject.toml`:
  - `citeproc-py` (runtime)
  - `bibtexparser >= 2.0` (optional, 只在 `gaia cite import` 时需要)
- [ ] 内置 CSL 样式文件：`gaia/lang/refs/styles/*.csl` (apa, ieee, nature, chicago)
- [ ] Tests:
  - `tests/gaia/lang/refs/test_extractor.py` —— 含裸 `@` / 括号 / `[-@]` / prefix / locator / suffix / multi-item / `\@` 转义
  - `tests/gaia/lang/refs/test_resolver.py` —— 含三态 resolve、`check_collisions`、`validate_group` 混合类型
  - `tests/gaia/lang/refs/test_loader.py`
  - `tests/cli/test_cite_import.py` —— 含 pre-check 拒绝与 label 冲突的新 citation key
  - `tests/gaia/lang/compiler/test_at_syntax.py` (end-to-end) 必须覆盖：
    - **Imported foreign node ref**：`from pkg_a import lemma_x` 后 `@lemma_x` 在 strategy reason 和 claim content 里都能 resolve 到 foreign QID（回归测试，protect 现有 workflow）
    - **混合组 compile error**：`[see @local_lemma; @Bell1964, p. 5]` 报 mixed-type error
    - **Collision compile error**：同时存在本地 label `bell_lemma` 和 references.json 中 `bell_lemma` 时 compile 失败
    - **strict miss error**：`[@no_such_thing]` 报 unknown-reference error
    - **opportunistic miss silent**：`@no_such_thing` 当字面量，不报错
    - **Provenance 记录**：resolve 成功的 marker 写入 `metadata["gaia"]["provenance"]["cited_refs"]` / `referenced_claims`
- [ ] 更新文档：
  - `docs/foundations/gaia-lang/` 里补充 reference syntax 章节
  - `docs/foundations/gaia-lang/` 里补充 `references.json` 约定
- [ ] Skill 更新：`paper-formalization` skill 里提示作者在 content 中用 `[@Key]` 引用，本包内 knowledge 用 `[@label]`
