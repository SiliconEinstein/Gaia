# Gaia Release Branch Strategy

This document defines when and how release branches are created, how hotfixes
and backports flow between branches, and how the release workflows interact with
the branch model. For the day-to-day release execution steps, see the release
process runbook in `docs/releases/`.

## TL;DR

- Feature development and alpha/beta releases live on `main`.
- A `release/0.N.x` branch is created when the RC phase begins.
- RC and stable releases are cut from the release branch.
- Hotfixes go to the release branch first, then cherry-pick to `main`.
- Only security fixes and critical (P0/P1) bugs are backported.
- At most two minor series are supported simultaneously (current + previous).

## Branch Model

```
main  ──────●──────●──────●──────●──────●──────●──► (next minor / features)
             │                    │
             │  alpha/beta from   │ RC phase begins
             │  main              │
             │                    ▼
             │             release/0.5.x ──●──────●──► (patches only)
             │                    │        │
             │                    │  0.5.0rc1   0.5.1 (hotfix)
             │                    │
             │                    ▼ 0.5.0 stable
```

## When to Create a Release Branch

| Event | Action |
|-------|--------|
| First alpha of a minor series | No branch. Dispatch `release-alpha.yml` from `main`. |
| Subsequent alphas / betas | No branch. Dispatch from `main`. |
| First RC of a minor series | **Create `release/0.N.x`** from the target commit. |
| Subsequent RCs | Dispatch from `release/0.N.x`. |
| Stable | Dispatch from `release/0.N.x`. |
| Patch release (hotfix) | Dispatch from `release/0.N.x` after merging the fix. |

The rule of thumb: a release branch is created exactly once per minor series,
at the RC phase. All pre-release activity (alpha, beta) uses `main` directly.

## Creating the Release Branch

When the RC phase begins, the release captain creates the branch from the same
target commit recorded in the Release Issue:

```bash
# Verify the target commit is the right one
git checkout main
git log --oneline -5

# Create the release branch
git checkout -b release/0.5.x <target-commit>
git push origin release/0.5.x
```

After pushing, update the Release Issue's `Target` section to note that
subsequent dispatches will use `release/0.5.x`.

## Dispatching Release Workflows from a Branch

The four release workflows (`release-alpha.yml`, `release-beta.yml`,
`release-rc.yml`, `release-stable.yml`) are all `workflow_dispatch`. When
dispatching from the GitHub Actions UI, use the **"Run workflow"** branch
selector to choose `release/0.N.x` instead of `main`.

The workflow captures `github.sha` at dispatch time, which will be the tip
commit of the selected branch — this is the correct provenance anchor.

## Hotfix and Backport Flow

### Step-by-step

```
1. Open a PR targeting release/0.N.x  (not main)
2. CI runs on the PR; reviewer approves
3. Merge to release/0.N.x
4. Record in Release Issue; run dry-run → publish
5. Cherry-pick the merge commit to main
   git cherry-pick -x <merge-commit-sha>
6. Open a follow-up PR on main if the cherry-pick has conflicts
```

### Backport policy

Only the following categories qualify for backport:

| Priority | Category | Backport? |
|----------|----------|-----------|
| P0 | Security fix (CVE or private vulnerability report) | Always |
| P0 | Data loss or corruption | Always |
| P1 | Critical regression from the previous stable release | Yes, case by case |
| P2 | Non-critical bug, performance regression | No |
| — | New features | Never |

A backport candidate is tracked by adding a `backport: release/0.N.x` label to
the original PR on `main`.

### Cherry-pick convention

Always use `git cherry-pick -x` so the original commit SHA is recorded in the
message body. This makes it easy to trace which `main` commit corresponds to a
patch release commit.

## Version Tracking on Release Branches

`pyproject.toml` on `release/0.N.x` stays at the base version of that series
(e.g., `0.5.0`). The actual release version is supplied as the `version` input
to the workflow dispatch (e.g., `0.5.1`) and applied transiently by the release
action — `pyproject.toml` is never committed with a bumped version.

This means the release action's version-override step must use a dynamic sed
pattern instead of a hardcoded version string. See the note in
`.github/actions/release/action.yml`.

## CI on Release Branches

The CI workflow (`ci.yml`) runs on push and pull-request events for
`release/**` branches. This ensures:

- All hotfix PRs get the same linting, type-checking, and test gates as PRs
  to `main`.
- The `commit-lint` job validates Conventional Commits on hotfix PRs.
- Direct pushes to `release/*` (only the release action's tag commit) also
  trigger CI.

Branch protection rules for `release/*`:

- Require pull request with at least 1 approved review before merging.
- Require status checks: `test` and `commit-lint`. The `test` job contains the
  lint, format, type-check, suppression-budget, pytest, and wheel-smoke gates.
- No direct push (only the `github-actions[bot]` tag push is an exception,
  handled by the workflow's `contents: write` permission).
- Do not allow force-push or branch deletion.

## Support Lifecycle

Gaia supports at most **two minor series** simultaneously: the current stable
and the previous stable.

| Series | Status | Support |
|--------|--------|---------|
| 0.6.x (example future) | Current stable | Security + critical bugs |
| 0.5.x | Previous stable | Security only |
| 0.4.x and older | EOL | No patches |

When a new stable minor is published, the N-2 series is declared EOL. An EOL
announcement is posted in the GitHub release and the release branch is archived
(read-only, not deleted).

## Release Branch vs. Hotfix Branch

Do not confuse the two:

| Term | What it is |
|------|-----------|
| `release/0.N.x` | Long-lived branch; source of all patch releases for a minor series |
| `hotfix/<description>` | Short-lived branch opened against `release/0.N.x`, deleted after merge |

Hotfix branches are merged via PR into `release/0.N.x`, not pushed directly.

## Common Scenarios

### Cutting 0.5.0rc1 while 0.6.0 work is ongoing

1. Create `release/0.5.x` from the RC target commit on `main`.
2. `main` continues accepting 0.6.0 feature PRs immediately.
3. Dispatch `release-rc.yml` from `release/0.5.x`.
4. RC bug fixes go to `release/0.5.x` via hotfix PRs; cherry-pick to `main`.

### A 0.5.0 regression found after stable ships

1. Open `hotfix/fix-foo` from `release/0.5.x`.
2. Fix, PR, merge to `release/0.5.x`.
3. Open Release Issue for `0.5.1`.
4. Dispatch `release-stable.yml` from `release/0.5.x` with `version=0.5.1`.
5. Cherry-pick to `main`.

### A security fix for an EOL series

Gaia does not backport to EOL series. Publish an advisory via GitHub Security
Advisories and recommend upgrading. If the vulnerability is severe enough to
warrant an exception, the release captain decides and documents the decision in
the advisory.
