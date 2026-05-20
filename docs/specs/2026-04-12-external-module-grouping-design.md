# Module Subgraph External Module Grouping Design

**Status:** Superseded
**Date:** 2026-04-12
**Type of change:** Clarification + targeted visual behavior replacement
**Former scope:** React/Vite GitHub Pages template component layout.

> **Superseded by v0.5 cleanup (2026-05-16):** the React/Vite GitHub Pages template was removed with its component tests.

## Problem

In the module subgraph view, external references from other modules already render as individual dashed white nodes and are enclosed by a lightly styled module box. However, the current layout still treats those external nodes as independent layout items, so nodes from the same source module can end up visually scattered. That weakens the grouping signal and makes it harder to read which outside module contributes which premises into the current conclusion.

## Goal

Make external references from the same source module read as one visual cluster while preserving the existing reasoning semantics:

- external references from the same module should be placed together intentionally
- each external reference must remain its own small clickable node
- every edge must still connect to the specific small node, not to a synthetic module-level hub
- internal module reasoning layout should remain unchanged as much as possible

## Non-goals

- No change to `frontend/src/pages/GraphPage.tsx`
- No change to graph JSON schema, module overview, or chain-highlighting semantics
- No new module-level edge type or synthetic “module gateway” node
- No change to external-node click behavior; clicking still navigates to the source module/node

## User-approved interaction and visual behavior

### Visual structure

For external references in `ModuleSubgraph`:

- group them by `sourceModule`
- render a labeled group container around each source module
- keep each external reference as its own white dashed node inside the group
- preserve current low-key styling: light group background / border, small module label, existing white node cards
- if an external ref has no `sourceModule`, group it under the fallback label `External`

### Layout behavior

The change is not just decorative. External references from the same source module should be actively arranged together so the group box encloses a compact cluster instead of whatever positions ELK happened to assign.

The intended result is:

- same-module external nodes sit adjacent to each other
- different external-module groups remain visually separated
- internal nodes and internal reasoning lines are not reinterpreted or regrouped
- edges still originate from the exact external node being referenced
- final rendered bounds (including SVG viewBox sizing and any clipping-sensitive canvas extents) must be derived from the adjusted post-layout geometry rather than raw ELK dimensions so downward-pushed groups remain visible

### Interaction behavior

- clicking an external node still calls the existing module-navigation behavior
- the group container itself is not interactive
- chain highlighting continues to operate on real node ids only

## Implementation boundary

This should remain a small template-pages change.

### Expected units

1. **Grouping data helper**
   - derive stable per-module external groups from `externalRefs`
   - normalize empty module names to the fallback label `External`
   - provide ordered node ids for each source module

2. **Grouped external layout helper**
   - take ELK output and reposition only external nodes into compact per-module clusters
   - keep original node sizes
   - leave internal node positions unchanged
   - produce updated group rectangles from the adjusted external-node positions
   - produce updated edge endpoints for any edge whose source or target node was repositioned

3. **ModuleSubgraph rendering update**
   - render using adjusted node positions
   - render edges from post-processed edge geometry aligned to the adjusted node positions
   - continue rendering group boxes behind nodes

## Layout rules

Keep the rules simple and deterministic:

- group by normalized `sourceModule`, with empty names mapped to `External`
- preserve a stable group order based on first appearance in `externalRefs`
- within a group, preserve a stable node order based on first appearance in `externalRefs`
- arrange grouped external nodes in a compact vertical stack
- maintain consistent intra-group spacing and group padding
- anchor each group inside the footprint of that group’s original ELK-assigned external-node positions so the overall graph shape does not jump dramatically
- if two external-module groups would overlap after restacking, push the later group downward by a fixed gap until the group boxes no longer overlap
- do not run a broader collision-avoidance pass against internal nodes; keeping each group inside its original ELK footprint is sufficient for this targeted change

A valid implementation may anchor each group by the original group bounding box, then restack that group’s nodes vertically within or near that same box.

## Edge geometry contract

Because `ModuleSubgraph` currently renders edges from ELK layout sections, any post-layout node repositioning must also post-process edge geometry.

Required behavior:

- keep the original graph edges and roles unchanged
- if an edge endpoint belongs to a repositioned external node, recompute that rendered endpoint from the adjusted node position
- if neither endpoint moved, preserve the ELK-produced edge geometry as-is
- no new intermediary nodes, edge roles, or module-level connectors may be introduced

For this targeted change, a straight-line endpoint rewrite is sufficient; preserving multi-segment ELK routing is not required.

## Constraints

- Do not change edge semantics or fabricate intermediary edges
- Do not move internal nodes
- Do not require ELK compound nodes or a larger layout-engine rewrite
- Do not add new persistent graph metadata just for this UI effect

## Testing

### Automated

Add focused tests for:

1. grouping helper returns stable source-module groups
2. grouped external layout only repositions external nodes
3. grouped external layout keeps same-module nodes aligned into a compact cluster
4. group box computation reflects adjusted positions, not raw ELK positions
5. edge geometry is updated when a repositioned external node participates in an edge

### Manual

In the template pages app:

- open a module with external references from multiple modules
- verify same-module external refs are visually clustered
- verify each edge still terminates on the specific small external node
- verify clicking an external node still navigates correctly
- verify internal nodes do not visibly reshuffle because of the grouping pass

## Acceptance criteria

The change is complete when:

1. external references from the same source module are visibly grouped together in `ModuleSubgraph`
2. each external reference remains an individual clickable node
3. lines still connect to the small nodes rather than to a module-level abstraction
4. internal reasoning structure is unchanged
5. tests cover grouping, post-layout repositioning, and edge-endpoint updates for moved external nodes
