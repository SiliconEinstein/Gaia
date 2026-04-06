# Claude Skills Distribution Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write 3 Claude Code skills (gaia-cli, gaia-lang, formalization) and distribute them via the Gaia repo as a Claude Code marketplace plugin.

**Architecture:** The Gaia repo doubles as a Claude Code marketplace (like `kepano/obsidian-skills`). `.claude-plugin/` contains both `marketplace.json` and `plugin.json`. Skills live at repo root `skills/`. Users install with `/plugin marketplace add SiliconEinstein/Gaia` then `/plugin install gaia@gaia-marketplace`.

**Tech Stack:** SKILL.md (Claude Code skill format), `.claude-plugin/` marketplace convention

---

## File Structure

| File | Responsibility |
|------|---------------|
| `.claude-plugin/marketplace.json` | Marketplace catalog (already exists) |
| `.claude-plugin/plugin.json` | Plugin metadata (already exists) |
| `skills/gaia-cli/SKILL.md` | CLI toolchain: install, init, compile, check, infer, register, review sidecar, package structure |
| `skills/gaia-lang/SKILL.md` | DSL syntax: claim/setting/question, operators, strategies, module organization, exports |
| `skills/formalization/SKILL.md` | Four-pass formalization methodology (references gaia-cli and gaia-lang) |

---

## Chunk 1: Write the three skills

### Task 1: Write gaia-cli skill

**Files:**
- Create: `skills/gaia-cli/SKILL.md`

- [ ] **Step 1: Write gaia-cli SKILL.md**

Content (extract from README tutorial + gaia-ir-authoring skill):

1. **Install** — `pip install gaia-lang`, verify with `gaia --help`
2. **gaia init** — scaffold package, naming convention (repo `CamelCase.gaia`, PyPI `kebab-case-gaia`, import `snake_case`), directory structure, `[tool.gaia]` config
3. **gaia compile** — DSL → IR, produces `.gaia/ir.json` + `.gaia/ir_hash`
4. **gaia check** — validation, common errors
5. **gaia infer** — review sidecar requirement, algorithm selection (JT vs loopy BP), output location
6. **gaia compile --readme** — README generation with Mermaid graph + belief values
7. **gaia register** — git tag, registry PR workflow
8. **Review sidecar** — file location (`reviews/`), `ReviewBundle`, `review_claim` (prior, judgment, justification), `review_strategy` (conditional_probability), `review_generated_claim`
9. **Package structure** — `pyproject.toml` fields, `src/` layout, `artifacts/`, `.gaia/`, `.gitignore` patterns
10. **Workflow diagram** — init → compile → check → review → infer → readme → register

Source material:
- `README.md` "Create a Knowledge Package" section (steps 1-7)
- `gaia-ir-authoring` skill steps 1, 6-9
- `docs/foundations/gaia-lang/dsl.md` (package structure parts)

- [ ] **Step 2: Verify frontmatter is valid**

```bash
head -5 skills/gaia-cli/SKILL.md
# Must show: ---\nname: gaia-cli\ndescription: ...\n---
```

- [ ] **Step 3: Commit**

```bash
git add skills/gaia-cli/SKILL.md
git commit -m "feat(skills): add gaia-cli skill — CLI toolchain reference"
```

### Task 2: Write gaia-lang skill

**Files:**
- Create: `skills/gaia-lang/SKILL.md`

- [ ] **Step 1: Write gaia-lang SKILL.md**

Content (extract from `docs/foundations/gaia-lang/dsl.md` + gaia-ir-authoring steps 2-5):

1. **Knowledge types** — `claim()` full signature (content, given, background, parameters, provenance), `setting()`, `question()`. When to use each. `given=` sugar for noisy_and.
2. **Operators** — `contradiction(a, b)`, `equivalence(a, b)`, `complement(a, b)`, `disjunction(*claims)`. Signatures, semantics, returned helper claim. `reason=` parameter.
3. **Strategies** — All strategy functions with signatures and when to use:
   - Direct: `noisy_and`, `infer`
   - Named: `deduction`, `abduction`, `analogy`, `extrapolation`, `elimination`, `case_analysis`, `mathematical_induction`
   - Composite: `induction`, `composite`
   - Key distinction: deduction (strict math) vs noisy_and (any uncertainty)
4. **Module organization** — one module per chapter/section, `__init__.py` re-exports, cross-module imports, docstring as module title
5. **Exports** — `__all__` semantics: exported (cross-package interface), public (visible to review), private (`_` prefix)
6. **Labels** — auto-assigned from variable names by `gaia compile`, never set manually
7. **Anti-patterns** — HARD-GATE list: no `Package()`, no manual `.label`, no setting/question as premises, no single-premise deduction, no `FormalExpr` by hand, no `gaia.gaia_ir` import, correct `[build-system]`

Source material:
- `docs/foundations/gaia-lang/dsl.md` (primary — full API reference)
- `gaia-ir-authoring` skill steps 2-5 + anti-patterns

- [ ] **Step 2: Verify frontmatter is valid**

- [ ] **Step 3: Commit**

```bash
git add skills/gaia-lang/SKILL.md
git commit -m "feat(skills): add gaia-lang skill — DSL syntax reference"
```

### Task 3: Rewrite formalization skill

**Files:**
- Modify: `skills/formalization/SKILL.md`

- [ ] **Step 1: Update formalization SKILL.md**

Changes to existing content:
- Replace `**REQUIRED:** Use gaia-ir-authoring for...` → `**REQUIRED:** Use gaia-cli skill for CLI commands and gaia-lang skill for DSL syntax.`
- Remove IR-level references (FormalExpr, formalize, etc.)
- All CLI commands say "see gaia-cli skill"
- All DSL syntax says "see gaia-lang skill"
- Keep all formalization methodology intact (Pass 0-4, review sidecar, BP interpretation, common mistakes)
- Translate remaining Chinese text to English for international users

- [ ] **Step 2: Verify frontmatter is valid**

- [ ] **Step 3: Commit**

```bash
git add skills/formalization/SKILL.md
git commit -m "feat(skills): rewrite formalization skill — reference gaia-cli and gaia-lang"
```

---

## Chunk 2: Debug and fix marketplace install

### Task 4: Investigate why `/plugin install` fails

- [ ] **Step 1: Compare our structure with obsidian-skills byte-for-byte**

Clone obsidian-skills and diff the `.claude-plugin/` structure:

```bash
cd /tmp && gh repo clone kepano/obsidian-skills
diff <(jq . /tmp/obsidian-skills/.claude-plugin/marketplace.json) \
     <(jq . /Users/kunchen/project/Gaia/.claude-plugin/marketplace.json)
diff <(jq . /tmp/obsidian-skills/.claude-plugin/plugin.json) \
     <(jq . /Users/kunchen/project/Gaia/.claude-plugin/plugin.json)
```

- [ ] **Step 2: Test install from OUTSIDE the Gaia repo**

The previous tests were done while working inside the Gaia repo. Test from a clean directory:

```bash
cd /tmp && mkdir test-install && cd test-install
claude
# Then: /plugin marketplace add SiliconEinstein/Gaia
# Then: /plugin install gaia@gaia-marketplace
```

- [ ] **Step 3: Check if the issue is marketplace caching**

```bash
# In Claude Code:
/plugin marketplace list
# Check if gaia-marketplace shows, then:
/plugin  # Use interactive UI to browse marketplace
```

- [ ] **Step 4: Fix any issues found and push**

- [ ] **Step 5: Verify install works**

```bash
# From a non-Gaia directory in Claude Code:
/plugin marketplace remove gaia-marketplace
/plugin marketplace add SiliconEinstein/Gaia
/plugin install gaia@gaia-marketplace
/gaia:formalization  # Should load the skill
```

- [ ] **Step 6: Commit any fixes**

### Task 5: Update README

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Update Claude Code Plugin section**

Replace current install instructions with verified working commands from Task 4.

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs(readme): update Claude Code skill install instructions"
```

### Task 6: Clean up old project-level skills

**Files:**
- Delete: `.claude/skills/paper-formalization/SKILL.md` (replaced by `skills/formalization/`)
- Keep: `.claude/skills/gaia-ir-authoring/SKILL.md` (developer-only, not distributed)

- [ ] **Step 1: Remove old skill**

```bash
rm -rf .claude/skills/paper-formalization
```

- [ ] **Step 2: Commit**

```bash
git add -A
git commit -m "chore: remove old paper-formalization skill — replaced by plugin skill"
```

### Task 7: Push and create PR

- [ ] **Step 1: Run linting**

```bash
ruff check .
ruff format --check .
```

- [ ] **Step 2: Push and create PR**

```bash
git push origin HEAD
gh pr create --title "feat: gaia-cli + gaia-lang + formalization Claude Code skills"
```

- [ ] **Step 3: Verify CI passes**

```bash
gh run list --branch $(git branch --show-current) --limit 1
```
