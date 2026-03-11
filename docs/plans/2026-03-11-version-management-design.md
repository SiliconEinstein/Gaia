# Package Version Management Design

> Status: Draft
> Date: 2026-03-11
> Related: [publish-pipeline.md](../foundations/review/publish-pipeline.md)

## 1. Design Principles

1. **Package semver, auto-derived.** The system determines the version bump (patch/minor/major) from the manifest diff. Authors declare intent; the system verifies.

2. **Knowledge has no independent version.** Content hash tracks changes. Package version fully determines every knowledge unit's content.

3. **Lock, don't range.** Dependencies are pinned to exact versions, like citing a specific paper. No range constraints (`^`, `>=`). Updates are explicit.

4. **No administrative lifecycle.** No `superseded` or `retracted` status. Conclusions are challenged by publishing counter-evidence; BP handles the rest.

## 2. Version Model

```
Package:     name @ semver (X.Y.Z)
Knowledge:   name + content_hash (no independent version number)
Manifest:    {knowledge_name → content_hash, ...}
```

- Package semver is auto-derived from the manifest diff against the previous published version.
- Knowledge content hash enables change detection, deduplication, and integrity verification.
- Package version + knowledge name fully identifies the content. No need for a separate knowledge version counter.

## 3. Semver Semantics

The three semver levels map to change impact:

| Level | Trigger | Examples |
|-------|---------|----------|
| **Patch** (x.y.Z) | No semantic change | Typo fix, wording clarification, minor prior adjustment |
| **Minor** (x.Y.z) | Semantic change or expansion, no downstream breakage | New knowledge/chain/module, new export, internal restructuring |
| **Major** (X.y.z) | Breaking interface change | Exported knowledge content substantively modified, export removed |

### Classification criteria

The key question: **if a downstream package references your exported knowledge, does its reasoning still hold?**

- Yes, unchanged → Patch or Minor
- Yes, but the package grew → Minor
- Potentially not → Major

### Case mapping

| Case | Change | Semantic? | Interface? | Level |
|------|--------|-----------|------------|-------|
| Intermediate typo fix | Content | No | No | Patch |
| Intermediate semantic change, may affect export belief | Content + belief | Yes | No | Minor |
| Export typo fix | Content | No | No | Patch |
| Export substantive content change | Content | Yes | Yes | Major |
| Prior adjustment | Metadata | No | No | Patch |
| New knowledge + chain, exports unchanged | Structure | Yes | No | Minor |
| New export added | Interface expansion | — | Yes (non-breaking) | Minor |
| Export removed | Interface contraction | — | Yes (breaking) | Major |

## 4. Modification Principles

### Review routing

| | Patch | Minor | Major |
|--|-------|-------|-------|
| **Review** | None — auto-verify diff confirms no semantic change | Lightweight (single engine) | Full peer review |
| **Trigger BP?** | No | Yes | Yes |
| **BP scope** | — | Local propagation | Wide propagation |
| **Downstream notification?** | No | No | Yes, all referencing packages |
| **Downstream action needed?** | None | None | Must confirm references still valid, or pin old version |

### BP update strategy (at billion scale)

Full global recomputation is infeasible. Incremental propagation:

```
Patch:   No propagation.
         Semantic content unchanged → beliefs unchanged.
         Minor prior adjustments batched / lazily updated.

Minor:   Local propagation.
         From changed nodes, propagate along factor graph
         until delta < ε (convergence).
         Typically attenuates within a few hops.
         Does not proactively cross package boundaries.

Major:   Wide propagation.
         From changed export nodes, propagate to all
         downstream referencing packages.
         Each referencing package triggers local BP recomputation.
         Layer-by-layer expansion until global convergence.
```

## 5. Submission Commands

```bash
gaia publish              # Initial publication → v1.0.0
gaia publish patch        # No semantic change
gaia publish minor        # Semantic change / expansion
gaia publish major        # Breaking interface change
```

### Verification rules

- **No under-reporting:** Declared level must be ≥ detected level. `gaia publish patch` with structural changes → rejected, suggests `minor`.
- **Over-reporting allowed:** `gaia publish major` for a minor-level change → accepted, routes to stricter review.

### Build-time diff preview

`gaia build` shows the diff and projected version before publish:

```
Changes detected (vs v1.2.0):
  modified:  reasoning.inclined_obs (content, hash changed)
  added:     reasoning.new_evidence
  structure: 1 new chain
  export:    unchanged

Projected: minor (v1.3.0)
```

## 6. Dependency Management

### Pinning model

Dependencies are pinned to exact versions. No range constraints.

Analogy: citing a paper. You cite "Newton 1687", not "Newton >=1687". Your reasoning was reviewed against a specific version of the referenced knowledge.

```yaml
# package.yaml — declare dependencies
dependencies:
  - package: newton_principia          # version omitted on first use

# gaia.lock — generated by gaia build
newton_principia: 2.3.1               # pinned to exact version
```

### Resolution workflow

```
gaia build (no lock file):
  1. Read dependencies from package.yaml
  2. Resolve each to latest approved version
  3. Generate gaia.lock
  4. Compile with resolved versions

gaia build (with lock file):
  → Use locked versions. Deterministic compilation.

gaia update <package>:
  → Re-resolve to latest approved version
  → Update gaia.lock
  → This counts as a revision — needs rebuild + review
```

### No constraint solver needed

No `^`, `>=`, `~` operators. No SAT solving. Lock file is a simple `{package_name: version}` mapping. At billion-package scale, this simplicity is a significant advantage.

## 7. No Supersedes / Retraction Mechanism

Knowledge lifecycle is managed entirely through BP, not administrative status.

### Challenging existing conclusions

To argue that a previous package's conclusions are wrong, publish a new package:

```
new_package:
  ref: old_package.conclusion_X
  chain: counter_evidence → conclusion_X_is_flawed
         (contradicts old_package.conclusion_X)

BP automatically recomputes:
  old_package.conclusion_X: belief 0.82 → 0.35
```

### Why no administrative status?

- **Superseded?** Publish better knowledge → old belief naturally decreases.
- **Retracted?** Publish counter-evidence → old belief drops.
- **Search ranking?** Low-belief knowledge naturally ranks lower.

Package has exactly one status: `approved`. Everything else is handled by the knowledge graph and BP.

### Comparison with academic publishing

| Academic | Gaia |
|----------|------|
| Retraction notice | New package with counter-evidence |
| Superseding paper | New package with better reasoning |
| Citation count decline | Belief decrease via BP |
| Editorial withdrawal | Not needed — BP is the arbiter |

## 8. Version Coexistence and Graph Connections

When a Major version is published, both old and new versions may coexist in the active graph (downstream packages may still pin the old version).

| Version level | Old/new coexist? | Graph connection? | BP? |
|--------------|-----------------|-------------------|-----|
| Patch | No (old retires) | Not needed | No |
| Minor | No (interface unchanged) | Not needed | No |
| Major | Yes (downstream may pin old) | Auto-created between old/new exports | Yes |

### Lifecycle of Major version connections

```
1. Package publishes Major version
   → System creates factor between old and new export nodes

2. Downstream packages gradually update dependencies

3. Last downstream package updates to new version
   → Old version has no references
   → Retires from active graph to archive

4. Connection removed (no longer needed)
```

Archive: old versions remain queryable for historical purposes but do not participate in BP.

## 9. Open Questions

1. **Patch auto-verification** — how does the system verify "no semantic change"? Content hash diff + structural diff is necessary, but is it sufficient? Should there be a lightweight LLM check?
2. **Major version notification** — push notification to downstream package authors? Or lazy detection on their next `gaia build`?
3. **Concurrent publishes** — two authors publish revisions to the same package simultaneously. Last-write-wins? Conflict detection?
4. **Archive storage** — how are retired versions stored? Separate table? Same table with status flag?
5. **BP batch scheduling** — for Minor updates, how often to run incremental BP? On every publish? Batched?
