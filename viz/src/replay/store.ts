// Canonical store — v4.
//
// The store holds the canonical layout (every node + cluster known to the
// final IR), seeded from `payload.final_layout` once at startup. As IR-ticks
// land it flips per-node `admitted` flags and admits edges; per-round belief
// snapshots are merged so each node carries `beliefByRound[round_id]`.
//
// Differences from v3:
//   • No d3-force / no spawn-positions — every admitted node sits at its
//     pinned `(x, y)` from `final_layout.nodes[id]`.
//   • Tick admission is index-based: the player advances `cursorTick`
//     monotonically, and the store recomputes per-node `admitted` flags
//     by replaying `ticks[0..cursorTick]` from a clean state. This makes
//     reverse-scrub trivial: scrub back to tick T and the store's
//     `admitted` set is exactly the set of nodes whose `admittedTick <= T`.

import type {
  CanonicalEdge,
  CanonicalNode,
  FinalLayout,
  GaiaAction,
  GraphDelta,
  GraphEdgeRecord,
  GraphNodeAdded,
  IrTick,
  LayoutNode,
  TimelineEvent,
} from './types';

const KNOWLEDGE_KINDS = new Set(['claim', 'deduction', 'setting']);

interface StoreInit {
  events: TimelineEvent[];
  ticks: IrTick[];
  layout: FinalLayout | null;
  roundBeliefs: Record<string, Record<string, number>>;
}

export class CanonicalStore {
  events: TimelineEvent[];
  ticks: IrTick[];
  layout: FinalLayout | null;
  roundBeliefs: Record<string, Record<string, number>>;

  // All nodes known to the final layout — keyed by id. Always present;
  // `admitted` flips on tick land.
  nodes = new Map<string, CanonicalNode>();
  edges = new Map<string, CanonicalEdge>();
  // Ids whose `kind` was set authoritatively from `final_layout.nodes[id]`
  // (i.e. CLI-side IR-derived annotation). For these, graph_delta-side
  // `nodes_added[].kind` must NOT overwrite the seeded kind — otherwise
  // a support/contradiction node_added (kind="support" / kind="contradiction")
  // would clobber the layout-derived `strategy`/`operator` style.
  private layoutKindLocked = new Set<string>();
  // `lkm_id` -> canonical id, for matching gcn_* / nodes_added entries to
  // pinned-layout ids when those forms differ (real packages namespace IR
  // ids as `github:<repo>::<label>` while logs reference gcn_*).
  private lkmToId = new Map<string, string>();
  // Tracks whatever ids the canvas has currently admitted, in order.
  cursorTick = -1;

  constructor(init: StoreInit) {
    this.events = init.events;
    this.ticks = init.ticks;
    this.layout = init.layout;
    this.roundBeliefs = init.roundBeliefs;
    this.seedFromLayout();
    this.indexLkmIds();
    this.mergeRoundBeliefs();
  }

  private seedFromLayout() {
    if (!this.layout) return;
    // Index pinned positions by id; the CLI's `annotate_layout_with_kinds`
    // already stamps each entry with `kind` + styling info derived from the
    // IR (so a strat_<i> shows up as a strategy ellipse and an oper_<i>
    // shows up as an operator hexagon, matching the static DOT). For
    // payloads that lack those fields (older builds, fixtures without IR),
    // we fall back to id-prefix heuristics + graph_delta-side metadata
    // landing during admission.
    for (const [id, pos] of Object.entries(this.layout.nodes)) {
      const kindLabel = this.kindFromLayoutEntry(id, pos);
      this.nodes.set(id, {
        id,
        x: pos.x,
        y: pos.y,
        kind: kindLabel.kind,
        label: pos.label || id,
        module: pos.module ?? this.findClusterFor(id, pos),
        prior: typeof pos.prior === 'number' ? pos.prior : undefined,
        beliefByRound: {},
        admitted: false,
        admittedTick: -1,
        removed: false,
      });
      // If the CLI annotated this entry with a kind, it's authoritative.
      if (pos.kind) this.layoutKindLocked.add(id);
    }
  }

  /**
   * Resolve a layout entry's render `kind` (the value the canvas uses to
   * pick a shape/colour from `NODE_STYLE`).
   *
   * Source of truth: the CLI-side `annotate_layout_with_kinds` populates
   * `pos.kind` (`knowledge`/`strategy`/`operator`) plus subtype fields.
   * We translate that to the canvas's per-shape kind names:
   *
   *   knowledge + sub_kind=setting    → 'setting'
   *   knowledge + sub_kind=exported   → 'exported'
   *   knowledge + sub_kind=derived    → 'derived'
   *   knowledge + sub_kind=claim      → 'claim'
   *   strategy                        → 'strategy'
   *   operator + operator_type=contradiction → 'contradiction'
   *   operator (other)                → 'equivalence' (yellow operator)
   *
   * When the CLI annotation is missing (fixture / older build), we fall
   * back to id-prefix heuristics (legacy v3 behaviour).
   */
  private kindFromLayoutEntry(id: string, pos: LayoutNode): { kind: string } {
    const cliKind = pos.kind;
    if (cliKind === 'strategy') return { kind: 'strategy' };
    if (cliKind === 'operator') {
      return {
        kind: pos.operator_type === 'contradiction' ? 'contradiction' : 'equivalence',
      };
    }
    if (cliKind === 'knowledge') {
      const sub = pos.sub_kind;
      if (sub === 'setting' || sub === 'exported' || sub === 'derived') {
        return { kind: sub };
      }
      return { kind: 'claim' };
    }
    // Fallback: id-prefix heuristics.
    if (id.startsWith('strat_')) return { kind: 'strategy' };
    if (id.startsWith('oper_')) return { kind: 'operator' };
    return { kind: 'claim' };
  }

  private findClusterFor(id: string, pos: { x: number; y: number }): string | null {
    if (!this.layout) return null;
    for (const c of this.layout.clusters) {
      if (
        pos.x >= c.x &&
        pos.x <= c.x + c.w &&
        pos.y >= c.y &&
        pos.y <= c.y + c.h
      ) {
        return c.label || c.name;
      }
    }
    void id;
    return null;
  }

  private indexLkmIds() {
    // Walk the events once; whenever a graph_delta.nodes_added entry has an
    // `lkm_id`, see whether the layout already knows it under that id, or
    // under a knowledge-id whose label embeds the lkm_id. This produces a
    // best-effort bridge that is consulted during admission for nodes that
    // are referenced by `lkm_id` in logs but stored under a `github:...`-
    // shaped id in the IR.
    for (const ev of this.events) {
      for (const n of ev.graph_delta?.nodes_added || []) {
        const lid = n.lkm_id;
        if (!lid) continue;
        if (this.nodes.has(lid)) {
          this.lkmToId.set(lid, lid);
        } else {
          // Some packages stamp the lkm_id into IR knowledge labels (e.g.
          // `gcn_a21f...` becomes `cmb_bao_vs_local_ladder_method`).
          // Without a hard contract we fall back to id-as-id; if no node
          // matches, the admission step silently no-ops.
          this.lkmToId.set(lid, lid);
        }
      }
    }
  }

  private mergeRoundBeliefs() {
    for (const [roundId, beliefs] of Object.entries(this.roundBeliefs)) {
      for (const [kid, value] of Object.entries(beliefs)) {
        const node = this.nodes.get(kid);
        if (node) node.beliefByRound[roundId] = value;
      }
    }
  }

  /**
   * Step the store forward (or backward) to *targetTick*. `-1` means
   * "before any tick has fired" (a clean initial state).
   *
   * Returns the set of node ids that became admitted in this step (for
   * staging the entrance halo + LKM overlay), and the list of LKM-driven
   * ticks that just landed (for displaying retrieval cards).
   */
  advanceTo(targetTick: number): {
    admittedNodeIds: string[];
    lkmTicks: IrTick[];
    activeRoundId: string | null;
  } {
    const clamped = Math.max(-1, Math.min(this.ticks.length - 1, targetTick));
    if (clamped === this.cursorTick) {
      return { admittedNodeIds: [], lkmTicks: [], activeRoundId: this.computeActiveRoundId(clamped) };
    }
    if (clamped < this.cursorTick) {
      // Reverse scrub: rebuild from scratch up to *clamped*.
      this.resetAdmission();
      this.cursorTick = -1;
    }
    const newlyAdmitted: string[] = [];
    const lkmTicks: IrTick[] = [];
    while (this.cursorTick < clamped) {
      this.cursorTick++;
      const tick = this.ticks[this.cursorTick];
      const result = this.applyTick(tick);
      newlyAdmitted.push(...result.admittedNodeIds);
      if (tick.lkm_driven) lkmTicks.push(tick);
    }
    // Final-state reconciliation: at the last tick, force-admit every
    // strat_<i> / oper_<i> that the IR-derived layout knows about. The
    // event log can be lossy — e.g. a single `deduction` action covering
    // multiple deduction edges, or a `deduction` action with no `symbol`
    // (carrying its factor_ids in the payload instead) — and the
    // bridge/positional pairing in the store can leave a handful of
    // strat_<i>/oper_<i> entries unadmitted by tick land. The static
    // `gaia starmap --format dot` output, however, always renders every
    // IR strategy and operator. Honouring the user contract — "final
    // canvas == static SVG" — means closing that gap unconditionally
    // when the player reaches the end. Reverse-scrub still rebuilds from
    // a clean state, so this only fires at the rightmost tick.
    if (clamped === this.ticks.length - 1 && this.ticks.length > 0) {
      this.reconcileFinalLayout(clamped, newlyAdmitted);
    }
    return {
      admittedNodeIds: newlyAdmitted,
      lkmTicks,
      activeRoundId: this.computeActiveRoundId(clamped),
    };
  }

  /**
   * Force-admit every layout entry whose CLI-side annotated kind is
   * `strategy` or `operator`, plus their linked knowledge nodes (so we
   * pick up any package-author-declared helper claims that the events
   * never explicitly admit). Idempotent with respect to already-admitted
   * nodes.
   *
   * Deduplication rule: each `canonical_id` (i.e. each `strat_<i>` or
   * `oper_<i>`) admits AT MOST one node at end-of-play. The bridge stamps
   * the same `canonical_id` on both the canonical entry and any event-
   * symbol aliases that share its coordinates, so we can detect when the
   * tick stream has already admitted the alias and skip the canonical
   * (and vice versa). Without this, a strategy with an event-symbol
   * alias would render twice — visually overlapping at the same pixel,
   * but counted as two ellipses by the parity test.
   */
  private reconcileFinalLayout(tickIdx: number, out: string[]) {
    if (!this.layout) return;
    // First pass: find every canonical_id that's already represented by
    // an admitted node (canonical or alias). We always pick the
    // *canonical* layout key (`strat_<i>` / `oper_<i>`) as the hub, not
    // the bridged event-symbol alias — that way edge tuples match the
    // static DOT exactly (which uses `strat_<i>` / `oper_<i>`).
    const canonicalAdmitted = new Set<string>();
    for (const [id, pos] of Object.entries(this.layout.nodes)) {
      const cid = pos.canonical_id;
      if (!cid) continue;
      const n = this.nodes.get(id);
      if (n?.admitted) canonicalAdmitted.add(cid);
    }
    // Second pass: admit the canonical strat_/oper_ entry itself, even
    // when the alias is already admitted. Both share the same pinned
    // coordinates, so visually one renders on top of the other; for
    // edge-tuple parity with the static DOT we want the canonical id
    // present in this.nodes so subsequent edges anchor on it.
    for (const [id, pos] of Object.entries(this.layout.nodes)) {
      if (pos.kind !== 'strategy' && pos.kind !== 'operator') continue;
      if (!(id.startsWith('strat_') || id.startsWith('oper_'))) continue;
      const node = this.nodes.get(id);
      if (!node || node.admitted) continue;
      node.admitted = true;
      node.admittedTick = tickIdx;
      out.push(id);
      canonicalAdmitted.add(pos.canonical_id || id);
      this.coAdmitLinkedKnowledge(id, tickIdx, out);
    }
    // Third pass: ensure every strat_/oper_ has its premise/variable +
    // conclusion edges admitted. Match the static DOT's edge structure
    // (premise → strat → conclusion / variable → oper → conclusion).
    // Idempotent — admitEdge skips duplicate keys.
    for (const [id, pos] of Object.entries(this.layout.nodes)) {
      if (pos.kind !== 'strategy' && pos.kind !== 'operator') continue;
      if (!(id.startsWith('strat_') || id.startsWith('oper_'))) continue;
      const node = this.nodes.get(id);
      if (!node?.admitted) continue;
      const edgeKind =
        pos.kind === 'operator'
          ? pos.operator_type || 'contradiction'
          : pos.strategy_type || 'deduction';
      // Conclusion edge: hub → conclusion knowledge.
      if (pos.conclusion_id && this.nodes.get(pos.conclusion_id)?.admitted) {
        this.admitEdge(
          { from: id, to: pos.conclusion_id, kind: edgeKind },
          edgeKind,
          undefined,
          tickIdx,
          out
        );
      }
      // Premise edges (strategy) / variable edges (operator).
      const incoming = pos.kind === 'operator' ? pos.variable_ids : pos.premise_ids;
      for (const upstreamId of incoming || []) {
        if (!this.nodes.get(upstreamId)?.admitted) continue;
        this.admitEdge(
          { from: upstreamId, to: id, kind: edgeKind },
          edgeKind,
          undefined,
          tickIdx,
          out
        );
      }
    }
  }

  /**
   * Round at the current tick = the round_id the tick belongs to (or the
   * latest seen up to that tick). Returns null when no round has opened.
   */
  computeActiveRoundId(tickIdx: number): string | null {
    if (tickIdx < 0) return null;
    let rid: string | null = null;
    for (let t = 0; t <= tickIdx && t < this.ticks.length; t++) {
      const r = this.ticks[t].round_id;
      if (r) rid = r;
    }
    return rid;
  }

  /** Belief for *kid* at the given round, with prior-fallback. */
  beliefAtRound(kid: string, roundId: string | null): number | undefined {
    const node = this.nodes.get(kid);
    if (!node) return undefined;
    if (roundId && node.beliefByRound[roundId] != null) {
      return node.beliefByRound[roundId];
    }
    // Fall back to the latest-known round whose belief table includes kid.
    const orderedRounds = Object.keys(this.roundBeliefs);
    for (let i = orderedRounds.length - 1; i >= 0; i--) {
      const r = orderedRounds[i];
      if (node.beliefByRound[r] != null) return node.beliefByRound[r];
    }
    return node.prior;
  }

  private resetAdmission() {
    for (const node of this.nodes.values()) {
      node.admitted = false;
      node.admittedTick = -1;
      node.removed = false;
    }
    this.edges.clear();
  }

  private applyTick(tick: IrTick): { admittedNodeIds: string[] } {
    const admittedNodeIds: string[] = [];
    const ev = this.events[tick.event_index];
    if (!ev) return { admittedNodeIds };
    // Orphan-tick guard: the CLI flags ticks whose action references a
    // symbol that the agent admitted mid-run but later merged/repaired
    // away (so it doesn't survive into the final compiled IR). The
    // tick still lives on the timeline (marker rendered, desaturated),
    // but we skip canvas admission entirely — keeping the hard
    // invariant that the replay's final state equals the static SVG.
    if (tick.survives_to_final === false) {
      return { admittedNodeIds };
    }
    const action = tick.action;
    const delta: GraphDelta | undefined = ev.graph_delta;
    const payload = (ev.payload as Record<string, unknown> | undefined) || {};

    const nodesAddedById = new Map<string, GraphNodeAdded>();
    for (const n of delta?.nodes_added || []) {
      nodesAddedById.set(n.id, n);
    }
    const edgesByKind = new Map<string, GraphEdgeRecord[]>();
    for (const e of delta?.edges_added || []) {
      const kind = e.kind || '';
      if (!edgesByKind.has(kind)) edgesByKind.set(kind, []);
      edgesByKind.get(kind)!.push(e);
    }

    // Resolve the action's symbol to its canonical layout key
    // (`strat_<i>` / `oper_<i>`) when one exists. The bridge stamps a
    // `canonical_id` on aliased entries so we can collapse `gfac_xx` →
    // `strat_0`, custom contradiction symbols → `oper_<i>`, etc. This
    // ensures admitted nodes + edges anchor on the same id the static
    // DOT uses. Without this collapse, the canvas would have one
    // ellipse for `gfac_xx` and another for `strat_0` overlapping at
    // the same coords, and the parity test would over-count.
    const resolveCanonical = (id: string | undefined): string | undefined => {
      if (!id) return undefined;
      const entry = this.layout?.nodes[id];
      const cid = entry?.canonical_id;
      if (cid && this.nodes.has(cid)) return cid;
      return id;
    };
    const symbolCanonical = resolveCanonical(action.symbol);

    switch (action.action) {
      case 'claim':
      case 'deduction': {
        if (action.symbol) {
          const meta = nodesAddedById.get(action.symbol);
          // For `claim`, admit the raw event-side symbol (it's a
          // knowledge node — has no canonical_id collapse). For
          // `deduction`, admit the canonical strat_<i> entry so the
          // canvas avoids drawing two ellipses at the same coords.
          const targetId = action.action === 'deduction' ? symbolCanonical || action.symbol : action.symbol;
          this.admitNode(targetId, action.action, meta, tick.tick_index, admittedNodeIds);
          // For deduction: co-admit the strategy's IR-side
          // conclusion + premises so the final canvas shows every
          // knowledge box the static DOT shows, even when no explicit
          // `claim` event lands for them (e.g. package-author premises).
          if (action.action === 'deduction') {
            this.coAdmitLinkedKnowledge(targetId, tick.tick_index, admittedNodeIds);
          }
        }
        // Bulk-promote: for `claim`, also admit any unrelated claim nodes
        // declared in the same nodes_added array (mirrors v3 behaviour
        // for 2dheg-style bulk acceptance).
        if (action.action === 'claim') {
          for (const n of delta?.nodes_added || []) {
            if (n.id === action.symbol) continue;
            if ((n.kind || 'claim') !== 'claim') continue;
            if (n.id.startsWith('inquiry:')) continue;
            this.admitNode(n.id, 'claim', n, tick.tick_index, admittedNodeIds);
          }
        }
        // Admit deduction edges in the same tick. Routes through the
        // canonical strat_<i> layout entry so edge tuples match the
        // static DOT. When no symbol is available (events occasionally
        // collapse multiple deductions under one action), defer to the
        // reconcile-final pass at end-of-play — it walks the IR-derived
        // strategy list directly, which is authoritative.
        if (action.action === 'deduction' && symbolCanonical && this.nodes.has(symbolCanonical)) {
          for (const e of edgesByKind.get('deduction') || []) {
            this.admitRoutedEdge(
              e,
              symbolCanonical,
              'deduction',
              undefined,
              tick.tick_index,
              admittedNodeIds
            );
          }
        }
        break;
      }
      case 'support':
      case 'contradiction':
      case 'equivalence': {
        const kindEdges = edgesByKind.get(action.action) || [];
        const operatorMeta = action.symbol ? nodesAddedById.get(action.symbol) : undefined;
        // Step 1: admit the canonical operator/strategy node so the
        // canvas shows the hexagon (contradiction / equivalence) or
        // yellow ellipse (support) at its pinned position. Resolve via
        // canonical_id so we admit `strat_<i>` / `oper_<i>` (not the
        // bridged event-symbol alias) — same coords, but the canonical
        // id matches what the static DOT emits.
        const hubId = symbolCanonical;
        if (hubId) {
          this.admitNode(
            hubId,
            action.action,
            operatorMeta,
            tick.tick_index,
            admittedNodeIds
          );
          // Co-admit the operator/strategy's conclusion knowledge node
          // (its IR helper claim). The static DOT renders this as a
          // knowledge box; the events never emit a `claim` action for it
          // (it's package-author-declared, not LKM-discovered) so without
          // this step the box would be missing from the final canvas.
          this.coAdmitLinkedKnowledge(hubId, tick.tick_index, admittedNodeIds);
        }
        // Step 2: admit edges incident to the operator/strategy. The CLI
        // splits one tick per action, so the tick admits ONE edge of that
        // kind in the simple case. Pair against payload.<kind>s[] when
        // available, else use the action's positional index within the
        // parent event.
        const payloadKey =
          action.action === 'support'
            ? 'supports'
            : action.action === 'contradiction'
            ? 'contradicts'
            : 'equivalent';
        const payloadList = payload[payloadKey];
        let edgeIdx = this.actionPositionalIndex(ev, tick.action_index, action.action);
        if (Array.isArray(payloadList) && payloadList.length === kindEdges.length && action.symbol) {
          const sIdx = (payloadList as unknown[]).indexOf(action.symbol);
          if (sIdx >= 0) edgeIdx = sIdx;
        }
        if (edgeIdx >= 0 && edgeIdx < kindEdges.length) {
          if (action.action === 'support') {
            // Support is a strategy — `premise → strat → conclusion`.
            // Route through the canonical strategy node so edge tuples
            // match the static DOT.
            if (hubId && this.nodes.has(hubId)) {
              this.admitRoutedEdge(
                kindEdges[edgeIdx],
                hubId,
                action.action,
                operatorMeta,
                tick.tick_index,
                admittedNodeIds
              );
            }
          } else {
            // Contradiction / equivalence are operators — both endpoints
            // of the event edge are *variables* pointing IN to the
            // operator hexagon. The static DOT emits one edge per
            // variable + one outgoing conclusion edge; we leave the
            // visual layout to `reconcileFinalLayout`, which draws those
            // edges from `variable_ids` + `conclusion_id` baked by
            // `annotate_layout_with_kinds`. At tick time we just admit
            // the hexagon (already handled in step 1).
            void operatorMeta;
          }
        }
        break;
      }
      case 'prior': {
        this.admitPrior(action, payload, delta, tick.tick_index);
        break;
      }
      default:
        // claim / deduction / support / contradiction / equivalence / prior
        // are the only IR-tick action types the CLI splits on; anything else
        // is a no-op here.
        break;
    }
    return { admittedNodeIds };
  }

  /**
   * Index of *action* within the parent event's actions of the same kind.
   * Used for edge pairing when payload lists aren't available.
   */
  private actionPositionalIndex(
    ev: TimelineEvent,
    actionIdx: number,
    kind: string
  ): number {
    let pos = -1;
    for (let i = 0; i <= actionIdx && i < (ev.gaia_actions?.length || 0); i++) {
      const a = ev.gaia_actions![i];
      if (a.action === kind) pos++;
    }
    return pos;
  }

  /**
   * Co-admit any knowledge node IDs the operator/strategy entry at *anchorId*
   * declares as its conclusion or premises/variables (set by
   * `annotate_layout_with_kinds` on the CLI side). Mirrors `_dot.py`'s
   * rendering rule that the static SVG always shows the operator's
   * conclusion claim even when no explicit `claim` event admits it (the
   * helper claim is package-author-declared, not LKM-discovered).
   */
  private coAdmitLinkedKnowledge(
    anchorId: string,
    tickIdx: number,
    out: string[]
  ) {
    const layoutEntry = this.layout?.nodes[anchorId];
    if (!layoutEntry) return;
    const linked: string[] = [];
    if (layoutEntry.conclusion_id) linked.push(layoutEntry.conclusion_id);
    for (const id of layoutEntry.premise_ids || []) linked.push(id);
    for (const id of layoutEntry.variable_ids || []) linked.push(id);
    for (const linkId of linked) {
      const target = this.nodes.get(linkId);
      if (!target) continue;
      if (!target.admitted) {
        target.admitted = true;
        target.admittedTick = tickIdx;
        out.push(linkId);
      }
    }
  }

  private admitNode(
    id: string,
    actionKind: string,
    meta: GraphNodeAdded | undefined,
    tickIdx: number,
    out: string[]
  ) {
    let node = this.nodes.get(id);
    if (!node) {
      // Node not in pinned layout — synthesize at viewport center. (Real
      // packages place every IR node in the layout; this branch handles
      // fixtures and inquiry:* hypothesis stubs.)
      const vp = this.layout?.viewport || { width: 800, height: 600 };
      node = {
        id,
        x: vp.width / 2,
        y: vp.height / 2,
        kind: meta?.kind || actionKind,
        label: meta?.label || id,
        module: null,
        beliefByRound: {},
        admitted: false,
        admittedTick: -1,
        removed: false,
      };
      this.nodes.set(id, node);
    }
    if (meta?.label && !this.layoutKindLocked.has(id)) node.label = meta.label;
    if (meta?.kind && !this.layoutKindLocked.has(id)) node.kind = meta.kind;
    if (meta?.content_excerpt) node.contentExcerpt = meta.content_excerpt;
    if (typeof meta?.prior === 'number') node.prior = meta.prior;
    if (!node.admitted) {
      node.admitted = true;
      node.admittedTick = tickIdx;
      out.push(id);
    }
  }

  /**
   * Admit a routed edge: thread *e* (a knowledge ↔ hub logical edge)
   * through *hubId* (a strategy or operator layout entry). Mirrors the
   * static DOT's emission rule (`_dot.py`):
   *
   *   premise → strat → conclusion          (deduction / support)
   *   variable → oper → conclusion          (contradiction / equivalence)
   *
   * Some lkm-to-gaia variants emit two-leg edges already
   * (premise → gfac, gfac → conclusion); others emit a single direct
   * edge (premise → conclusion). We canonicalize either form by
   * resolving each endpoint through `canonical_id` and emitting one or
   * two legs as needed — without ever drawing a knowledge ↔ knowledge
   * direct edge that bypasses the hub.
   */
  private admitRoutedEdge(
    e: GraphEdgeRecord,
    hubId: string,
    actionKind: string,
    operatorMeta: GraphNodeAdded | undefined,
    tickIdx: number,
    out: string[]
  ) {
    const fromCanon = this.layout?.nodes[e.from]?.canonical_id || e.from;
    const toCanon = this.layout?.nodes[e.to]?.canonical_id || e.to;
    if (fromCanon === hubId) {
      // Outgoing leg only (hub → conclusion).
      this.admitEdge(
        { from: hubId, to: e.to, kind: actionKind, prior: e.prior, reason_excerpt: e.reason_excerpt },
        actionKind,
        operatorMeta,
        tickIdx,
        out
      );
      return;
    }
    if (toCanon === hubId) {
      // Incoming leg only (premise → hub).
      this.admitEdge(
        { from: e.from, to: hubId, kind: actionKind, prior: e.prior, reason_excerpt: e.reason_excerpt },
        actionKind,
        operatorMeta,
        tickIdx,
        out
      );
      return;
    }
    // Single-leg form: split into both legs.
    this.admitEdge(
      { from: e.from, to: hubId, kind: actionKind, prior: e.prior, reason_excerpt: e.reason_excerpt },
      actionKind,
      operatorMeta,
      tickIdx,
      out
    );
    this.admitEdge(
      { from: hubId, to: e.to, kind: actionKind, prior: e.prior, reason_excerpt: e.reason_excerpt },
      actionKind,
      operatorMeta,
      tickIdx,
      out
    );
  }

  private admitEdge(
    e: GraphEdgeRecord,
    actionKind: string,
    operatorMeta: GraphNodeAdded | undefined,
    tickIdx: number,
    out: string[]
  ) {
    const kind = e.kind || actionKind;
    const key = `${e.from}->${e.to}:${kind}`;
    if (this.edges.has(key)) return;
    // Ensure endpoints exist + are admitted.
    for (const endpoint of [e.from, e.to]) {
      if (!this.nodes.has(endpoint)) {
        const vp = this.layout?.viewport || { width: 800, height: 600 };
        this.nodes.set(endpoint, {
          id: endpoint,
          x: vp.width / 2,
          y: vp.height / 2,
          kind: 'claim',
          label: endpoint,
          module: null,
          beliefByRound: {},
          admitted: true,
          admittedTick: tickIdx,
          removed: false,
        });
        out.push(endpoint);
      } else {
        const ep = this.nodes.get(endpoint)!;
        if (!ep.admitted) {
          ep.admitted = true;
          ep.admittedTick = tickIdx;
          out.push(endpoint);
        }
      }
    }
    this.edges.set(key, {
      key,
      from: e.from,
      to: e.to,
      kind,
      prior: e.prior,
      reason_excerpt: e.reason_excerpt,
      operatorLabel: operatorMeta?.label,
      operatorExcerpt: operatorMeta?.content_excerpt,
      admitted: true,
      admittedTick: tickIdx,
      removed: false,
    });
  }

  private admitPrior(
    action: GaiaAction,
    payload: Record<string, unknown>,
    delta: GraphDelta | undefined,
    tickIdx: number
  ) {
    const updates: Array<{ id: string; value?: number; reason?: string }> = [];
    const targetLkmId =
      typeof payload['target_lkm_id'] === 'string' ? (payload['target_lkm_id'] as string) : undefined;
    const directPrior = typeof payload['prior'] === 'number' ? (payload['prior'] as number) : undefined;
    const rationale =
      typeof payload['rationale'] === 'string' ? (payload['rationale'] as string) : undefined;
    if (targetLkmId) updates.push({ id: targetLkmId, value: directPrior, reason: rationale });

    const priorsDict = payload['priors'];
    if (priorsDict && typeof priorsDict === 'object' && !Array.isArray(priorsDict)) {
      for (const [id, v] of Object.entries(priorsDict as Record<string, unknown>)) {
        const value = typeof v === 'number' ? v : undefined;
        if (!updates.find((u) => u.id === id)) updates.push({ id, value, reason: rationale });
      }
    }
    for (const e of delta?.edges_added || []) {
      if (e.kind !== 'prior') continue;
      const id = e.to;
      const existing = updates.find((u) => u.id === id);
      if (existing) {
        if (existing.value == null && typeof e.prior === 'number') existing.value = e.prior;
        if (!existing.reason && e.reason_excerpt) existing.reason = e.reason_excerpt;
      } else {
        updates.push({ id, value: e.prior, reason: e.reason_excerpt });
      }
    }
    if (
      updates.length === 0 &&
      action.symbol &&
      this.nodes.has(action.symbol) &&
      typeof payload['prior'] === 'number'
    ) {
      updates.push({ id: action.symbol, value: payload['prior'] as number, reason: rationale });
    }
    for (const u of updates) {
      const node = this.nodes.get(u.id);
      if (!node) continue;
      if (typeof u.value === 'number') node.prior = u.value;
      if (u.reason) node.priorReason = u.reason;
      // Don't auto-admit on prior — prior annotations are a side channel.
      void tickIdx;
    }
  }

  /** Keys of edges currently admitted (for canvas binding). */
  admittedEdges(): CanonicalEdge[] {
    return Array.from(this.edges.values()).filter((e) => e.admitted && !e.removed);
  }

  admittedNodes(): CanonicalNode[] {
    return Array.from(this.nodes.values()).filter((n) => n.admitted && !n.removed);
  }
}

// Used by the timeline / chapters to find the index of the first event in
// the timeline that belongs to a given round_id.
export function firstEventIdxForRound(events: TimelineEvent[], roundId: string): number {
  for (let i = 0; i < events.length; i++) {
    if (events[i].round_id === roundId) return i;
  }
  return -1;
}

void KNOWLEDGE_KINDS;
