# Gaia Release Process

This runbook is the operational guide for cutting Gaia releases. For the
release-channel design and workflow rationale, see the repository source file
`docs/specs/2026-05-16-gaia-release-channel-strategy.md`. For branch ownership,
hotfix, and backport policy, see `docs/releases/branch-strategy.md`.

## TL;DR

- Alpha and beta releases are cut from `main`.
- RC, stable, and patch releases are cut from the relevant `release/0.N.x`
  branch once that branch exists.
- Only changes merged into the selected release source branch can enter a
  release.
- Work that is not ready to ship stays in an open or draft PR.
- Every manual release has a GitHub Release Issue as its source of truth.
- Run the release workflow with `dry_run=true` before publishing.
- After publish, the immutable `v<version>` tag is the provenance anchor.

## Source Of Truth

Use one GitHub issue per release, named `Release <version>` (for example,
`Release 0.5.0a2`). The issue records:

- release captain
- channel and version
- target commit
- audited list of merged PRs intended for the release
- PRs that must not merge before this release, when any need explicit blocking
- dry-run workflow link
- publish workflow link
- PyPI and GitHub release links
- known limitations and follow-ups

If a detail is not in the Release Issue, it is not part of the release plan.
Chat messages can coordinate, but the Release Issue records the decision.

## Example Release Issue

Use the issue template for real releases. A dry-run issue can look like this:

```md
## Release

Version: 0.5.0a2
Channel: alpha
Release captain: dp
Status: dry-run green

## Target

Target commit: 7dc94636f1f93ada18af7fbf7ab0004921037a35
Workflow: release-alpha.yml

## Include

PRs listed here are the audited release contents already present in the target
commit. This list is not a filter: any PR already merged into the target commit
is included by construction. To exclude a merged PR, choose an earlier target
commit or revert the PR before dry-run.

- [x] PR #740 LKM graph API alignment

## Do Not Merge Before This Release

Optional. Use only for PRs that are at risk of being merged into `main` before
this release is cut but should not enter this release.

- [ ] none

## Pre-Release Checks

- [ ] Release notes exist or are not required for this channel
- [x] Included PRs are merged into `main`
- [x] At-risk non-included PRs are listed above, if any
- [ ] Short release freeze announced
- [x] Target commit recorded
- [x] PR CI green for target commit
- [ ] Nightly green, or reason recorded for not waiting

## Dry-Run

- [x] Release workflow dispatched with `dry_run=true` and `target_commit` set
- [x] Dry-run workflow passed
- [x] Dry-run run head SHA equals Target commit

Dry-run workflow link:
https://github.com/SiliconEinstein/Gaia/actions/runs/26992416344

## Publish

- [ ] Release workflow dispatched with `dry_run=false` and `target_commit` set
- [ ] Publish run head SHA equals Target commit
- [ ] PyPI publication confirmed
- [ ] `v<version>` tag confirmed
- [ ] GitHub release or prerelease confirmed
- [ ] Fresh install smoke completed
- [ ] Release freeze lifted

Publish workflow link:
PyPI link:
GitHub release link:
Tag:

## Known Limitations

- This was a dry-run only. PyPI publish, tag creation, and GitHub prerelease
  creation were skipped as expected.

## Follow-Ups

- Decide whether to publish `0.5.0a2` for real.
- Add or confirm release notes if this becomes a real alpha release.
```

## Channels

| Channel | Version form | Trigger | Publish target | Intended users |
|---|---|---|---|---|
| PR/dev | none | PR, push to `main`, or `workflow_dispatch` | Not published | Contributors |
| Nightly | `0.5.0.devYYYYMMDD` | Daily schedule or manual dispatch | GitHub Actions artifact only | Maintainers and package authors |
| Alpha | `0.5.0aN` | Manual `release-alpha.yml` dispatch | PyPI + GitHub prerelease | Early adopters |
| Beta | `0.5.0bN` | Manual `release-beta.yml` dispatch | PyPI + GitHub prerelease | Migration testers |
| RC | `0.5.0rcN` | Manual `release-rc.yml` dispatch | PyPI + GitHub prerelease | Final validators |
| Stable | `0.5.0` | Manual `release-stable.yml` dispatch | PyPI + GitHub release | Default users |

Nightly artifacts are validation snapshots. They do not publish to PyPI. Alpha,
beta, rc, and stable are explicit human promotions.

## Roles

- **Release captain:** Opens and owns the Release Issue, announces the release
  window, selects the target commit, dispatches workflows, and closes the issue.
- **PR owner:** States whether their PR is ready for the release. If not ready,
  keeps it open or draft.
- **Reviewer / maintainer:** Reviews release blockers, confirms included PRs,
  and approves merge timing.

## Merge Rules

- A PR that should be included in the release must pass CI and be merged into
  the selected release source branch before the target commit is selected.
- A PR that is not ready to release must remain open or draft.
- The `Include` section is the audited list of release contents. It does not
  filter the release artifact: the published wheel, sdist, tag, and GitHub
  release are produced from the selected workflow head SHA. Any PR already in
  the target commit ships even if it is absent from `Include`.
- Use `Do Not Merge Before This Release` only for PRs that are at risk of being
  merged into `main` during the release window but should not enter this
  release.
- Once the release captain announces a short release freeze, avoid merging
  unrelated PRs into the selected release source branch until the release is
  published or cancelled.
- If an unwanted PR was already merged into the selected release source branch,
  choose explicitly:
  include it in the release, or revert it before dry-run. Do not assume the
  release workflow can partially exclude merged code.

## Standard Release Flow

1. Open a Release Issue from the release issue template.
2. Pick the channel and version.
3. Add included PRs.
4. Add any at-risk PRs to `Do Not Merge Before This Release`.
5. Confirm release notes exist or are not required for this channel.
6. Merge only release-ready PRs into the selected release source branch (`main`
   for alpha/beta; `release/0.N.x` for RC, stable, and patch releases).
7. Announce a short release freeze.
8. Record the target commit in the Release Issue.
9. Confirm PR CI and, when appropriate, nightly are green for the target commit.
10. Dispatch the matching release workflow with `dry_run=true` and
    `target_commit` set to the recorded target commit.
11. Confirm the dry-run run head SHA equals the target commit.
12. If dry-run is green, dispatch the same workflow with `dry_run=false` and
    the same `target_commit`.
13. Confirm the publish run head SHA equals the target commit.
14. Confirm PyPI publication.
15. Confirm the `v<version>` git tag and GitHub release or prerelease.
16. Update the Release Issue with links and known limitations.
17. Lift the release freeze and close the issue.

## Workflow Gates

The release workflows all use `.github/actions/release/action.yml`. The release
workflows require a `target_commit` input and fail before publishing if the
workflow head SHA is not exactly that target. The shared release action then
validates:

- transient `pyproject.toml` version override
- injected channel and commit metadata
- `gaia --version` version and channel output
- wheel and sdist build
- wheel smoke in a fresh virtual environment
- full test suite via `make test-all`
- strict docs build
- package corpus e2e via `scripts/run_package_corpus.py`

PyPI Trusted Publishing runs in the top-level release workflow after the shared
release action completes.

## Common Scenarios

### A Small Docs Or API Release While Another PR Is Unfinished

Merge only the docs or API PR. Keep the unfinished PR open or draft. If the
unfinished PR is at risk of being merged before publication, record it under
`Do Not Merge Before This Release`.

### A PR Was Merged Too Early

Before dry-run, decide whether the release should include it. If yes, add it to
the Release Issue. If no, revert it on `main`, let CI run, and release from the
post-revert commit.

### A Release Blocker Appears During Dry-Run

Cancel the publish run. Fix the blocker in a PR, merge it into the selected
release source branch, update the target commit in the Release Issue, and run
dry-run again.

### A Hotfix Is Needed

Open a hotfix Release Issue, keep the include list minimal, and use the same
dry-run-then-publish flow from the relevant `release/0.N.x` branch. If the
branch does not exist yet, create it first as described in
`docs/releases/branch-strategy.md`, then record that decision in the Release
Issue.

## After Publication

After publishing, the release captain should verify:

- `https://pypi.org/project/gaia-lang/<version>/` exists
- the `v<version>` tag points to the intended commit
- the GitHub release or prerelease exists
- `gaia --version` from a fresh install reports the expected version, channel,
  commit, and IR schema

For prereleases, users must install with an explicit version pin or allow
prereleases, for example:

```bash
pip install gaia-lang==0.5.0a2
pip install --pre gaia-lang
```
