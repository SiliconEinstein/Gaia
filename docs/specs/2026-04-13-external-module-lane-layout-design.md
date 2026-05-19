# External Module Lane Layout Design

**Status:** Superseded
**Date:** 2026-04-13
**Type of change:** Replacement + targeted visual behavior redesign
**Former scope:** React/Vite GitHub Pages template component layout.

> **Superseded by v0.5 cleanup (2026-05-16):** the React/Vite GitHub Pages template was removed with its component tests.

## Problem

The current external-module grouping change successfully preserves per-node semantics, but its collision-avoidance strategy pushes grouped external nodes downward inside the same drawing field as the internal reasoning graph. In practice this makes the module subgraph harder to read:

- grouped external boxes can still compete visually with internal colored nodes
- pushing groups downward creates awkward whitespace and unstable composition
- straight external edges fan out irregularly and clutter the center of the graph
- arrowheads at target nodes are hard to see when they land near node borders or overlapping strokes

The result solves overlap mechanically but weakens the visual hierarchy of the module view.

## Goal

Redesign the module subgraph so external references read as a dedicated input area rather than floating obstacles inside the internal reasoning layout.

The target behavior is:

- external references stay grouped by `sourceModule`
- each external reference remains its own small dashed white clickable node
- edges still connect directly to those specific small nodes
- internal reasoning nodes remain primarily governed by the ELK layout
- grouped external references are visually cleaner, with more regular edge entry and clearer target arrowheads

## Non-goals

- No change to `frontend/src/pages/GraphPage.tsx`
- No change to graph JSON schema, module overview, or chain-highlighting semantics
- No synthetic module hub, gateway node, or aggregated fake connector
- No ELK compound-node migration or broader graph-layout rewrite
- No change to external-node click behavior; clicking still navigates to the source module/node
- No attempt to fully bundle or reroute internal-to-internal edges

## User-approved visual direction

### Visual structure

In `ModuleSubgraph`:

- keep grouped external references enclosed by a labeled container
- keep individual external references as small dashed white nodes inside that container
- move all external-module groups into a fixed left-side docking lane outside the internal graph footprint
- treat the internal graph as the main canvas and the external lane as a supporting input region

### Layout behavior

The redesign replaces free-floating collision avoidance with deterministic lane placement.

Required behavior:

- compute the internal graph footprint from non-external layout nodes and relevant rendered edges
- place grouped external modules in a dedicated vertical lane to the left of that footprint
- keep a fixed horizontal gap between the lane and the internal graph
- vertically stack nodes within each external-module group using stable first-seen order
- compute each group’s preferred vertical position from the internal nodes it connects to, so the group stays near the region it influences
- if preferred positions would make two groups overlap, resolve the overlap with minimal vertical adjustment within the lane instead of pushing groups through the internal graph
- derive final rendered bounds from the adjusted post-layout geometry so the lane is fully visible in the SVG viewBox

This preserves semantic adjacency in Y while making X deterministic and visually clean.

### Edge behavior

The semantic contract stays unchanged:

- every edge still belongs to a real source and target node
- external edges still connect directly to the individual small external nodes
- no intermediary nodes or fake module-level connectors may be introduced

The visual routing changes only for edges that touch an external node:

- external-to-internal and internal-to-external edges should render as orthogonal-style paths rather than a single straight line
- the path should leave the external lane cleanly, align toward the target, and enter the target with a clearer final segment
- internal-to-internal edges may keep the current simpler rendering

A valid path shape is a three-segment route:

1. horizontal segment leaving the external node toward the graph
2. vertical segment aligning with the target entry band
3. final horizontal segment entering the target side

Exact bend coordinates may be derived deterministically from the two endpoints and a small lane-exit offset.

## Rendering hierarchy

To preserve readability:

1. external group containers render first
2. edges render above containers
3. nodes render above both

This ensures:

- group backgrounds never cover arrowheads or node fills
- nodes remain the topmost interactive objects
- external groups read as background structure rather than foreground clutter

## Arrow readability requirements

Edges touching external nodes must improve endpoint readability compared with the current straight-line rendering.

Required improvements:

- slightly thicker stroke for external-connected edges
- larger arrow marker dimensions than the current default
- darker or more assertive marker fill/stroke so the arrowhead remains visible
- a subtle light halo/underlay near the target end so arrowheads do not visually disappear into node borders or crossing strokes

These changes apply to external-connected edges only unless a shared implementation makes broader application simpler without harming internal-edge appearance.

## Implementation boundary

This remains a small template-pages redesign.

### Expected units

1. **External lane layout helper**
   - derive stable grouped externals from `externalRefs`
   - identify the internal graph footprint
   - compute deterministic lane X placement
   - compute group preferred Y from connected internal targets
   - resolve group overlap within the lane
   - emit adjusted external node positions and group bounds

2. **External edge routing helper**
   - detect whether an edge touches an external node
   - produce orthogonal rendered geometry for those edges
   - preserve internal-only edge geometry when neither endpoint is external

3. **Rendering updates**
   - render group boxes from adjusted lane layout
   - render external-connected edges with improved arrow treatment
   - keep node rendering and click handling unchanged

## Layout rules

Keep the rules deterministic and minimal:

- group external refs by normalized `sourceModule`, with empty names mapped to `External`
- preserve stable group order based on first appearance in `externalRefs`
- preserve stable node order within a group based on first appearance in `externalRefs`
- keep external nodes in a compact vertical stack within each group
- place all groups at the same lane X, outside the internal graph footprint
- compute each group’s preferred Y from the center of its connected internal target nodes
- when preferred Y positions overlap, move only as much as needed to separate group boxes by a fixed gap
- never move internal nodes during this redesign pass
- never place external groups back inside the internal graph footprint

## Edge geometry contract

Because `ModuleSubgraph` renders from ELK-derived geometry, post-layout external repositioning must continue to post-process rendered edge geometry.

Required behavior:

- keep graph-edge identities and roles unchanged
- if neither endpoint is external, preserve current edge rendering behavior
- if an edge touches an external node, recompute the rendered geometry from the adjusted endpoint positions using the orthogonal external-edge route
- maintain correct start/end attachment to the actual node positions after lane placement
- do not introduce synthetic graph structure, fake intermediate ids, or extra semantic edges

## Constraints

- Do not change edge semantics
- Do not move internal nodes
- Do not change navigation behavior for external nodes
- Do not broaden the redesign into the module overview or other pages
- Do not modify `frontend/src/pages/GraphPage.tsx`

## Testing

### Automated

Add focused tests for:

1. external groups are placed in a common side lane outside the internal footprint
2. group ordering remains stable while Y placement tracks connected internal targets
3. overlap resolution separates lane groups without moving internal nodes
4. external-connected edges render with orthogonal routed geometry derived from adjusted endpoints
5. internal-only edges preserve existing geometry behavior
6. arrow-marker configuration for external-connected edges uses the enhanced readable style

### Manual

In the template pages app, open a module with incoming external references from multiple modules and verify:

- external-module groups appear in a dedicated left-side lane
- each group is labeled and contains the correct dashed white nodes
- groups align roughly with the part of the internal graph they feed
- lines still terminate on specific small nodes
- external-connected edges enter the graph in a more regular pattern than before
- arrowheads at target nodes are clearly visible
- clicking an external node still navigates correctly
- internal reasoning nodes do not visibly reshuffle because of the lane layout pass

## Acceptance criteria

The redesign is complete when:

1. external-module groups no longer float inside the internal graph area
2. all grouped externals appear in a dedicated side lane with stable ordering
3. each external reference remains an individual clickable node
4. edges still connect to specific small nodes rather than to a module-level abstraction
5. external-connected edges render in a cleaner orthogonal style with clearer arrowheads
6. internal reasoning structure remains unchanged
7. tests cover lane placement, overlap resolution, external-edge routing, and preservation of internal-only geometry
