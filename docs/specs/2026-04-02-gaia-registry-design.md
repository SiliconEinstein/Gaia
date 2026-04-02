# Gaia Official Registry — Phase 1 Design

> **Status:** Target design
>
> **Depends on:** [Gaia Lang v5](2026-04-02-gaia-lang-v5-python-dsl-design.md), [Gaia IR v2](../foundations/gaia-ir/02-gaia-ir.md), [Ecosystem](../foundations/ecosystem/)
>
> **Phase 1 scope:** Package registration + CI validation + distribution. **Review system deferred** — no reviewer assignment, no review gate, no parameterization validation.

## 1. Overview

The Gaia Official Registry is a **GitHub repository** that serves as the central index for Gaia knowledge packages. It follows the [Julia General Registry](https://github.com/JuliaRegistries/General) model: metadata-only git repo + automated CI + community governance.

### 1.1 Architecture

```
                   ┌─────────────────────────────────┐
                   │     Registry Repo (GitHub)       │
                   │                                  │
                   │  packages/                       │
                   │    galileo-falling-bodies/       │
                   │      Package.toml               │
                   │      Versions.toml              │
                   │      Deps.toml                  │
                   │                                  │
                   │  .github/workflows/              │
                   │    register.yml   (CI validate)  │
                   │    publish.yml    (build + dist) │
                   │    index.yml      (regen index)  │
                   │                                  │
                   │  GitHub Releases                 │
                   │    (wheel files stored here)     │
                   │                                  │
                   │  GitHub Pages (gh-pages branch)  │
                   │    simple/  (auto-generated)     │
                   │      galileo-falling-bodies-gaia/│
                   │        index.html  (PEP 503)    │
                   └─────────────────────────────────┘
                         ↑                    ↑
                    PR (register)      uv add (install)
                         │                    │
                      Authors             Consumers
```

### 1.2 Key Properties

| Property | Implementation |
|----------|---------------|
| **Trust chain** | Only Registry CI can publish wheels → GitHub Pages serves verified packages only |
| **Decentralized authoring** | Each package lives in its own git repo; Registry only stores metadata |
| **Zero infrastructure** | GitHub repo + GitHub Actions + GitHub Pages + GitHub Releases. No servers. |
| **uv-native** | PEP 503 static index → standard `uv add` workflow |
| **Auditable** | Every registration is a git commit with full CI log |
| **Forkable** | Any community can fork the registry with different policies |

> **Phase 1 deviation from ecosystem foundation:** The ecosystem doc (`04-registry-operations.md`) states that review is a precondition for registry entry ("没有足够 assigned review reports 的包版本不能通过入库校验"). Phase 1 intentionally relaxes this to bootstrap the infrastructure — structural integrity is verified, but no epistemic parameters (priors, conditional probabilities) are required. When Phase 2 enables the review gate, a **grandfathering policy** must be defined: either (a) all Phase 1 packages undergo retroactive review, or (b) they are marked as "unreviewed" and excluded from LKM global inference until reviewed.

---

## 2. Registry Repo Structure

```
gaia-registry/
├── packages/                     # Package metadata (changes here trigger publish.yml)
│   ├── galileo-falling-bodies/
│   │   ├── Package.toml
│   │   ├── Versions.toml         # Includes git_sha pinned at validation time
│   │   └── Deps.toml
│   ├── aristotle-mechanics/
│   │   └── ...
│   └── ...
├── metadata/                     # Post-publish data (does NOT trigger publish.yml)
│   └── wheel-hashes.toml         # wheel_hash records, written by trusted publisher
├── .github/
│   └── workflows/
│       ├── register.yml          # PR validation (sandbox + trusted gate)
│       └── publish.yml           # Build + publish (untrusted builder + trusted publisher)
├── registry.toml                 # Global registry config
└── README.md
```

### 2.1 Package Metadata

**Package.toml** — one per package, created at first registration:

```toml
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
name = "galileo-falling-bodies"
pypi_name = "galileo-falling-bodies-gaia"    # PyPI name (-gaia suffix)
repo = "https://github.com/kunyuan/GalileoFallingBodies.gaia"
description = "Galileo's falling bodies argument"
created_at = "2026-04-02T10:00:00Z"
```

**Versions.toml** — appended with each new version:

```toml
[versions."4.0.0"]
ir_hash = "sha256:a1b2c3d4..."
wheel_hash = "sha256:f9e8d7c6..."    # SHA-256 of the .whl file (for PEP 503)
git_tag = "v4.0.0"
git_sha = "abc123def456..."           # Immutable commit SHA — pinned at validation time
registered_at = "2026-04-02T10:30:00Z"
wheel = "galileo_falling_bodies_gaia-4.0.0-py3-none-any.whl"

[versions."4.1.0"]
ir_hash = "sha256:e5f6g7h8..."
wheel_hash = "sha256:b5a4c3d2..."
git_tag = "v4.1.0"
git_sha = "789abc012def..."
registered_at = "2026-04-10T15:00:00Z"
wheel = "galileo_falling_bodies_gaia-4.1.0-py3-none-any.whl"
```

**Deps.toml** — dependencies per version (auto-generated from `pyproject.toml` by `gaia register`, verified by CI):

```toml
[deps."4.0.0"]
"aristotle-mechanics-gaia" = ">= 1.0.0"

[deps."4.1.0"]
"aristotle-mechanics-gaia" = ">= 1.0.0"
"newton-mechanics-gaia" = ">= 2.0.0"
```

`Deps.toml` is derived from the package's `pyproject.toml` (filtered to `*-gaia` dependencies only). `gaia register` generates it automatically; CI verifies consistency with the source `pyproject.toml`.

### 2.2 Global Config

**registry.toml:**

```toml
[registry]
name = "Gaia Official Registry"
url = "https://siliconeinstein.github.io/gaia-registry/simple/"

[policy]
new_package_wait_hours = 72      # 3 days for new packages
version_update_wait_hours = 1    # 1 hour for version updates
require_review = false           # Phase 1: no review gate
min_review_count = 0             # Phase 1: no reviews required

[index]
github_pages_branch = "gh-pages"
releases_repo = "SiliconEinstein/gaia-registry"  # Where wheels are stored as Releases
```

---

## 3. Registration Flow

### 3.1 Author's Workflow

```bash
# 1. Author develops package in their own repo
cd ~/my-package
vim my_package/__init__.py       # Write knowledge
gaia compile .                    # Compile → .gaia/ir.json + ir_hash
gaia check .                      # Validate structure
git tag v1.0.0
git push origin v1.0.0

# 2. Request registration
gaia register                     # Creates PR to Registry repo
# Or: comment @GaiaRegistrator on the release
```

### 3.2 `gaia register` Command

`gaia register` automates PR creation:

1. Read `pyproject.toml` for package metadata
2. Read `.gaia/ir_hash` for integrity checksum
3. Verify git tag exists and is pushed
4. Create PR to Registry repo via GitHub API (`gh pr create`):
   - For new packages: create `Package.toml` + `Versions.toml` + `Deps.toml`
   - For version updates: append to `Versions.toml` + update `Deps.toml`

PR body template:

```markdown
## Register: galileo-falling-bodies-gaia v4.0.0

- **Repository:** https://github.com/galileo/falling-bodies
- **Tag:** v4.0.0
- **IR Hash:** sha256:a1b2c3d4...

### Exported claims
- `vacuum_prediction` — In a vacuum, objects of different mass fall at the same rate.
- `air_resistance` — Observed speed differences are caused by air resistance.

### Dependencies
- aristotle-mechanics-gaia >= 1.0.0
```

### 3.3 CI Validation (`register.yml`)

Two jobs: an **untrusted sandbox** (no write permissions) that executes author code, and a **trusted gate** (no code execution) that records results.

> **Security design:** `gaia compile` executes author Python code via `importlib.import_module()`. This MUST run in a job with no write credentials. The trusted gate job only reads validation artifacts — it never touches third-party code.

```yaml
name: Validate Registration
on:
  pull_request:
    paths: ['packages/**']

jobs:
  # ── Job 1: Untrusted sandbox (NO write permissions) ──
  # Executes author code in isolation. Cannot modify registry.
  sandbox-validate:
    runs-on: ubuntu-latest
    permissions:
      contents: read         # Read-only: no write to releases/pages
    steps:
      - uses: actions/checkout@v4

      - name: Parse registration PR
        id: parse
        run: python scripts/parse_registration_pr.py

      - name: Clone and pin to immutable commit SHA
        id: pin
        run: |
          git clone ${{ steps.parse.outputs.repo_url }} pkg
          cd pkg && git checkout ${{ steps.parse.outputs.git_tag }}
          # Record the resolved commit SHA (immutable, unlike tags)
          echo "git_sha=$(git rev-parse HEAD)" >> "$GITHUB_OUTPUT"
          # Verify tag points to declared SHA (if PR includes git_sha)
          if [ -n "${{ steps.parse.outputs.git_sha }}" ]; then
            [ "$(git rev-parse HEAD)" = "${{ steps.parse.outputs.git_sha }}" ] \
              || { echo "ERROR: tag moved since registration!"; exit 1; }
          fi

      - name: Install gaia-lang
        run: uv sync

      - name: Reproducible build (executes author code — sandboxed)
        run: |
          cd pkg
          gaia compile .
          diff <(cat .gaia/ir_hash) <(echo "${{ steps.parse.outputs.ir_hash }}")

      - name: Schema validation
        run: cd pkg && gaia check .

      - name: Dependency check
        run: |
          python scripts/check_deps_registered.py \
            --deps pkg/pyproject.toml \
            --registry packages/

    outputs:
      git_sha: ${{ steps.pin.outputs.git_sha }}

  # ── Job 2: Trusted gate (has label/merge permissions, NO code execution) ──
  trusted-gate:
    needs: sandbox-validate
    runs-on: ubuntu-latest
    permissions:
      pull-requests: write   # For labeling/merging
    steps:
      - uses: actions/checkout@v4

      - name: Parse registration PR
        id: parse
        run: python scripts/parse_registration_pr.py

      - name: UUID uniqueness check
        run: |
          python scripts/check_uuid_unique.py \
            --package ${{ steps.parse.outputs.package_name }} \
            --registry packages/

      - name: Repository ownership check
        run: |
          gh api repos/${{ steps.parse.outputs.repo_owner_and_name }}/collaborators/${{ github.event.pull_request.user.login }}/permission \
            --jq '.permission' | grep -qE 'admin|write'

      - name: Record pinned git_sha in PR
        run: |
          echo "Validated commit: ${{ needs.sandbox-validate.outputs.git_sha }}"
          # Write git_sha into Versions.toml if not already present
          python scripts/pin_git_sha.py \
            --package ${{ steps.parse.outputs.package_name }} \
            --version ${{ steps.parse.outputs.version }} \
            --sha ${{ needs.sandbox-validate.outputs.git_sha }}

      - name: Label and schedule auto-merge
        run: |
          if [ "${{ steps.parse.outputs.is_new_package }}" = "true" ]; then
            WAIT_HOURS=72
          else
            WAIT_HOURS=1
          fi
          gh pr label ${{ github.event.pull_request.number }} --add "ci-passed"
          python scripts/schedule_auto_merge.py \
            --pr ${{ github.event.pull_request.number }} \
            --wait-hours $WAIT_HOURS
```

### 3.4 Build & Publish (`publish.yml`)

Triggered when a registration PR is merged. Two jobs: an **untrusted builder** (read-only, executes package code) that produces wheel artifacts, and a **trusted publisher** (write access, no code execution) that uploads to Releases and updates GitHub Pages.

> **Security design:** The builder job checks out author code by **pinned commit SHA** (not tag) and builds the wheel, but has no write permissions. The publisher job only handles pre-built artifacts — it never executes third-party code.
>
> **Self-trigger prevention:** The publisher writes `wheel_hash` to `metadata/` (not `packages/`), so it does not match the `packages/**` trigger path. The workflow is idempotent: `detect_changed_versions.py` only selects versions without an existing GitHub Release.

```yaml
name: Build and Publish
on:
  push:
    branches: [main]
    paths: ['packages/**']       # Only triggers on registration merges, NOT metadata/ writes
concurrency:
  group: publish
  cancel-in-progress: false

jobs:
  # ── Job 1: Untrusted builder (read-only, executes author code) ──
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read             # Read-only: cannot modify registry
    steps:
      - uses: actions/checkout@v4

      - name: Detect changed packages (skip already-published versions)
        id: changed
        run: python scripts/detect_changed_versions.py

      - name: Clone by pinned SHA, build wheel
        run: |
          for pkg_info in ${{ steps.changed.outputs.packages }}; do
            REPO_URL=$(echo $pkg_info | jq -r .repo)
            GIT_SHA=$(echo $pkg_info | jq -r .git_sha)    # Immutable SHA, not tag
            PKG_NAME=$(echo $pkg_info | jq -r .pypi_name)
            VERSION=$(echo $pkg_info | jq -r .version)

            # Clone and checkout by SHA (immutable — cannot be moved)
            git clone $REPO_URL build_pkg
            cd build_pkg && git checkout $GIT_SHA

            # Build wheel (executes author code — but we are read-only)
            uv build --wheel

            # Compute wheel hash
            WHEEL_FILE=$(ls dist/*.whl)
            WHEEL_HASH=$(sha256sum $WHEEL_FILE | cut -d' ' -f1)

            # Stage artifact for upload
            mkdir -p /tmp/wheels
            cp $WHEEL_FILE /tmp/wheels/
            echo "${PKG_NAME}|${VERSION}|${WHEEL_HASH}|$(basename $WHEEL_FILE)" >> /tmp/wheels/manifest.txt

            cd .. && rm -rf build_pkg
          done

      - name: Upload wheel artifacts
        uses: actions/upload-artifact@v4
        with:
          name: wheels
          path: /tmp/wheels/

  # ── Job 2: Trusted publisher (write access, NO code execution) ──
  publish:
    needs: build
    runs-on: ubuntu-latest
    permissions:
      contents: write            # For creating Releases + pushing metadata
      pages: write               # For updating GitHub Pages
    steps:
      - uses: actions/checkout@v4

      - name: Download wheel artifacts
        uses: actions/download-artifact@v4
        with:
          name: wheels
          path: /tmp/wheels/

      - name: Upload to GitHub Releases and record hashes
        run: |
          while IFS='|' read -r PKG_NAME VERSION WHEEL_HASH WHEEL_FILE; do
            # Create Release (idempotent: skip if already exists)
            gh release create "release/${PKG_NAME}-${VERSION}" \
              "/tmp/wheels/${WHEEL_FILE}" \
              --repo SiliconEinstein/gaia-registry \
              --title "${PKG_NAME} ${VERSION}" \
              --notes "Auto-published by registry CI" \
              2>/dev/null || echo "Release already exists, skipping"

            # Record wheel_hash in metadata/ (NOT packages/ — avoids self-trigger)
            python scripts/update_wheel_hash.py \
              --package $PKG_NAME --version $VERSION --hash $WHEEL_HASH
          done < /tmp/wheels/manifest.txt

      - name: Commit wheel hashes to metadata/
        run: |
          git add metadata/ packages/
          git commit -m "ci: record wheel hashes [skip ci]" || true
          git push

      - name: Regenerate PEP 503 index
        run: python scripts/generate_pep503_index.py --output-dir /tmp/simple

      - name: Deploy to GitHub Pages
        uses: peaceiris/actions-gh-pages@v4
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          publish_dir: /tmp/simple
```

### 3.5 Auto-Merge Policy

```yaml
# In register.yml, after CI passes:
- name: Auto-merge after waiting period
  if: steps.parse.outputs.is_new_package == 'true'
  run: |
    gh pr merge ${{ github.event.pull_request.number }} \
      --auto --squash \
      --delete-branch
  # GitHub's auto-merge respects branch protection rules:
  # - Required check: "validate" must pass
  # - Required wait: configured via GitHub branch protection or custom action
```

| Scenario | Waiting period | Rationale |
|----------|---------------|-----------|
| New package | 72 hours (3 days) | Community review window |
| Version update | 1 hour | Lower risk, proven package |

During the waiting period, anyone can comment on the PR to raise concerns.

---

## 4. PEP 503 Static Index

### 4.1 Structure

GitHub Pages serves a standard [PEP 503](https://peps.python.org/pep-0503/) Simple Repository:

```
simple/
├── index.html                              # Root: lists all packages
├── galileo-falling-bodies-gaia/
│   └── index.html                          # Per-package: lists all versions
├── aristotle-mechanics-gaia/
│   └── index.html
└── ...
```

### 4.2 Root index.html

```html
<!DOCTYPE html>
<html><body>
<a href="/galileo-falling-bodies-gaia/">galileo-falling-bodies-gaia</a>
<a href="/aristotle-mechanics-gaia/">aristotle-mechanics-gaia</a>
</body></html>
```

### 4.3 Per-Package index.html

```html
<!DOCTYPE html>
<html><body>
<a href="https://github.com/SiliconEinstein/gaia-registry/releases/download/release/galileo-falling-bodies-gaia-4.0.0/galileo_falling_bodies_gaia-4.0.0-py3-none-any.whl#sha256=f9e8d7c6">
  galileo_falling_bodies_gaia-4.0.0-py3-none-any.whl
</a>
<a href="https://github.com/SiliconEinstein/gaia-registry/releases/download/release/galileo-falling-bodies-gaia-4.1.0/galileo_falling_bodies_gaia-4.1.0-py3-none-any.whl#sha256=b5a4c3d2">
  galileo_falling_bodies_gaia-4.1.0-py3-none-any.whl
</a>
</body></html>
```

Download URLs point to GitHub Releases assets on the Registry repo itself. The `#sha256=...` fragment is the **wheel file hash** (not `ir_hash`), enabling standard PEP 503 integrity verification by uv. `ir_hash` is a separate field in `Versions.toml` for reproducible-build verification.

### 4.4 Index Generation Script

```python
# scripts/generate_pep503_index.py
"""Reads packages/ metadata, generates simple/ PEP 503 HTML index."""

import re
import tomllib
from pathlib import Path

REGISTRY_REPO = "SiliconEinstein/gaia-registry"
RELEASES_URL = f"https://github.com/{REGISTRY_REPO}/releases/download"

def normalize(name: str) -> str:
    """PEP 503 normalization: lowercase, replace [-_.] runs with single dash."""
    return re.sub(r"[-_.]+", "-", name).lower()

def generate():
    packages_dir = Path("packages")
    simple_dir = Path("simple")
    simple_dir.mkdir(exist_ok=True)

    package_links = []
    for pkg_dir in sorted(packages_dir.iterdir()):
        if not pkg_dir.is_dir():
            continue

        pkg_toml = tomllib.loads((pkg_dir / "Package.toml").read_text())
        versions_toml = tomllib.loads((pkg_dir / "Versions.toml").read_text())
        pypi_name = pkg_toml["pypi_name"]
        normalized_name = normalize(pypi_name)

        package_links.append(f'<a href="/{normalized_name}/">{normalized_name}</a>')

        # Per-package index
        pkg_index_dir = simple_dir / normalized_name
        pkg_index_dir.mkdir(exist_ok=True)
        version_links = []
        for version, info in versions_toml.get("versions", {}).items():
            wheel = info["wheel"]
            wheel_hash = info["wheel_hash"]  # SHA-256 of the .whl file
            tag = f"release/{pypi_name}-{version}"
            url = f"{RELEASES_URL}/{tag}/{wheel}#sha256={wheel_hash}"
            version_links.append(f'<a href="{url}">{wheel}</a>')

        (pkg_index_dir / "index.html").write_text(
            f"<!DOCTYPE html>\n<html><body>\n"
            + "\n".join(version_links)
            + "\n</body></html>"
        )

    # Root index
    (simple_dir / "index.html").write_text(
        f"<!DOCTYPE html>\n<html><body>\n"
        + "\n".join(package_links)
        + "\n</body></html>"
    )
```

---

## 5. Consumer Workflow

### 5.1 Configuration

```toml
# Consumer's pyproject.toml
[[tool.uv.index]]
name = "gaia"
url = "https://siliconeinstein.github.io/gaia-registry/simple/"
```

### 5.2 Installing Packages

```bash
uv add galileo-falling-bodies-gaia
# 1. uv queries https://siliconeinstein.github.io/gaia-registry/simple/galileo-falling-bodies-gaia/
# 2. Gets HTML with download links pointing to GitHub Releases
# 3. Downloads wheel, verifies hash
# 4. Installs into .venv

# Version pinning works as expected
uv add "galileo-falling-bodies-gaia >= 4.0.0, < 5.0.0"
```

### 5.3 Cross-Package References

```python
# Works immediately after uv add
from galileo_falling_bodies import vacuum_prediction

with Package("my_analysis") as pkg:
    my_claim = claim("...", given=[vacuum_prediction])
```

---

## 6. Trust Model

### 6.1 Trust Chain

```
Consumer does `uv add galileo-falling-bodies-gaia`
    ↓
uv queries GitHub Pages index (served from gh-pages branch)
    ↓ Only the trusted publisher job can write to gh-pages
Download link points to GitHub Releases
    ↓ Only the trusted publisher job can create Releases
Wheel was built by the untrusted builder job (read-only, sandboxed)
    ↓ Builder checks out by pinned commit SHA (immutable)
    ↓ Builder produces wheel artifact, passed to publisher via Actions artifact
Source was validated by sandbox-validate job in register.yml
    ↓ Verified: ir_hash match, schema valid, deps registered
    ↓ Pinned commit SHA recorded in Versions.toml at validation time
```

**Guarantees:**
- Every package on the index was compiled and verified by Registry CI.
- Author code never executes in a job with write permissions (sandbox isolation).
- Source is pinned by commit SHA at validation time — tag mutation after validation cannot affect published artifacts.
- The publish workflow is idempotent and non-self-triggering (`metadata/` writes don't match `packages/**` trigger).

### 6.2 What Phase 1 Does NOT Guarantee

| Not guaranteed | Why | Future phase |
|---|---|---|
| Scientific quality | No review system | Phase 2: reviewer assignment + review gate |
| Probability values verified | No parameterization check | Phase 2: review reports with PriorRecord/StrategyParamRecord |
| Cross-package consistency | No LKM integration | Phase 3: LKM global inference |
| Duplicate detection | No curation service | Phase 3: LKM discovery + curation packages |

Phase 1 guarantees **structural integrity** (compiles, valid schema, deps exist) but not **epistemic quality** (priors reasonable, reasoning sound).

### 6.3 Phase 1 Limitations

- **Public repos only:** Registration CI clones the author's repo via unauthenticated `git clone`. Private repositories are not supported in Phase 1. Future: GitHub App installation tokens or deploy keys.
- **No spam protection:** Registration relies on community review during the waiting period. Future: minimum repo age, author rate limiting.
- **Command naming:** This spec uses `gaia compile` / `gaia check` (per the [v5 DSL spec](2026-04-02-gaia-lang-v5-python-dsl-design.md)). The ecosystem foundation docs still reference `gaia build` — will be reconciled when ecosystem docs are updated for v5.

---

## 7. CLI Commands (Registry-Related)

```bash
# Author-side
gaia register                  # Create PR to Registry repo
gaia register --check          # Dry-run: validate locally before submitting

# Consumer-side (standard uv)
uv add galileo-falling-bodies-gaia        # Install from registry
uv add --upgrade galileo-falling-bodies-gaia  # Upgrade to latest

# Registry admin
gaia registry rebuild-index    # Regenerate full PEP 503 index from metadata
gaia registry list             # List all registered packages
gaia registry info galileo     # Show package details
```

---

## 8. Phase 2 Extension Points

The Phase 1 design includes extension points for future phases:

### 8.1 Review Gate (Phase 2)

```toml
# registry.toml — flip when ready
[policy]
require_review = true
min_review_count = 1
```

`register.yml` adds steps:
- Check `.gaia/reviews/` exists
- Verify reviewer is registered in `reviewers/` directory
- Verify review report count meets policy
- Verify parameterization values are in legal range

### 8.2 Reviewer Registration (Phase 2)

```
gaia-registry/
├── reviewers/
│   ├── alice/
│   │   └── Reviewer.toml      # Identity, expertise, public key
│   └── bob/
│       └── Reviewer.toml
├── review-assignments/
│   └── assignments.jsonl       # Version → assigned reviewers
```

### 8.3 LKM Integration (Phase 3)

```
gaia-registry/
├── lkms/
│   └── lkm-alpha/
│       └── LKM.toml           # LKM server registration
```

LKM pulls newly registered packages, runs global inference, publishes belief snapshots.

---

## 9. Example: End-to-End Registration

```bash
# === Author side ===

# Create package
uv init --lib my-research-gaia
uv add gaia-lang
uv add galileo-falling-bodies-gaia  # Cross-package dependency

# Write knowledge
cat > my_research/__init__.py << 'EOF'
from gaia.lang import Package, claim
from galileo_falling_bodies import vacuum_prediction

with Package("my_research") as pkg:
    apollo_15 = claim(r"""
        Apollo 15 astronaut David Scott demonstrated that a hammer and feather
        fall at the same rate on the Moon (no atmosphere).
    """, given=[vacuum_prediction])

__all__ = ["apollo_15"]
EOF

# Compile and verify
gaia compile .
gaia check .

# Tag and push
git add . && git commit -m "Initial knowledge package"
git tag v1.0.0
git push origin main v1.0.0

# Register
gaia register
# → Creates PR to SiliconEinstein/gaia-registry

# === Registry CI (automatic) ===
# 1. Clones https://github.com/author/my-research @ v1.0.0
# 2. gaia compile . → verifies ir_hash
# 3. gaia check . → schema valid
# 4. Checks galileo-falling-bodies-gaia is registered → ✓
# 5. Labels PR "ci-passed"
# 6. After 72h waiting period → auto-merge
# 7. Builds wheel, uploads to GitHub Releases
# 8. Regenerates PEP 503 index, deploys to GitHub Pages

# === Consumer side ===
uv add my-research-gaia    # Just works
```
