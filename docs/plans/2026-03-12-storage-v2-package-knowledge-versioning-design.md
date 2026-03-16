# Storage v2 Package Commit and Knowledge Identity Design

## Goal

Clarify the storage model for package revisions, knowledge identity, chain snapshots, and visibility.

This document replaces the current ambiguous mix of:

- package-level versioning
- knowledge entity versioning
- publish visibility
- downstream graph/vector indexing

The target model is:

- package revisions are identified by `package_name + commit_hash`
- knowledge has both a logical name and an immutable entity hash
- chain does not have an independent entity version
- references in source remain logical
- references in storage resolve to immutable entity IDs within a specific package commit snapshot

## Current Implementation

### What Exists Today

The current `storage_v2` implementation is built around `StorageManager` and a publish-state-machine flow:

1. write package as `preparing`
2. write content rows
3. write graph rows
4. write vector rows
5. mark the package as `merged`

Recent fixes moved package rows toward version awareness by storing package snapshots under `(package_id, version)`. Modules and chains also carry `package_version`. Knowledge rows additionally carry `source_package_version`.

### Current Identity Model

Today the codebase effectively uses the following identities:

- package snapshot: `(package_id, version)`
- module snapshot: `(module_id, package_version)`
- chain snapshot: `(chain_id, package_version)`
- knowledge row: `(knowledge_id, version)` plus `source_package_version`

This means:

- package is treated as a versioned publish snapshot
- chain is treated as a package-scoped snapshot, not an independently versioned entity
- knowledge is treated partly as an independently versioned entity and partly as a package-scoped snapshot row

### Why The Current Model Is Still Incomplete

The problem is not just an implementation bug. The current model mixes two different concerns into the same `knowledge` row:

- entity identity: "what knowledge content is this?"
- publish membership: "which package revision currently exposes it?"

That creates several failure modes:

- a new package publish can overwrite visibility metadata for an older committed knowledge row
- package visibility is enforced by filtering fields on the knowledge row itself
- the same logical knowledge across commits does not have a first-class binding layer
- graph and vector stores must infer publish visibility indirectly instead of reading explicit membership

In short: package revision identity and knowledge entity identity are not cleanly separated.

## Design Principles

The target design should follow these rules:

1. Human-authored references use logical names, not hashes.
2. Immutable stored entities use content-derived hashes or immutable IDs.
3. Every package commit is a snapshot and must remain reproducible forever.
4. New commits must never mutate the meaning of old committed snapshots.
5. Visibility is determined by package commit membership, not by mutating entity rows.
6. Graph and vector stores are indexes over committed snapshots and immutable entities, not the source of truth.

## Final Target Model

### 1. Package Revision Identity

Each published package revision is uniquely identified by:

- `package_name`
- `commit_hash`

Optional human-facing display version may also exist:

- `revision_no`

But the true storage identity is:

- `(package_name, commit_hash)`

This matches the intended workflow:

- package state comes from a specific Git commit
- re-publishing means ingesting a new commit snapshot
- old snapshots remain readable

### 2. Knowledge Identity

Knowledge has two identities:

#### Logical identity

Used by authors and by the language layer:

- `package_name + knowledge_name`

This is how source code refers to knowledge.

#### Entity identity

Used by storage for immutability and deduplication:

- `knowledge_hash`

The hash is derived from normalized knowledge content and any fields that should contribute to entity identity, for example:

- knowledge type
- content
- prior
- keywords
- other semantic metadata

This means:

- if content does not change, the same `knowledge_hash` is reused
- if content changes, a new `knowledge_hash` is created

### 3. Knowledge "Version"

Under this model, the immutable entity hash is the real entity version.

We do not need a separate mandatory numeric `knowledge_version` in storage if:

- the logical identity is `package_name + knowledge_name`
- the immutable identity is `knowledge_hash`

A numeric version can still exist for UI or reporting, but it should not be the primary storage key.

### 4. Chain Identity

Chain does not have an independent entity version.

Chain exists only as part of a package commit snapshot.

Its identity is:

- `(package_name, commit_hash, chain_name)`

This means:

- chain changes are represented by a new package commit
- no separate `chain_version` field is required
- chain snapshots are reproducible within each package revision

## Required Binding Layer

The key missing piece in the current implementation is an explicit binding layer between logical names and immutable entities.

### Knowledge Binding

For each package commit, store:

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`

This gives the system a stable answer to:

"In package `P` at commit `C`, what immutable knowledge entity does logical name `K` refer to?"

This table is what allows:

- old commits to keep old knowledge bindings
- new commits to point the same logical name to a new entity hash
- unchanged knowledge to reuse the same entity hash

## Final Table Structure

The minimum target schema should be the following.

### 1. `package_revisions`

Represents a publishable package snapshot.

Fields:

- `package_name`
- `commit_hash`
- `parent_commit_hash`
- `revision_no`
- `status`
- `submitted_at`
- `manifest_json`

Primary key:

- `(package_name, commit_hash)`

Status values:

- `preparing`
- `reviewed`
- `committed`
- `failed`

### 2. `knowledge_entities`

Represents immutable knowledge content.

Fields:

- `knowledge_hash`
- `type`
- `content`
- `prior`
- `keywords_json`
- `metadata_json`
- `created_at`

Primary key:

- `knowledge_hash`

Notes:

- this is the canonical deduplicated knowledge store
- this table does not encode package visibility

### 3. `knowledge_bindings`

Maps logical knowledge names within a package revision to immutable knowledge entities.

Fields:

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`
- `module_name`
- `is_exported`

Primary key:

- `(package_name, commit_hash, knowledge_name)`

Secondary lookup:

- `(package_name, commit_hash, knowledge_hash)`

### 4. `module_snapshots`

Represents module metadata for a package revision.

Fields:

- `package_name`
- `commit_hash`
- `module_name`
- `role`
- `imports_json`
- `chain_names_json`
- `export_names_json`

Primary key:

- `(package_name, commit_hash, module_name)`

### 5. `chain_snapshots`

Represents chain state inside a package revision.

Fields:

- `package_name`
- `commit_hash`
- `chain_name`
- `module_name`
- `type`
- `steps_source_json`
- `steps_resolved_json`
- `chain_hash`

Primary key:

- `(package_name, commit_hash, chain_name)`

Notes:

- `steps_source_json` preserves logical references by knowledge name
- `steps_resolved_json` stores the resolved `knowledge_hash` values used for execution and indexing

### 6. `probability_records`

Review-derived probabilities for a package revision.

Fields:

- `package_name`
- `commit_hash`
- `chain_name`
- `step_index`
- `value`
- `source`
- `recorded_at`

Primary key recommendation:

- append-only table; no hard unique key required

### 7. `belief_snapshots`

Inference-derived beliefs for a package revision.

Fields:

- `package_name`
- `commit_hash`
- `knowledge_name`
- `knowledge_hash`
- `belief`
- `bp_run_id`
- `computed_at`

Primary key recommendation:

- append-only table; no hard unique key required

### 8. `resources`

Unchanged resource metadata table.

Primary key:

- `resource_id`

### 9. `resource_attachments`

Resource attachments should be package-revision aware when they target snapshot objects.

Fields:

- `resource_id`
- `package_name`
- `commit_hash`
- `target_type`
- `target_name`
- `role`
- `description`

Primary key recommendation:

- `(resource_id, package_name, commit_hash, target_type, target_name, role)`

## Graph and Vector Storage

### Vector Store

Vector storage should be keyed by immutable knowledge entity, not by package revision.

Recommended key:

- `knowledge_hash`

Reason:

- embeddings are a property of knowledge content
- the same knowledge entity may appear in many package revisions
- embeddings should be computed once and reused

### Graph Store

Graph data should be stored as package revision snapshots.

Recommended node identities:

- package revision node: `(package_name, commit_hash)`
- knowledge snapshot node: `(package_name, commit_hash, knowledge_name)`
- chain snapshot node: `(package_name, commit_hash, chain_name)`

Each knowledge snapshot node should also carry:

- `knowledge_hash`

This allows:

- historical graph reproducibility
- topology queries scoped to a specific package commit
- reuse of the same immutable knowledge entity across multiple revisions

## Final Interface Model

The API should separate:

- package-snapshot reads
- knowledge-entity reads
- logical-name resolution

### Package Revision APIs

- `write_package_revision(package_revision)`
- `commit_package_revision(package_name, commit_hash)`
- `get_package_revision(package_name, commit_hash)`
- `get_latest_committed_package_revision(package_name)`
- `list_package_revisions(package_name)`

### Knowledge Entity APIs

- `write_knowledge_entities(entities)`
- `get_knowledge_entity(knowledge_hash)`
- `get_knowledge_entities(knowledge_hashes)`

### Binding APIs

- `write_knowledge_bindings(bindings)`
- `get_knowledge_binding(package_name, commit_hash, knowledge_name)`
- `list_knowledge_bindings(package_name, commit_hash)`
- `resolve_knowledge_name(package_name, commit_hash, knowledge_name)`

### Chain Snapshot APIs

- `write_chain_snapshots(chains)`
- `get_chain_snapshot(package_name, commit_hash, chain_name)`
- `list_chain_snapshots(package_name, commit_hash, module_name=None)`

### Review / Inference APIs

- `write_probability_records(records)`
- `get_probability_history(package_name, commit_hash, chain_name, step_index=None)`
- `write_belief_snapshots(snapshots)`
- `get_belief_snapshot(package_name, commit_hash, knowledge_name)`

### Manager-Level Publish APIs

The publish pipeline should move from "write mutable package/version rows" to "create a new immutable revision snapshot":

- `ingest_package_revision(package_revision, modules, knowledge_entities, bindings, chains, embeddings)`
- `retry_package_revision(package_name, commit_hash)`
- `mark_package_revision_failed(package_name, commit_hash, error)`

## Write Flow

### Proposed Commit Ingest Flow

1. Insert `package_revisions(status='preparing')`
2. Canonicalize all knowledge objects in the commit
3. Compute `knowledge_hash` for each logical knowledge item
4. Upsert `knowledge_entities`
5. Write `knowledge_bindings`
6. Compile chain snapshots and resolve `knowledge_name -> knowledge_hash`
7. Write `chain_snapshots`
8. Write graph snapshot
9. Write vector embeddings keyed by `knowledge_hash`
10. Write probabilities and beliefs
11. Mark package revision as `committed`

On failure:

- leave the new package revision as `preparing` or `failed`
- do not delete old committed revisions
- do not mutate historical bindings

## Read Flow

### Latest Package Read

1. resolve latest committed `(package_name, commit_hash)`
2. read module snapshots and chain snapshots for that revision
3. resolve knowledge through `knowledge_bindings`

### Historical Package Read

1. take explicit `(package_name, commit_hash)`
2. read the exact snapshot rows for that revision

### Knowledge History Read

1. query `knowledge_bindings` by `(package_name, knowledge_name)` across commits
2. join each binding to `knowledge_entities`

This gives a full logical history of a knowledge item across package commits.

## Comparison: Current vs Target

### Current

- package version is partially modeled
- chain is package-scoped
- knowledge is both an entity row and a publish-membership row
- visibility is inferred by filtering mutable fields on downstream content rows

### Target

- package commit snapshot is the publish identity
- knowledge hash is the immutable entity identity
- knowledge name is the logical source identity
- chain exists only as a package commit snapshot
- visibility comes from committed package revisions and snapshot membership tables

## Migration Guidance

The migration should be done in two phases.

### Phase 1: Stop the Current Leaks

Short-term safety fixes if the team keeps the current schema temporarily:

- make all snapshot tables fully commit-aware
- do not let package re-publish overwrite previous committed rows
- do not infer topology visibility from graph stubs
- do not use `knowledge` rows as the publish-membership source of truth

### Phase 2: Move To Binding-Based Design

Planned structural changes:

1. add `package_revisions`
2. add `knowledge_entities`
3. add `knowledge_bindings`
4. migrate current `knowledge` table responsibilities into:
   - entity storage
   - binding storage
5. convert chain storage into explicit snapshot rows keyed by package commit
6. update graph/vector ingestion to consume resolved snapshot data

## Decisions

### Accepted

- package identity is `package_name + commit_hash`
- package display revision number is optional and derived
- knowledge logical identity is `package_name + knowledge_name`
- knowledge immutable identity is `knowledge_hash`
- chain has no independent entity version
- references in source remain logical-name based
- references in storage resolve to immutable IDs within a package revision

### Rejected

- treating `package_name` alone as unique
- treating `knowledge_name` alone as unique in storage
- mutating old committed snapshots when new commits arrive
- using downstream graph/vector rows as the source of truth for visibility
- forcing chain to have an independent version number without a real need

## Summary

The final design should model three different things explicitly:

- immutable knowledge entities
- immutable package commit snapshots
- bindings from logical names in a snapshot to immutable knowledge entities

That separation is what allows:

- reproducible history
- safe re-publish
- logical authoring by name
- internal deduplication by hash
- chain snapshots without independent chain versioning
- correct graph/vector indexing without cross-version contamination
