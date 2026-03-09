---
name: gitflow
description: "Git flow assistant for team development. Use when the user says /gitflow, asks about git conventions, wants to create/merge a PR, or needs help with branching/commit/review workflow. Can also be triggered by 'create PR', 'merge PR', '合并PR', 'git规范', 'PR怎么写'."
---

# Git Flow Assistant

Team git workflow assistant based on the conventions in `Notes/Git Flow 团队开发规范.md`.

## Capabilities

This skill has four modes: **PR creation**, **PR merge**, **convention lookup**, and **issue management**.

## Mode 1: PR Creation (`/gitflow pr` or "帮我提PR")

Guide the user through creating a PR that follows team conventions:

### Steps

1. **Pre-flight checks** (run BEFORE anything else)
   ```bash
   # Lint check
   ruff check .
   # Format check
   ruff format --check .
   ```
   - If either fails, **auto-fix** (`ruff check --fix .` then `ruff format .`), stage the fixes, and commit as `chore: fix lint/format violations`
   - Confirm all checks pass before proceeding

2. **Check current branch state**
   ```bash
   git branch --show-current
   git log main..HEAD --oneline
   git diff main --stat
   ```

3. **Validate against conventions**
   - Is the branch named correctly? (`feature/模块-描述` or `hotfix/描述`)
   - Is it rebased on latest main? If not, remind to rebase
   - Is the diff size reasonable? (warn if >3 days of work / very large diff)

4. **Check pinned issues for relevant checklist items**
   ```bash
   # Fetch pinned issues via GraphQL
   gh api graphql -f query='{ repository(owner:"SiliconEinstein", name:"Gaia") { pinnedIssues(first:5) { nodes { issue { number title body } } } } }'
   ```
   - Parse checklist items (`- [ ]` and `- [x]`) from pinned issues
   - Check if this PR addresses any unchecked items
   - If yes, note which items this PR covers — they will be checked off after merge

5. **Create or link a GitHub issue**
   - Search open issues for a matching one:
     ```bash
     gh issue list --state open --limit 30
     ```
   - If a matching issue exists, ask the user to confirm linking to it
   - If no matching issue exists, **auto-create** one:
     ```bash
     gh issue create --title "<type>: <description>" --body "<brief description of what this PR does>"
     ```
   - The PR description should reference the issue with `Closes #<number>` or `Ref #<number>`

6. **Generate PR content**
   - Draft a PR title following commit message conventions (`feat:`, `fix:`, etc.)
   - Draft a PR description with:
     - What changed and why
     - Issue reference (`Closes #N` or `Ref #N`)
     - Testing results placeholder (remind user to fill in)
     - If pinned issue checklist items are addressed, note them
   - Add the checklist from the conventions

7. **Create the PR**
   - Use `gh pr create` targeting `main`
   - Remind user to: @reviewer on GitHub, tag others in 飞书群

8. **Post-PR actions**
   - If pinned issue checklist items were addressed, remind user to update them after merge
   - Display PR link
   - Remind: 官方 reviewer 24小时内必须 review

## Mode 2: PR Merge (`/gitflow merge` or "合并PR")

Merge a PR and handle all post-merge cleanup:

### Steps

1. **Identify the PR**
   - If on a feature branch, find the associated PR:
     ```bash
     gh pr list --head "$(git branch --show-current)" --json number,title,state --jq '.[]'
     ```
   - If a PR number is provided, use that directly
   - Confirm the PR is approved and CI passes:
     ```bash
     gh pr checks <number>
     gh pr view <number> --json reviewDecision --jq .reviewDecision
     ```

2. **Merge the PR**
   ```bash
   gh pr merge <number> --merge --delete-branch
   ```
   - Use `--merge` (not squash, per team convention)
   - `--delete-branch` removes the remote feature branch after merge

3. **Close linked issues**
   - Parse the PR body for `Closes #N` / `Fixes #N` / `Ref #N` references:
     ```bash
     gh pr view <number> --json body --jq .body
     ```
   - Issues referenced with `Closes`/`Fixes` should auto-close on merge
   - For issues referenced with `Ref`, ask the user if they should be closed:
     ```bash
     gh issue close <number> --comment "Closed via PR #<pr_number>"
     ```

4. **Update pinned issue checklists**
   - Fetch all pinned issues:
     ```bash
     gh api graphql -f query='{ repository(owner:"SiliconEinstein", name:"Gaia") { pinnedIssues(first:5) { nodes { issue { number title body } } } } }'
     ```
   - Parse checklist items from pinned issue bodies
   - Determine which unchecked items (`- [ ]`) are addressed by this PR (based on PR title, body, and changed files)
   - For each matched item, show the user what will be checked off and ask for confirmation
   - Update the pinned issue body:
     ```bash
     gh issue view <number> --json body --jq .body
     # Replace `- [ ] item` with `- [x] item — ✅ PR #<number>`
     gh issue edit <number> --body "<updated body>"
     ```

5. **Switch back to main**
   ```bash
   git checkout main
   git pull origin main
   ```

6. **Display summary**
   - PR merge confirmation
   - List of closed issues
   - List of updated pinned issue checklist items
   - Confirm feature branch deleted

## Mode 3: Convention Lookup (`/gitflow` or "git规范")

When the user asks about git conventions, answer based on the team rules:

### Quick Reference

**Branch naming**: `feature/模块-描述`, `hotfix/描述`

**Commit message**: `<type>: <description>`
- `feat` / `fix` / `refactor` / `docs` / `chore` / `test`

**PR rules**:
- 一个功能一个 PR，小而完整
- 每个 PR 不超过 3 天开发量，超过必须拆分
- 禁止半成品代码，每个 PR 必须附测试结果
- GitHub 上指定 1 个官方 reviewer，其他人飞书群 @

**Review rules**:
- 官方 reviewer 24 小时内必须 review
- 需要修改 → request changes
- 无法当天回应 → 移交其他 reviewer
- 必须 review 通过才能 merge

**Merge rules**:
- feature → PR → main
- merge 后删除远程 feature 分支
- 不强制 squash

**大工程**:
- 先写 plan doc，单独提 PR 讨论
- 通过后分工，各自拉 feature 分支开发

**铁律**:
- 本地代码视为无效工作，所有代码必须进 GitHub
- 不要直接在 main 上写代码
- 不要 force push 到共享分支
- 不要提交 .env、密钥、大文件

### Answering Questions

- If the user asks a specific question (e.g., "branch怎么命名", "commit message格式"), give a concise direct answer from the rules above
- If the user asks a general question (e.g., "git规范是什么"), show the full quick reference
- Always reference `Notes/Git Flow 团队开发规范.md` for the full document

## Mode 4: Issue Management (`/gitflow issue` or "创建issue")

Create or update GitHub issues:

### Creating issues
```bash
gh issue create --title "<type>: <description>" --body "<details>" --label "<labels>"
```
- Use the same type prefixes as commit messages (`feat:`, `fix:`, `docs:`, etc.)

### Issue 分类与标签

**任务型 issue**（有明确交付物，需要排期）：
- **必须**加优先级标签：`P0`（紧急/阻塞）、`P1`（本周）、`P2`（近期）、`P3`（低优先级）
- 加类型标签：`enhancement`、`bug`、`documentation`、`testing`
- 例：`feat: versioned publish --local with content dedup` → `P0`, `enhancement`

**讨论型 issue**（设计讨论、方向探索、无明确交付物）：
- 不需要优先级标签
- 可用 `wishlist` 标签标记远期想法
- 如果包含 checklist，考虑 pin 到 repo 首页方便跟踪
- 例：`Design discussion: strong/weak references` → `enhancement`, `P3`（或不加优先级）

### Updating pinned issue checklists
After a PR is merged that addresses a pinned issue checklist item:
```bash
# Get current body, update checkbox, then update issue
gh issue view <number> --json body --jq .body
# Replace `- [ ] item` with `- [x] item` and add PR reference
gh issue edit <number> --body "<updated body>"
```
