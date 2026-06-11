---
name: Release
about: Coordinate a Gaia release from main
title: "Release <version>"
labels: release
assignees: ""
---

## Release

Version:
Channel: alpha | beta | rc | stable
Release captain:
Status: planning | frozen | dry-run green | published | closed

## Target

Target commit:
Workflow:

## Include

PRs listed here are the audited release contents already present in the target
commit. This list is not a filter: any PR already merged into the target commit
is included by construction. To exclude a merged PR, choose an earlier target
commit or revert the PR before dry-run.

- [ ] PR #

## Do Not Merge Before This Release

Optional. Use only for PRs that are at risk of being merged into `main` before
this release is cut but should not enter this release.

- [ ] PR #

## Pre-Release Checks

- [ ] Release notes exist or are not required for this channel
- [ ] Included PRs are merged into `main`
- [ ] At-risk non-included PRs are listed above, if any
- [ ] Short release freeze announced
- [ ] Target commit recorded
- [ ] PR CI green for target commit
- [ ] Nightly green, or reason recorded for not waiting

## Dry-Run

- [ ] Release workflow dispatched with `dry_run=true` and `target_commit` set
- [ ] Dry-run workflow passed
- [ ] Dry-run run head SHA equals Target commit

Dry-run workflow link:

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

-

## Follow-Ups

-
