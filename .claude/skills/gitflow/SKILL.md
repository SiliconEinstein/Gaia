---
name: gitflow
description: "Git flow assistant for team development. Use when the user says /gitflow, asks about git conventions, wants to create a PR, or needs help with branching/commit/review workflow. Can also be triggered by 'create PR', 'git规范', 'PR怎么写'."
---

# Git Flow Assistant

Team git workflow assistant based on the conventions in `Notes/Git Flow 团队开发规范.md`.

## Capabilities

This skill has two modes: **PR creation** and **convention lookup**.

## Mode 1: PR Creation (`/gitflow pr` or "帮我提PR")

Guide the user through creating a PR that follows team conventions:

### Steps

1. **Check current branch state**
   ```bash
   git branch --show-current
   git log main..HEAD --oneline
   git diff main --stat
   ```

2. **Validate against conventions**
   - Is the branch named correctly? (`feature/模块-描述` or `hotfix/描述`)
   - Is it rebased on latest main? If not, remind to rebase
   - Is the diff size reasonable? (warn if >3 days of work / very large diff)

3. **Generate PR content**
   - Draft a PR title following commit message conventions (`feat:`, `fix:`, etc.)
   - Draft a PR description with:
     - What changed and why
     - Testing results placeholder (remind user to fill in)
   - Add the checklist from the conventions

4. **Create the PR**
   - Use `gh pr create` targeting `main`
   - Remind user to: @reviewer on GitHub, tag others in 飞书群

5. **Display summary**
   - PR link
   - Remind: 官方 reviewer 24小时内必须 review

## Mode 2: Convention Lookup (`/gitflow` or "git规范")

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
