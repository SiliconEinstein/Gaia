# V1 Shared Knowledge Package File Formats

## Purpose

This document defines the shared V1 text-file formats used to exchange Gaia knowledge packages.

It does not define how canonicalization, review, or revision are implemented. Those operations belong to higher-layer formalization services, not to the Gaia kernel.

This document defines only:

1. the package directory / repository layout
2. the `Gaia.toml` manifest format
3. the `package.yaml` content format
4. the `review_report` sidecar format

It assumes the V1 static structure defined in [knowledge-package-static.md](knowledge-package-static.md).

It does not cover:

- canonicalization algorithms
- review algorithms
- revision algorithms
- `Gaia.lock`
- publish / archive protocol
- global Gaia graph integration
- cross-package identity resolution policy
- contradiction / retraction semantics
- prior / belief propagation
- BP

Those belong to later layers:

- V2: global Gaia graph integration
- V3: probabilistic semantics and propagation

## Boundary

V1 defines a knowledge package as a portable directory or repository, not as a single standalone object blob.

The shared exchange unit is therefore:

- one package root
- one manifest file
- one package content file
- zero or more review report files
- zero or more externally referenced resources

Implementations may construct or consume these files in different ways, but the on-disk and exchange shapes should remain the same.

## 1. Package Layout

The recommended V1 package layout is:

```text
<package-root>/
├── Gaia.toml
├── package.yaml
├── reviews/
│   └── <review_id>.yaml
└── resources/
    └── ...
```

### Required files

- `Gaia.toml`
- `package.yaml`

### Optional files and directories

- `reviews/`
- `resources/`

### Layout rules

#### 1. `Gaia.toml` is the package-management manifest

It carries package metadata and dependency declarations.

#### 2. `package.yaml` is the package content file

It serializes the V1 static package schema:

- `closure` (global knowledge objects)
- `module` (chains of closures and inferences, with imports and exports)
- `package`-level exports

#### 3. `reviews/*.yaml` are sidecar review artifacts

They do not mutate `package.yaml`.

#### 4. `resources/` holds external payloads

Large code files, datasets, figures, tables, logs, notebooks, and other bulky materials should live in external files and be referenced through `metadata.refs[]`, rather than being embedded inline in YAML when that would be impractical.

## 2. Gaia.toml

`Gaia.toml` is the package-management manifest.

It is a UTF-8 TOML file.

### Role

`Gaia.toml` should contain:

- package-level metadata
- package version information
- dependency declarations

It should not duplicate the full package content graph stored in `package.yaml`.

### Minimal shape

```toml
schema_version = "gaia.toml.v1"

[package]
name = "example-package"
version = "0.1.0"
description = "Optional description"
authors = ["Example Author"]

[dependencies]
some-package = ">=1.0"
another-package = ">=2.0, <3.0"
```

### Notes

- `name` and `version` are package-management identifiers
- the package's internal reasoning content still lives in `package.yaml`
- `Gaia.lock` is intentionally not part of V1 shared package formats yet

## 3. package.yaml

`package.yaml` is the package content file.

It is a UTF-8 YAML file.

It serializes one complete V1 static `package`.

### Minimal shape

```yaml
schema_version: gaia.knowledge_package.v1
package_id: pkg_...

closures:
  - closure_id: cl_...
    closure_kind: claim
    content_mode: nl
    content: "Current methods do not explain X."
  - closure_id: cl_action_...
    closure_kind: action
    action_type: infer
    content: "Contrast behavior under two different conditions."

modules:
  - module_id: mod_...
    role: reasoning
    summary: "Short description of what this module establishes"
    imports:
      - closure: cl_...
        from: mod_...
        strength: strong
    exports: [cl_...]
    chain:
      - closure: cl_...
      - inference: "Applying the definition to contrast behaviors"     # anonymous
      - closure: cl_...
      - inference:                                                      # named (function application)
          content: "Applying contrastive analysis"
          action: cl_action_...
      - closure: cl_...

exports: [cl_...]

metadata: {}
```

### Required top-level fields

- `schema_version`
- `package_id`
- `modules`

### Optional top-level fields

- `closures` (closures may also be defined externally and referenced by `closure_id`)
- `exports`
- `metadata`

### Serialization rule

The structure inside `package.yaml` should follow the V1 static schema defined in [knowledge-package-static.md](knowledge-package-static.md).

This document does not redefine that internal schema. It only defines that `package.yaml` is the standard text-file serialization of that schema.

## 4. Review Report Sidecar

A review report is a separate UTF-8 YAML file.

Recommended location:

```text
reviews/<review_id>.yaml
```

### Role

A review report is attached to a package, but is not part of the package content file itself.

Multiple review reports may coexist for the same package.

### Minimal shape

```yaml
schema_version: gaia.review_report.v1
review_id: rr_...
package_id: pkg_...

module_reviews:
  - module_id: mod_...
    exported_closure_id: cl_...
    exported_closure_kind: claim
    conditional_prior: 0.72
    weak_points:
      - target_closure_id: cl_...
        proposed_closure_kind: setting
        proposed_content: "Assume near-vacuum conditions."
        dependency_strength: strong
        rationale: "Without this setting, the module does not support the exported claim."

notes: "Optional package-level notes."
metadata: {}
```

### Required top-level fields

- `schema_version`
- `review_id`
- `package_id`
- `module_reviews`

### `module_reviews[]`

Each `module_review` should contain:

- `module_id`
- `exported_closure_id`
- `exported_closure_kind`

Optional fields:

- `conditional_prior`
- `weak_points`
- `notes`

### `weak_points[]`

Each weak point may contain:

- `target_closure_id`
- `proposed_closure_kind`
- `proposed_content`
- `dependency_strength`
- `rationale`

### Review report rules

#### 1. Review does not rewrite `package.yaml`

The review report is a sidecar artifact.

#### 2. `conditional_prior` is local

If present, `conditional_prior` is a local score for one exported closure. It is not a future global belief score.

#### 3. `conditional_prior` is mainly for claim exports

For question exports, `conditional_prior` is usually omitted.

#### 4. Multiple reports are allowed

V1 does not require a single authoritative review result.

## Deferred Topics

The following file formats or protocols are intentionally deferred:

- `Gaia.lock`
- revised package materialization format
- package archive / publish protocol
- exact graph-level identity resolution
- prior / belief propagation
- BP

Those belong to later documents.
