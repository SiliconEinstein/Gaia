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
                   │      gaia-pkg-galileo/           │
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
├── packages/
│   ├── galileo-falling-bodies/
│   │   ├── Package.toml
│   │   ├── Versions.toml
│   │   └── Deps.toml
│   ├── aristotle-mechanics/
│   │   ├── Package.toml
│   │   ├── Versions.toml
│   │   └── Deps.toml
│   └── ...
├── .github/
│   └── workflows/
│       ├── register.yml          # PR validation
│       ├── publish.yml           # Build wheel + upload to Releases + update index
│       └── index.yml             # Regenerate full PEP 503 index
├── registry.toml                 # Global registry config
└── README.md
```

### 2.1 Package Metadata

**Package.toml** — one per package, created at first registration:

```toml
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
name = "galileo-falling-bodies"
pypi_name = "gaia-pkg-galileo-falling-bodies"    # Python package name
repo = "https://github.com/galileo/falling-bodies"
description = "Galileo's falling bodies argument"
created_at = "2026-04-02T10:00:00Z"
```

**Versions.toml** — appended with each new version:

```toml
[versions."4.0.0"]
ir_hash = "sha256:a1b2c3d4..."
wheel_hash = "sha256:f9e8d7c6..."    # SHA-256 of the .whl file (for PEP 503)
git_tag = "v4.0.0"
registered_at = "2026-04-02T10:30:00Z"
wheel = "gaia_pkg_galileo_falling_bodies-4.0.0-py3-none-any.whl"

[versions."4.1.0"]
ir_hash = "sha256:e5f6g7h8..."
wheel_hash = "sha256:b5a4c3d2..."
git_tag = "v4.1.0"
registered_at = "2026-04-10T15:00:00Z"
wheel = "gaia_pkg_galileo_falling_bodies-4.1.0-py3-none-any.whl"
```

**Deps.toml** — dependencies per version (auto-generated from `pyproject.toml` by `gaia register`, verified by CI):

```toml
[deps."4.0.0"]
"gaia-pkg-aristotle-mechanics" = ">= 1.0.0"

[deps."4.1.0"]
"gaia-pkg-aristotle-mechanics" = ">= 1.0.0"
"gaia-pkg-newton-mechanics" = ">= 2.0.0"
```

`Deps.toml` is derived from the package's `pyproject.toml` (filtered to `gaia-pkg-*` dependencies only). `gaia register` generates it automatically; CI verifies consistency with the source `pyproject.toml`.

### 2.2 Global Config

**registry.toml:**

```toml
[registry]
name = "Gaia Official Registry"
url = "https://gaia-registry.github.io/registry/simple/"

[policy]
new_package_wait_hours = 72      # 3 days for new packages
version_update_wait_hours = 1    # 1 hour for version updates
require_review = false           # Phase 1: no review gate
min_review_count = 0             # Phase 1: no reviews required

[index]
github_pages_branch = "gh-pages"
releases_repo = "gaia-registry/registry"  # Where wheels are stored as Releases
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
## Register: gaia-pkg-galileo-falling-bodies v4.0.0

- **Repository:** https://github.com/galileo/falling-bodies
- **Tag:** v4.0.0
- **IR Hash:** sha256:a1b2c3d4...

### Exported claims
- `vacuum_prediction` — In a vacuum, objects of different mass fall at the same rate.
- `air_resistance` — Observed speed differences are caused by air resistance.

### Dependencies
- gaia-pkg-aristotle-mechanics >= 1.0.0
```

### 3.3 CI Validation (`register.yml`)

```yaml
name: Validate Registration
on:
  pull_request:
    paths: ['packages/**']

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Parse registration PR
        id: parse
        run: python scripts/parse_registration_pr.py

      - name: Clone package repo
        run: git clone ${{ steps.parse.outputs.repo_url }} pkg
             && cd pkg && git checkout ${{ steps.parse.outputs.git_tag }}

      - name: Install gaia-lang
        run: uv sync

      - name: Reproducible build
        run: |
          cd pkg
          gaia compile .
          # Verify ir_hash matches what author declared
          diff <(cat .gaia/ir_hash) <(echo "${{ steps.parse.outputs.ir_hash }}")

      - name: Schema validation
        run: cd pkg && gaia check .

      - name: Dependency check
        run: |
          # Verify all gaia-pkg-* dependencies are registered in this registry
          python scripts/check_deps_registered.py \
            --deps pkg/pyproject.toml \
            --registry packages/

      - name: UUID uniqueness check
        run: |
          # Verify UUID is not already taken by a different package
          python scripts/check_uuid_unique.py \
            --package ${{ steps.parse.outputs.package_name }} \
            --registry packages/

      - name: Repository ownership check
        run: |
          # Verify PR author has write access to the declared repository
          gh api repos/${{ steps.parse.outputs.repo_owner_and_name }}/collaborators/${{ github.event.pull_request.user.login }}/permission \
            --jq '.permission' | grep -qE 'admin|write'

      - name: Label and schedule auto-merge
        if: success()
        run: |
          # Determine waiting period
          if [ "${{ steps.parse.outputs.is_new_package }}" = "true" ]; then
            WAIT_HOURS=72
          else
            WAIT_HOURS=1
          fi
          gh pr label ${{ github.event.pull_request.number }} --add "ci-passed"
          # Custom bot/action enforces waiting period before merge
          python scripts/schedule_auto_merge.py \
            --pr ${{ github.event.pull_request.number }} \
            --wait-hours $WAIT_HOURS
```

### 3.4 Build & Publish (`publish.yml`)

Triggered when a registration PR is merged:

```yaml
name: Build and Publish
on:
  push:
    branches: [main]
    paths: ['packages/**']
concurrency:
  group: publish          # Serialize all publish runs to avoid index races
  cancel-in-progress: false

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: write    # For creating Releases
      pages: write       # For updating GitHub Pages
    steps:
      - uses: actions/checkout@v4

      - name: Detect changed packages
        id: changed
        run: python scripts/detect_changed_versions.py

      - name: Clone, build, upload
        run: |
          for pkg_info in ${{ steps.changed.outputs.packages }}; do
            REPO_URL=$(echo $pkg_info | jq -r .repo)
            GIT_TAG=$(echo $pkg_info | jq -r .tag)
            PKG_NAME=$(echo $pkg_info | jq -r .pypi_name)
            VERSION=$(echo $pkg_info | jq -r .version)

            # Clone and build
            git clone $REPO_URL build_pkg
            cd build_pkg && git checkout $GIT_TAG
            uv build --wheel

            # Compute wheel file hash for PEP 503
            WHEEL_FILE=$(ls dist/*.whl)
            WHEEL_HASH=$(sha256sum $WHEEL_FILE | cut -d' ' -f1)

            # Upload wheel as GitHub Release asset (release/ prefix avoids git tag collision)
            gh release create "release/${PKG_NAME}-${VERSION}" \
              $WHEEL_FILE \
              --repo gaia-registry/registry \
              --title "${PKG_NAME} ${VERSION}" \
              --notes "Auto-published by registry CI"

            # Record wheel_hash in Versions.toml
            python scripts/update_wheel_hash.py \
              --package $PKG_NAME --version $VERSION --hash $WHEEL_HASH

            cd .. && rm -rf build_pkg
          done

      - name: Commit wheel hashes
        run: |
          git add packages/
          git commit -m "ci: record wheel hashes" || true
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
├── gaia-pkg-galileo-falling-bodies/
│   └── index.html                          # Per-package: lists all versions
├── gaia-pkg-aristotle-mechanics/
│   └── index.html
└── ...
```

### 4.2 Root index.html

```html
<!DOCTYPE html>
<html><body>
<a href="/gaia-pkg-galileo-falling-bodies/">gaia-pkg-galileo-falling-bodies</a>
<a href="/gaia-pkg-aristotle-mechanics/">gaia-pkg-aristotle-mechanics</a>
</body></html>
```

### 4.3 Per-Package index.html

```html
<!DOCTYPE html>
<html><body>
<a href="https://github.com/gaia-registry/registry/releases/download/release/gaia-pkg-galileo-falling-bodies-4.0.0/gaia_pkg_galileo_falling_bodies-4.0.0-py3-none-any.whl#sha256=f9e8d7c6">
  gaia_pkg_galileo_falling_bodies-4.0.0-py3-none-any.whl
</a>
<a href="https://github.com/gaia-registry/registry/releases/download/release/gaia-pkg-galileo-falling-bodies-4.1.0/gaia_pkg_galileo_falling_bodies-4.1.0-py3-none-any.whl#sha256=b5a4c3d2">
  gaia_pkg_galileo_falling_bodies-4.1.0-py3-none-any.whl
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

REGISTRY_REPO = "gaia-registry/registry"
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
url = "https://gaia-registry.github.io/registry/simple/"
```

### 5.2 Installing Packages

```bash
uv add gaia-pkg-galileo-falling-bodies
# 1. uv queries https://gaia-registry.github.io/registry/simple/gaia-pkg-galileo-falling-bodies/
# 2. Gets HTML with download links pointing to GitHub Releases
# 3. Downloads wheel, verifies hash
# 4. Installs into .venv

# Version pinning works as expected
uv add "gaia-pkg-galileo-falling-bodies >= 4.0.0, < 5.0.0"
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
Consumer does `uv add gaia-pkg-galileo`
    ↓
uv queries GitHub Pages index (served from gh-pages branch)
    ↓ Only Registry CI (publish.yml) can write to gh-pages
Download link points to GitHub Releases
    ↓ Only Registry CI can create Releases
Wheel was built by Registry CI from verified source
    ↓ register.yml verified: ir_hash match, schema valid, deps registered
Source is author's git repo at specific tag
    ↓ Immutable git tag, auditable
```

**Guarantee:** Every package on the index was compiled and verified by Registry CI. No package can enter the index without passing validation.

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
uv add gaia-pkg-galileo        # Install from registry
uv add --upgrade gaia-pkg-galileo  # Upgrade to latest

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
uv init --lib gaia-pkg-my-research
uv add gaia-lang
uv add gaia-pkg-galileo-falling-bodies  # Cross-package dependency

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
# → Creates PR to gaia-registry/registry

# === Registry CI (automatic) ===
# 1. Clones https://github.com/author/my-research @ v1.0.0
# 2. gaia compile . → verifies ir_hash
# 3. gaia check . → schema valid
# 4. Checks gaia-pkg-galileo-falling-bodies is registered → ✓
# 5. Labels PR "ci-passed"
# 6. After 72h waiting period → auto-merge
# 7. Builds wheel, uploads to GitHub Releases
# 8. Regenerates PEP 503 index, deploys to GitHub Pages

# === Consumer side ===
uv add gaia-pkg-my-research    # Just works
```
