# Publish and Register

> **Status:** Current canonical (alpha 0 grouped CLI)

Use this path when a Gaia package is ready to submit to a registry.

## Local Release Prep

```bash
gaia build compile .
gaia build check --gate .
gaia run infer .
git status --short
git tag v1.0.0
git push origin v1.0.0
```

The package must have a clean git worktree, a pushed tag pointing to `HEAD`,
and fresh compiled artifacts.

## Register

```bash
gaia pkg register .
gaia pkg register . --registry-dir ../gaia-registry
gaia pkg register . --registry-dir ../gaia-registry --create-pr
```

Without `--registry-dir`, registration is a dry-run JSON plan. With
`--registry-dir`, Gaia writes registry metadata into a local registry checkout.
With `--create-pr`, Gaia also pushes the registry branch and opens a PR.

Registry CI, waiting periods, and auto-merge are registry-side policy. The local
CLI prepares or submits metadata; it does not guarantee registry acceptance.

## What To Read Next

- [CLI Reference: pkg](../../reference/cli/pkg.md) for `register`.
- [Registration Internals](../../foundations/cli/registration.md) for generated registry files and validation boundaries.
