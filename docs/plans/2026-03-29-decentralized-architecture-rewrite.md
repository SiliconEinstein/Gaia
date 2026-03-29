# Decentralized Architecture Doc Rewrite Plan

> **For agentic workers:** REQUIRED: Use superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rewrite `docs/foundations/ecosystem/03-decentralized-architecture.md` as a proper architecture overview with layer-by-layer explanation and end-to-end business flow narrative, removing details that belong in sub-documents (04-07).

**Architecture:** Single-file rewrite of 03, plus minor cross-reference updates to 02 (vocabulary) and 04 (authoring). The Mermaid diagram is retained with multi-instance annotations. No code changes.

**Spec:** `docs/specs/2026-03-29-decentralized-architecture-redesign.md`

---

## Chunk 1: Rewrite 03-decentralized-architecture.md

### Task 1: Write the new document

**Files:**
- Modify: `docs/foundations/ecosystem/03-decentralized-architecture.md` (full rewrite)

The new document follows this exact structure. Each section's content is specified in the spec; the full text is provided below.

- [ ] **Step 1: Read the current file**

Read `docs/foundations/ecosystem/03-decentralized-architecture.md` to confirm current state.

- [ ] **Step 2: Write the new document**

Replace the entire contents of `03-decentralized-architecture.md` with the following structure:

```markdown
# 去中心化架构

> **Status:** Current canonical

本文档是 Gaia 去中心化架构的总纲——参与者、基础设施、以及从包创建到证据汇聚的完整业务流转。各环节的展开详见 04-07。

## 参与者与基础设施

[六类实体表 — spec §2]
[两个关键设计点]

## Git 作为通用交互面

[简述 git 交互，不绑定 GitHub — spec §3]

## 架构图

[现有 Mermaid 图，微调多实例标注 — spec §4]
[连线说明表]

## 架构分层

[逐层递进叙事 — spec §5]
### 纯包层：两个 git 仓库就能推理
### + Review Server：推理链获得可信参数
### + Official Registry：证据开始汇聚
### + LKM Server：全局推理与跨包关系发现

## 端到端业务流转

[Alice 场景串联 — spec §6]
### 主线：包从创建到证据汇聚
### 支线：社区协作
### 错误修正

## 设计原则

[精简原则表 — spec §7]

## 各环节详解

[04-07 链接]

## 参考文献

[00-pipeline-overview, 01-product-scope 链接]
```

Content guidelines for each section:

**参与者与基础设施：**
- Use the six-entity table from the spec exactly (LKM Server ×N, Review Server ×N, LKM Repo ×N)
- Two key design points as bullet points
- Do NOT include the old "两类贡献者" comparison table or "Review Server 的定位" subsection

**Git 作为通用交互面：**
- Keep the current text but trim to essentials (no participant interaction table — that's redundant with the architecture diagram)

**架构图：**
- Keep the current Mermaid `flowchart TB` diagram
- Update node labels: `RS(["⚙ Review Server ×N"])` → already correct; `LKM(["🖥 LKM Server ×N"])` add ×N; `LKMR["🔬 LKM Repo ×N"]` add ×N
- Keep connection description table
- Do NOT change the diagram layout or styling

**架构分层：**
- Four subsections, each with: what this layer does, what capabilities it adds, what limitations remain
- "纯包层" must include dependency pointing: registered → Registry identifier; unregistered → git URL + tag
- Each subsection is 4-8 lines of prose, not bullet-heavy
- Do NOT include detailed flows (those are in 04-07)

**端到端业务流转：**
- Use Alice's superconductivity package as the running example
- Seven numbered steps (① through ⑦) in the main flow, each with a one-line description and a "→ 详见 0x" reference
- Expand each step to 2-3 sentences (more than the spec's one-liner, but less than 04-07's full treatment)
- "支线：社区协作" — three bullet points
- "错误修正" — four bullet points with "→ 详见 07"

**设计原则：**
- Use the nine-row table from the spec exactly
- No additional prose

**各环节详解：**
- Four links to 04-07 with one-line descriptions

**参考文献：**
- Two links: 00-pipeline-overview, 01-product-scope

- [ ] **Step 3: Verify no Gaia IR terminology leaked in**

Grep the rewritten file for IR-layer terms that should not appear: `RawGraph`, `LocalCanonicalGraph`, `GlobalCanonicalGraph`, `FactorNode`, `variable node`, `factor node`, `ir.json`, `ir_hash` (except in the compilation subsection where `ir_hash` is mentioned for CI verification — check if it's there and remove if so; that detail belongs in 04/05).

- [ ] **Step 4: Verify all cross-reference links are valid**

Check that every `[...](...)` link in the file points to an existing file with the correct relative path.

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/ecosystem/03-decentralized-architecture.md
git commit -m "docs(ecosystem): rewrite 03-decentralized-architecture as architecture overview

Add layer-by-layer architecture explanation and end-to-end business
flow narrative (Alice scenario). Remove details that belong in
sub-documents (04-07): TOML examples, curation two-stage flow,
open questions comparison table, three candidate types.

Spec: docs/specs/2026-03-29-decentralized-architecture-redesign.md"
```

### Task 2: Update cross-references in other docs

**Files:**
- Modify: `docs/foundations/ecosystem/02-domain-vocabulary.md` (update LKM Repo entry)
- Modify: `docs/foundations/ecosystem/04-authoring-and-publishing.md` (update reference to 03)

- [ ] **Step 1: Update 02-domain-vocabulary.md**

The LKM Repo entry currently says "LKM Server 的运营仓库" (singular). Update to reflect that each LKM has its own repo:

Old:
```
LKM Server 的运营仓库。通过 Issues 管理 research tasks——LKM 在全局推理中发现的候选关系（equivalence、contradiction、connection）的发布、调查和分拣。人类研究者可浏览和参与。
```

New:
```
各 LKM Server 各自维护的运营仓库。通过 Issues 管理该 LKM 的 research tasks——在全局推理中发现的候选关系（equivalence、contradiction、connection）的发布、调查和分拣。人类研究者可浏览不同 LKM 的 repo 寻找研究机会。
```

- [ ] **Step 2: Check 04-authoring-and-publishing.md reference**

Line 185 references "03-decentralized-architecture.md 中的 LKM Repo 和 Open Questions". The rewritten 03 still covers these topics (in "架构分层 > + LKM Server" and "端到端业务流转 > 支线：社区协作"), so the link remains valid. No change needed unless the wording feels misleading — read and verify.

- [ ] **Step 3: Check 06 and 07 references**

`06-review-and-curation.md:262` and `07-belief-flow-and-quality.md:339` reference 03. Both are file-level links with generic descriptions ("架构总纲"). These remain accurate. No change needed.

- [ ] **Step 4: Commit**

```bash
git add docs/foundations/ecosystem/02-domain-vocabulary.md
git commit -m "docs(ecosystem): update LKM Repo vocabulary to reflect ×N instances"
```

### Task 3: Final verification

- [ ] **Step 1: Read the rewritten 03 end-to-end**

Read the full document and verify:
1. Every spec section (§1-§8) is present
2. No content from the "砍掉的内容" table leaked back in
3. No Gaia IR terminology present
4. The tone is overview-level, not detail-level
5. Every "详见 0x" reference points to the correct sub-document

- [ ] **Step 2: Verify Mermaid diagram renders**

The Mermaid diagram should be syntactically valid. Check that `×N` in node labels doesn't break rendering — if it does, use `xN` or spell out `(multiple)`.

- [ ] **Step 3: Push**

```bash
git push
```
