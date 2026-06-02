# Gaia Research Implementation Milestone Index

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans before each milestone implementation. Each milestone must have its own implementation plan with checkbox steps and reviewable success criteria.

**Goal:** Implement package-native `gaia research` in small, reviewable slices that preserve the canonical research-action invariants.

**Architecture:** `gaia research` is a thin CLI orchestration layer over existing Gaia package, inquiry, search, authoring, and build primitives. `.gaia/research/` stores artifacts and provenance only; accepted semantic state remains in package source or `.gaia/inquiry/`.

**Tech Stack:** Typer CLI, Gaia package metadata, `.gaia/inquiry/state.json`, package-local JSON/JSONL artifacts, pytest CLI tests.

---

## Shared Review Invariants

Every implementation PR must preserve these checks:

- `src/<pkg>/` is unchanged unless the milestone explicitly implements an accepted source-promotion command.
- `.gaia/research/` is not a focus registry or obligation ledger.
- Research commands default to artifact-only behavior.
- `gaia build check` remains the package structural validation path.
- LKM paper pulls require an explicit budget or explicit user action.
- Artifact references must stay traceable to Gaia-native identifiers, LKM identifiers, source paths, or content hashes.

## M1. Canonical CLI Skeleton And Manifest

**Plan:** `docs/superpowers/plans/2026-06-01-gaia-research-m1-cli-skeleton.md`

**Reviewable Success Criteria:**

- `gaia --help` lists `research`.
- `gaia research status <pkg>` verifies the target is an existing Gaia package and reports inquiry/research status.
- `gaia research explore <pkg> --mode scan --dry-run` writes `.gaia/research/manifest.json` and appends `.gaia/research/events.jsonl`.
- `gaia research assess <pkg> --focus <target> --artifact-only` records an artifact-only planning event and does not write stable source claims.
- Invalid targets produce a `gaia pkg scaffold --target ... --name ...` suggestion and do not create a parallel layout.
- Suggested gaps are printed as `gaia inquiry obligation add ...` commands, not persisted as a research-local obligation ledger.
- Targeted tests cover help registration, manifest/events creation, source immutability, invalid target behavior, and `gaia build check` compatibility.

## M2. Explore Scan

**Plan:** `docs/superpowers/plans/2026-06-01-gaia-research-m2-explore-scan.md`

**Reviewable Success Criteria:**

- `gaia research explore --mode scan` consumes normalized `gaia search lkm` JSON output.
- It writes a landscape artifact with query provenance, paper leads, pull candidates, coverage gaps, and candidate focuses.
- Pull budget defaults to `0`.
- `.gaia/lkm_packages/` is not created unless the user explicitly requests pulls.
- Candidate focuses remain artifact-local candidates and are not written to inquiry focus state automatically.
- Landscape refs preserve LKM provenance and can be resolved back to item refs, variable ids, paper ids, or query records.

## M2b. Port Selected Exploration Utilities

**Plan:** `docs/superpowers/plans/2026-06-01-gaia-research-m2b-port-exploration-utilities.md`

**Reviewable Success Criteria:**

- Ported deterministic utilities write `.gaia/research/` artifacts, not `.gaia/exploration/` canonical state.
- Paper-lead building, provenance normalization, pull-candidate deduplication, and rationale aggregation have direct unit tests.
- MapHealth / orphan / fragmentation signals become status/check signals or candidate obligations, never a durable parallel obligation ledger.
- Output refs are traceable to LKM search refs, paper ids, QIDs, or inquiry ids.
- `src/<pkg>/` remains unchanged.

## M3. Explore Expand

**Plan:** `docs/superpowers/plans/2026-06-01-gaia-research-m3-explore-expand.md`

**Reviewable Success Criteria:**

- `gaia research explore --mode expand` requires `--obligation`, `--focus`, or an equivalent accepted target.
- Targeted landscape artifacts link back to the selected inquiry id, focus, or accepted artifact.
- Pulls remain budgeted and explicit.
- Obligation coverage updates are artifacts or inquiry suggestions unless the user passes an explicit accept/write flag.

## M4. Assessment Artifact Schema

**Plan:** `docs/superpowers/plans/2026-06-01-gaia-research-m4-assessment-schema.md`

**Reviewable Success Criteria:**

- Assessment relation records validate against the v1 vocabulary: `supports`, `opposes`, `qualifies`, `undercuts`, `background_for`, `needs_more_evidence`.
- `promotion_hint` validates against the narrowed v1 set and the allowed relation-to-hint mapping.
- Every relation carries epistemic status and resolvable source refs.
- Schema validation rejects unsupported hints such as v1 `candidate_relation`.
- Validation writes no stable source claims.

## M5. Assess

**Plan:** `docs/superpowers/plans/2026-06-01-gaia-research-m5-assess.md`

**Reviewable Success Criteria:**

- `gaia research assess --focus ...` resolves a focus or obligation and selects relevant landscape artifacts.
- The assessment artifact links to the focus or obligation.
- Evidence packets include landscape items, not only paper titles or metadata.
- Supporting, opposing, qualifying, and undercutting refs are resolvable.
- New gaps are emitted as candidate obligations or `gaia inquiry obligation add ...` suggestions.
- Default behavior writes no stable claims.

## M6. Propose

**Plan:** Create a dedicated `docs/superpowers/plans/YYYY-MM-DD-gaia-research-m6-propose.md` before implementation.

**Reviewable Success Criteria:**

- `gaia research propose --from-assessment ...` writes proposal artifacts with open questions, hypotheses, and candidate obligations.
- Default behavior is artifact-only.
- `--accept` can write inquiry state or package questions when the lower Gaia primitive supports the target.
- It does not write stable truth claims.

## M7. `gaia-lkm-explore` Deprecation Gate

**Plan:** Create a dedicated `docs/superpowers/plans/YYYY-MM-DD-gaia-research-m7-lkm-explore-deprecation.md` before implementation.

**Reviewable Success Criteria:**

- M1-M5 cover status, broad scan, targeted expand, and assessment artifact workflows.
- Required deterministic utilities are migrated or explicitly left behind with rationale.
- `.gaia/exploration/` import/migration behavior is documented and tested.
- Docs and agent-facing instructions no longer describe `gaia-lkm-explore` as the canonical workflow.
- At least one real LKM-backed example runs through `gaia research` without the old entry point.
