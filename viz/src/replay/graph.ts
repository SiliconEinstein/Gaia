// Pinned canonical-layout canvas — v4.
//
// Renders nodes at the coordinates baked by `gaia starmap-replay` (which
// piped the final IR's DOT through `dot -Tjson0`). No d3-force, no drag —
// canvas-pan / wheel-zoom only.
//
// Three SVG layers, top → bottom:
//   • overlay   — transient effects: entrance halos, LKM-overlay cards
//   • nodes     — pinned node bodies + labels + belief annotations
//   • links     — straight edges between pinned endpoints
//   • clusters  — rounded paper-cluster boxes (drawn first, behind everything)

import { select, type Selection } from 'd3-selection';
import { zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior } from 'd3-zoom';

import { CanonicalStore } from './store';
import {
  EDGE_COLOUR,
  NODE_STYLE,
  PALETTE,
  type CanonicalEdge,
  type CanonicalNode,
  type IrTick,
  type TimelineEvent,
} from './types';

const HALO_DURATION = 800;
const LKM_OVERLAY_DURATION = 600;
const BELIEF_TWEEN_DURATION = 400;
const CLUSTER_FADE_DURATION = 600;

interface NodeEnterAnimation {
  id: string;
  startedAt: number;
}

interface LkmOverlay {
  // Anchor node id (existing in `store.nodes`) — used as the React-key
  // for the d3 join. When the tick's symbol is orphaned (the agent
  // admitted it mid-run but the final IR lacks it), this falls back to
  // a same-event surviving-node id, else a synthetic key.
  nodeId: string;
  // Pre-resolved canvas coordinates — captured at staging time so the
  // overlay doesn't snap to (-9999,-9999) when the symbol doesn't
  // exist in the canonical store.
  x: number;
  y: number;
  retrievals: TimelineEvent[];
  startedAt: number;
}

export class GraphCanvas {
  private host: HTMLElement;
  private store: CanonicalStore;
  private retrievalById: Map<string, TimelineEvent>;

  private svg!: Selection<SVGSVGElement, unknown, null, undefined>;
  private viewport!: Selection<SVGGElement, unknown, null, undefined>;
  private clusterLayer!: Selection<SVGGElement, unknown, null, undefined>;
  private linkLayer!: Selection<SVGGElement, unknown, null, undefined>;
  private nodeLayer!: Selection<SVGGElement, unknown, null, undefined>;
  private overlayLayer!: Selection<SVGGElement, unknown, null, undefined>;
  private zoomBehaviour!: ZoomBehavior<SVGSVGElement, unknown>;
  private tooltip!: HTMLElement;

  private enterAnims = new Map<string, NodeEnterAnimation>();
  private lkmOverlays: LkmOverlay[] = [];
  private animTimer: number | null = null;

  // Belief animation state — `lastRound` is the round whose belief is
  // currently being shown (or animated *to*). `tweens` map per-node from a
  // start-belief to a target-belief over BELIEF_TWEEN_DURATION ms.
  private currentRoundId: string | null = null;
  private tweens = new Map<string, { from: number; to: number; startedAt: number }>();

  // Cluster boxes only materialize after every node has been placed: we
  // consider playback "at the end" when cursorTick === totalTicks - 1.
  // `clustersVisible` tracks the *current* on/off state; `clusterFade`
  // animates between them across CLUSTER_FADE_DURATION ms.
  private clustersVisible = false;
  private clusterFade: { from: number; to: number; startedAt: number } | null = null;

  private onSelect: (id: string) => void = () => {};

  constructor(host: HTMLElement, store: CanonicalStore, events: TimelineEvent[]) {
    this.host = host;
    this.store = store;
    this.retrievalById = new Map();
    for (const ev of events) {
      if (ev.event_kind === 'retrieval') this.retrievalById.set(ev.event_id, ev);
    }
    this.mount();
    this.drawClusters();
  }

  setSelectHandler(fn: (id: string) => void) {
    this.onSelect = fn;
  }

  private mount() {
    const layout = this.store.layout;
    const vw = layout?.viewport.width || 800;
    const vh = layout?.viewport.height || 600;

    const existing = this.host.querySelector('svg#graph-canvas') as SVGSVGElement | null;
    if (existing) {
      this.svg = select(existing);
      this.svg
        .attr('class', 'graph-canvas')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${vw} ${vh}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');
    } else {
      this.svg = select(this.host)
        .append('svg')
        .attr('class', 'graph-canvas')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('viewBox', `0 0 ${vw} ${vh}`)
        .attr('preserveAspectRatio', 'xMidYMid meet');
      (this.svg.node() as SVGSVGElement).id = 'graph-canvas';
    }

    const defs = this.svg.append('defs');
    for (const [kind, colour] of Object.entries(EDGE_COLOUR)) {
      defs
        .append('marker')
        .attr('id', `arrow-${kind}`)
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 14)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', colour);
    }
    defs
      .append('marker')
      .attr('id', 'arrow-default')
      .attr('viewBox', '0 -5 10 10')
      .attr('refX', 14)
      .attr('refY', 0)
      .attr('markerWidth', 6)
      .attr('markerHeight', 6)
      .attr('orient', 'auto')
      .append('path')
      .attr('d', 'M0,-5L10,0L0,5')
      .attr('fill', '#888');

    this.viewport = this.svg.append('g').attr('class', 'viewport');
    this.clusterLayer = this.viewport.append('g').attr('class', 'clusters');
    this.linkLayer = this.viewport.append('g').attr('class', 'links');
    this.nodeLayer = this.viewport.append('g').attr('class', 'nodes');
    this.overlayLayer = this.viewport.append('g').attr('class', 'overlay-fx');

    this.zoomBehaviour = zoom<SVGSVGElement, unknown>()
      .scaleExtent([0.2, 6])
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        this.viewport.attr('transform', event.transform.toString());
      });
    this.svg.call(this.zoomBehaviour);
    this.svg.on('dblclick.zoom', null);
    this.svg.on('dblclick', () => {
      this.svg.call(this.zoomBehaviour.transform, zoomIdentity);
    });

    this.tooltip = document.createElement('div');
    this.tooltip.className = 'graph-tip';
    this.tooltip.style.position = 'absolute';
    this.tooltip.style.pointerEvents = 'none';
    this.tooltip.style.opacity = '0';
    this.tooltip.style.background = PALETTE.bgPanel;
    this.tooltip.style.border = `1px solid ${PALETTE.grid}`;
    this.tooltip.style.color = PALETTE.fg;
    this.tooltip.style.padding = '6px 9px';
    this.tooltip.style.borderRadius = '3px';
    this.tooltip.style.font = '11px ui-sans-serif, system-ui';
    this.tooltip.style.maxWidth = '280px';
    this.tooltip.style.zIndex = '6';
    if (getComputedStyle(this.host).position === 'static') {
      this.host.style.position = 'relative';
    }
    this.host.appendChild(this.tooltip);
  }

  /**
   * Render cluster boxes once at startup at opacity 0. Their geometry is
   * static (the pinned layout doesn't change), but their visibility is
   * driven by `updateClusterVisibility`: cluster rectangles fade in only
   * once playback reaches the final tick, and fade back out on reverse
   * scrub.
   */
  private drawClusters() {
    const layout = this.store.layout;
    if (!layout) return;
    const sel = this.clusterLayer
      .selectAll<SVGGElement, (typeof layout.clusters)[number]>('g.cluster-box')
      .data(layout.clusters, (d) => d.name);
    sel.exit().remove();
    const enter = sel
      .enter()
      .append('g')
      .attr('class', 'cluster-box')
      // Start hidden — `updateClusterVisibility` flips opacity once playback
      // reaches the final tick.
      .attr('opacity', 0);
    enter
      .append('rect')
      .attr('class', 'cluster-bg')
      .attr('rx', 6)
      .attr('ry', 6);
    enter
      .append('text')
      .attr('class', 'cluster-label')
      .attr('font-size', 11)
      .attr('font-family', 'system-ui, sans-serif');
    const merge = enter.merge(sel);
    merge
      .select<SVGRectElement>('rect.cluster-bg')
      .attr('x', (d) => d.x)
      .attr('y', (d) => d.y)
      .attr('width', (d) => d.w)
      .attr('height', (d) => d.h)
      .attr('fill', '#fafafa')
      .attr('stroke', '#999999')
      .attr('stroke-width', 1.2);
    merge
      .select<SVGTextElement>('text.cluster-label')
      .attr('x', (d) => d.x + 8)
      .attr('y', (d) => d.y + 14)
      .attr('fill', '#444')
      .text((d) => d.label);
  }

  reset() {
    this.enterAnims.clear();
    this.lkmOverlays = [];
    this.tweens.clear();
    this.nodeLayer.selectAll('*').remove();
    this.linkLayer.selectAll('*').remove();
    this.overlayLayer.selectAll('*').remove();
    // Hide cluster boxes again — they only re-appear when playback reaches
    // the final tick.
    this.clustersVisible = false;
    this.clusterFade = null;
    this.clusterLayer.selectAll<SVGGElement, unknown>('g.cluster-box').attr('opacity', 0);
    this.stopAnimLoop();
  }

  /**
   * Apply the result of `store.advanceTo(...)` to the canvas. Newly admitted
   * nodes get an entrance halo; LKM-driven ticks also stage a transient
   * overlay near the affected node.
   */
  applyTick(result: {
    admittedNodeIds: string[];
    lkmTicks: IrTick[];
    activeRoundId: string | null;
    cursorTick?: number;
    totalTicks?: number;
  }) {
    const now = performance.now();
    for (const id of result.admittedNodeIds) {
      this.enterAnims.set(id, { id, startedAt: now });
    }
    // Stage one LKM overlay per LKM-driven tick. The overlay anchors at
    // the primary symbol when it exists in the canonical store; for
    // orphan ticks (`survives_to_final === false`) the symbol points at
    // a node the final IR lacks, so we fall back — first to the parent
    // event's most recent surviving admitted node, then to viewport
    // top-center. This honours the user contract: the user sees that
    // "the agent attempted X here", but no halo pins to a non-existent
    // node and the canonical canvas stays unchanged.
    for (const tick of result.lkmTicks) {
      const retrievals = tick.retrieval_event_ids
        .map((rid) => this.retrievalById.get(rid))
        .filter((x): x is TimelineEvent => !!x);
      const anchor = this.resolveLkmAnchor(tick, result.admittedNodeIds);
      this.lkmOverlays.push({
        nodeId: anchor.nodeId,
        x: anchor.x,
        y: anchor.y,
        retrievals,
        startedAt: now,
      });
    }
    // Belief animation: when the active round changes, kick a belief tween
    // for every claim node whose belief differs between rounds.
    if (result.activeRoundId !== this.currentRoundId) {
      this.startBeliefTransition(this.currentRoundId, result.activeRoundId, now);
      this.currentRoundId = result.activeRoundId;
    }
    // Cluster reveal: only show paper-cluster boxes once playback reaches
    // the final tick. On reverse-scrub away from the end, fade them out.
    this.updateClusterVisibility(result.cursorTick, result.totalTicks, now);
    this.bindDom();
    this.startAnimLoop();
  }

  private updateClusterVisibility(
    cursorTick: number | undefined,
    totalTicks: number | undefined,
    now: number
  ) {
    if (cursorTick == null || totalTicks == null) return;
    const atEnd = totalTicks > 0 && cursorTick >= totalTicks - 1;
    if (atEnd === this.clustersVisible) return;
    // Determine current opacity (in case a fade is mid-flight).
    let current: number;
    if (this.clusterFade) {
      const u = Math.min(1, (now - this.clusterFade.startedAt) / CLUSTER_FADE_DURATION);
      current = this.clusterFade.from + (this.clusterFade.to - this.clusterFade.from) * u;
    } else {
      current = this.clustersVisible ? 1 : 0;
    }
    this.clustersVisible = atEnd;
    this.clusterFade = {
      from: current,
      to: atEnd ? 1 : 0,
      startedAt: now,
    };
  }

  private startBeliefTransition(from: string | null, to: string | null, now: number) {
    void from;
    for (const node of this.store.nodes.values()) {
      if (node.kind === 'strategy' || node.kind === 'operator') continue;
      const target = this.store.beliefAtRound(node.id, to);
      if (typeof target !== 'number') {
        this.tweens.delete(node.id);
        continue;
      }
      // Determine the current displayed value: an in-flight tween's
      // current interpolated value, else the previously displayed value.
      const existing = this.tweens.get(node.id);
      let current: number;
      if (existing) {
        const t = Math.min(1, (now - existing.startedAt) / BELIEF_TWEEN_DURATION);
        current = existing.from + (existing.to - existing.from) * t;
      } else {
        current = node.prior ?? target;
      }
      if (Math.abs(current - target) < 1e-6) {
        this.tweens.delete(node.id);
        continue;
      }
      this.tweens.set(node.id, { from: current, to: target, startedAt: now });
    }
  }

  private bindDom() {
    const admittedNodes = this.store.admittedNodes();
    const admittedEdges = this.store.admittedEdges().filter((e) => {
      const a = this.store.nodes.get(e.from);
      const b = this.store.nodes.get(e.to);
      return a?.admitted && b?.admitted;
    });

    // ── Edges ──
    const linkSel = this.linkLayer
      .selectAll<SVGLineElement, CanonicalEdge>('line.link')
      .data(admittedEdges, (d) => d.key);
    linkSel.exit().remove();
    const linkEnter = linkSel
      .enter()
      .append('line')
      .attr('class', 'link')
      .attr('stroke-width', 1.4)
      .attr('marker-end', (d) =>
        EDGE_COLOUR[d.kind] ? `url(#arrow-${d.kind})` : 'url(#arrow-default)'
      );
    const linkMerge = linkEnter.merge(linkSel);
    linkMerge
      .attr('x1', (d) => this.store.nodes.get(d.from)!.x)
      .attr('y1', (d) => this.store.nodes.get(d.from)!.y)
      .attr('x2', (d) => this.store.nodes.get(d.to)!.x)
      .attr('y2', (d) => this.store.nodes.get(d.to)!.y)
      .attr('stroke', (d) => EDGE_COLOUR[d.kind] || '#888')
      .attr('stroke-dasharray', (d) => (d.kind === 'inquiry' ? '4 3' : null))
      .attr('opacity', 0.85);

    // ── Nodes ──
    const nodeSel = this.nodeLayer
      .selectAll<SVGGElement, CanonicalNode>('g.node')
      .data(admittedNodes, (d) => d.id);
    nodeSel.exit().remove();
    const nodeEnter = nodeSel
      .enter()
      .append('g')
      .attr('class', 'node')
      .style('cursor', 'pointer')
      .on('click', (_event, d) => this.onSelect(d.id))
      .on('mousemove', (event: MouseEvent, d) => this.showNodeTooltip(d, event))
      .on('mouseleave', () => this.hideTooltip());

    // Halo (entrance pulse).
    nodeEnter
      .append('circle')
      .attr('class', 'node-halo')
      .attr('r', 0)
      .attr('fill', 'none')
      .attr('stroke', PALETTE.accent)
      .attr('stroke-width', 2)
      .attr('opacity', 0);
    // Body — a single path element renders any shape (rect for
    // claims/derived/setting/exported, ellipse for strategies, hexagon
    // for operators). Mirrors the static DOT renderer's emission rules
    // (`_dot.py`: `_emit_strategy_node` ellipse, `_emit_operator_node`
    // hexagon).
    nodeEnter
      .append('path')
      .attr('class', 'node-shape')
      .attr('stroke-width', 1.2);
    nodeEnter
      .append('text')
      .attr('class', 'node-label')
      .attr('text-anchor', 'middle')
      .attr('font-size', 9.5)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('paint-order', 'stroke')
      .attr('stroke', '#ffffff')
      .attr('stroke-width', 2)
      .attr('fill', '#222');

    const nodeMerge = nodeEnter.merge(nodeSel);
    nodeMerge.attr('transform', (d) => `translate(${d.x},${d.y})`);
    nodeMerge.each((d, i, group) => {
      const g = select(group[i] as SVGGElement);
      const style = NODE_STYLE[d.kind] || NODE_STYLE.claim;
      const text = this.formatNodeLabel(d);
      const shape = shapeForKind(d.kind);
      // Width depends on shape: knowledge boxes scale with label length,
      // strategy ellipses and operator hexagons are kept compact (the
      // static DOT renderer also uses small ellipses/hexagons regardless
      // of label length).
      const w =
        shape === 'rect'
          ? Math.max(60, Math.min(150, text.length * 5.2 + 16))
          : shape === 'ellipse'
          ? Math.max(70, text.length * 5 + 14)
          : 70; // hexagon
      const h = 28;
      g.select<SVGPathElement>('path.node-shape')
        .attr('d', shapePath(shape, w, h))
        .attr('fill', style.fill)
        .attr('stroke', style.stroke);
      const lbl = g.select<SVGTextElement>('text.node-label');
      lbl.selectAll('tspan').remove();
      const lines = text.split('\n');
      lines.forEach((line, idx) => {
        lbl
          .append('tspan')
          .attr('x', 0)
          .attr('dy', idx === 0 ? -4 + (lines.length - 1) * -5 : 11)
          .text(line);
      });
    });
  }

  private formatNodeLabel(node: CanonicalNode): string {
    const raw = node.label || node.id;
    const truncated = raw.length > 22 ? raw.slice(0, 21) + '…' : raw;
    const prior = node.prior;
    const beliefRaw = this.tweens.get(node.id)?.to ?? this.store.beliefAtRound(node.id, this.currentRoundId);
    if (prior == null && beliefRaw == null) return truncated;
    const beliefShown = this.currentBeliefDisplay(node);
    if (prior != null && beliefShown != null) {
      return `${truncated}\n(${prior.toFixed(2)} → ${beliefShown.toFixed(2)})`;
    }
    if (beliefShown != null) return `${truncated}\n(${beliefShown.toFixed(2)})`;
    if (prior != null) return `${truncated}\n(${prior.toFixed(2)})`;
    return truncated;
  }

  private currentBeliefDisplay(node: CanonicalNode): number | undefined {
    const t = this.tweens.get(node.id);
    if (t) {
      const elapsed = performance.now() - t.startedAt;
      const u = Math.min(1, elapsed / BELIEF_TWEEN_DURATION);
      return t.from + (t.to - t.from) * u;
    }
    return this.store.beliefAtRound(node.id, this.currentRoundId);
  }

  // ── Animation loop ──

  private startAnimLoop() {
    if (this.animTimer != null) return;
    const step = () => {
      const now = performance.now();
      const stillEnter: NodeEnterAnimation[] = [];
      for (const anim of this.enterAnims.values()) {
        const t = (now - anim.startedAt) / HALO_DURATION;
        if (t >= 1) continue;
        stillEnter.push(anim);
        const halo = this.nodeLayer
          .selectAll<SVGGElement, CanonicalNode>('g.node')
          .filter((d) => d.id === anim.id)
          .select<SVGCircleElement>('circle.node-halo');
        halo.attr('r', 14 + t * 26).attr('opacity', 1 - t);
      }
      // Cleanup finished entrance halos.
      for (const id of Array.from(this.enterAnims.keys())) {
        if (!stillEnter.find((a) => a.id === id)) {
          this.enterAnims.delete(id);
          this.nodeLayer
            .selectAll<SVGGElement, CanonicalNode>('g.node')
            .filter((d) => d.id === id)
            .select<SVGCircleElement>('circle.node-halo')
            .attr('opacity', 0);
        }
      }

      // LKM overlays — render an outer halo + small text "LKM ×N" near the node.
      const remainingOverlays: LkmOverlay[] = [];
      for (const ov of this.lkmOverlays) {
        const u = (now - ov.startedAt) / LKM_OVERLAY_DURATION;
        if (u >= 1) continue;
        remainingOverlays.push(ov);
      }
      this.lkmOverlays = remainingOverlays;
      this.renderLkmOverlays(now);

      // Belief tweens — rebind labels for any node mid-tween, then drop
      // tweens that have finished.
      if (this.tweens.size > 0) {
        const finished: string[] = [];
        for (const [id, t] of this.tweens.entries()) {
          if ((now - t.startedAt) / BELIEF_TWEEN_DURATION >= 1) finished.push(id);
        }
        for (const id of finished) this.tweens.delete(id);
        // Re-render label text for in-flight tweens.
        this.nodeLayer
          .selectAll<SVGGElement, CanonicalNode>('g.node')
          .each((d, i, group) => {
            if (!this.tweens.has(d.id)) return;
            const g = select(group[i] as SVGGElement);
            const lbl = g.select<SVGTextElement>('text.node-label');
            lbl.selectAll('tspan').remove();
            const text = this.formatNodeLabel(d);
            const lines = text.split('\n');
            lines.forEach((line, idx) => {
              lbl
                .append('tspan')
                .attr('x', 0)
                .attr('dy', idx === 0 ? -4 + (lines.length - 1) * -5 : 11)
                .text(line);
            });
          });
      }

      // Cluster fade — interpolate opacity across the active fade window.
      if (this.clusterFade) {
        const u = (now - this.clusterFade.startedAt) / CLUSTER_FADE_DURATION;
        const opacity =
          u >= 1
            ? this.clusterFade.to
            : this.clusterFade.from +
              (this.clusterFade.to - this.clusterFade.from) * u;
        this.clusterLayer
          .selectAll<SVGGElement, unknown>('g.cluster-box')
          .attr('opacity', opacity);
        if (u >= 1) this.clusterFade = null;
      }

      if (
        this.enterAnims.size === 0 &&
        this.lkmOverlays.length === 0 &&
        this.tweens.size === 0 &&
        this.clusterFade == null
      ) {
        this.stopAnimLoop();
        return;
      }
      this.animTimer = window.requestAnimationFrame(step);
    };
    this.animTimer = window.requestAnimationFrame(step);
  }

  private stopAnimLoop() {
    if (this.animTimer != null) {
      window.cancelAnimationFrame(this.animTimer);
      this.animTimer = null;
    }
  }

  /**
   * Pick the canvas anchor for an LKM overlay tick. Returns
   * `{nodeId, x, y}` so the caller can stage the overlay even when the
   * tick's symbol never makes it into the canonical store (orphan
   * tick: `survives_to_final === false`).
   *
   * Priority:
   *   1. The tick's own `action.symbol`, if it's an admitted node in
   *      the store. (Surviving ticks always hit this branch.)
   *   2. The most recent admitted node from the same parent event —
   *      lets the user see "agent attempted X here" near the action's
   *      conceptual neighbourhood.
   *   3. Any newly admitted node from this advance step.
   *   4. Viewport top-center as a last resort, with a synthetic
   *      `nodeId` keyed to the tick so d3's join doesn't dedupe.
   */
  private resolveLkmAnchor(
    tick: IrTick,
    admittedThisStep: string[]
  ): { nodeId: string; x: number; y: number } {
    const sym = tick.action.symbol;
    if (sym) {
      const symNode = this.store.nodes.get(sym);
      if (symNode?.admitted) return { nodeId: sym, x: symNode.x, y: symNode.y };
    }
    // Same-event surviving anchor: walk this tick's parent event for
    // any other gaia_action whose symbol is now an admitted node.
    const ev = this.store.events[tick.event_index];
    if (ev?.gaia_actions) {
      for (const a of ev.gaia_actions) {
        const s = a.symbol;
        if (!s) continue;
        const n = this.store.nodes.get(s);
        if (n?.admitted) return { nodeId: s, x: n.x, y: n.y };
      }
    }
    // Anything admitted on this advance step.
    for (const id of admittedThisStep) {
      const n = this.store.nodes.get(id);
      if (n?.admitted) return { nodeId: id, x: n.x, y: n.y };
    }
    // Viewport top-center fallback. Use a synthetic node id keyed to
    // the tick index so multiple orphan overlays don't collide on the
    // same d3 data key.
    const vp = this.store.layout?.viewport || { width: 800, height: 600 };
    return {
      nodeId: `__lkm_orphan_${tick.tick_index}`,
      x: vp.width / 2,
      y: 30,
    };
  }

  private renderLkmOverlays(now: number) {
    const sel = this.overlayLayer
      .selectAll<SVGGElement, LkmOverlay>('g.lkm-overlay')
      .data(this.lkmOverlays, (d) => `${d.nodeId}:${d.startedAt}`);
    sel.exit().remove();
    const enter = sel.enter().append('g').attr('class', 'lkm-overlay');
    enter
      .append('circle')
      .attr('class', 'lkm-halo')
      .attr('fill', 'none')
      .attr('stroke', PALETTE.retrieval)
      .attr('stroke-width', 2.5);
    enter
      .append('text')
      .attr('class', 'lkm-label')
      .attr('font-size', 10)
      .attr('font-family', 'ui-monospace, monospace')
      .attr('text-anchor', 'middle')
      .attr('paint-order', 'stroke')
      .attr('stroke', PALETTE.bg)
      .attr('stroke-width', 2)
      .attr('fill', PALETTE.retrieval);
    const merge = enter.merge(sel);
    merge.attr('transform', (d) => {
      // Prefer the live store coordinates (handles late-arriving node
      // positions). Fall back to the pre-resolved coords captured at
      // staging time — used for orphan ticks whose symbol never lands
      // in the canonical store.
      const node = this.store.nodes.get(d.nodeId);
      if (node) return `translate(${node.x},${node.y})`;
      return `translate(${d.x},${d.y})`;
    });
    merge.select<SVGCircleElement>('circle.lkm-halo')
      .attr('r', (d) => {
        const u = (now - d.startedAt) / LKM_OVERLAY_DURATION;
        return 22 + u * 18;
      })
      .attr('opacity', (d) => {
        const u = (now - d.startedAt) / LKM_OVERLAY_DURATION;
        return Math.max(0, 0.85 * (1 - u));
      });
    merge.select<SVGTextElement>('text.lkm-label')
      .attr('y', -34)
      .attr('opacity', (d) => {
        const u = (now - d.startedAt) / LKM_OVERLAY_DURATION;
        return Math.max(0, 1 - u);
      })
      .text((d) => `LKM × ${d.retrievals.length}`);
  }

  resize() {
    // Pinned layout — viewBox already takes care of it. Nothing to recompute.
  }

  private showNodeTooltip(n: CanonicalNode, event: MouseEvent) {
    const lines: string[] = [`<b>${escapeHtml(n.label || n.id)}</b>`];
    if (n.kind && n.kind !== 'claim') lines.push(`<i>${escapeHtml(n.kind)}</i>`);
    const belief = this.store.beliefAtRound(n.id, this.currentRoundId);
    if (typeof n.prior === 'number') lines.push(`prior: ${n.prior.toFixed(3)}`);
    if (typeof belief === 'number') lines.push(`belief: ${belief.toFixed(3)}`);
    if (n.priorReason) lines.push(escapeHtml(truncate(n.priorReason, 200)));
    if (n.contentExcerpt) lines.push(escapeHtml(truncate(n.contentExcerpt, 200)));
    this.tooltip.innerHTML = lines.join('<br/>');
    this.positionTooltip(event);
  }

  private positionTooltip(event: MouseEvent) {
    const rect = this.host.getBoundingClientRect();
    this.tooltip.style.left = `${event.clientX - rect.left + 12}px`;
    this.tooltip.style.top = `${event.clientY - rect.top + 8}px`;
    this.tooltip.style.opacity = '1';
  }

  private hideTooltip() {
    this.tooltip.style.opacity = '0';
  }
}

function truncate(s: string, n: number): string {
  if (s.length <= n) return s;
  return s.slice(0, n - 1) + '…';
}

type NodeShape = 'rect' | 'ellipse' | 'hexagon';

/**
 * Map a logical node kind to its SVG shape.
 *
 * Mirrors `_dot.py`:
 *   • strategy → ellipse
 *   • operator / contradiction / equivalence → hexagon
 *   • everything else (claim / derived / exported / setting / deduction
 *     fallback) → rect
 */
function shapeForKind(kind: string): NodeShape {
  if (kind === 'strategy') return 'ellipse';
  if (kind === 'operator' || kind === 'contradiction' || kind === 'equivalence') {
    return 'hexagon';
  }
  return 'rect';
}

/**
 * Build an SVG ``d`` attribute for *shape* sized *w*×*h*, centered on the
 * origin. Rectangle uses rounded corners (rx=4) like the DOT-rendered
 * `shape=box` style. Ellipse is the natural ellipse path. Hexagon is a
 * regular hexagon with horizontal top/bottom edges, matching Graphviz's
 * default `shape=hexagon`.
 */
function shapePath(shape: NodeShape, w: number, h: number): string {
  const hw = w / 2;
  const hh = h / 2;
  if (shape === 'rect') {
    const r = 4;
    return (
      `M${-hw + r},${-hh}` +
      `H${hw - r}` +
      `Q${hw},${-hh} ${hw},${-hh + r}` +
      `V${hh - r}` +
      `Q${hw},${hh} ${hw - r},${hh}` +
      `H${-hw + r}` +
      `Q${-hw},${hh} ${-hw},${hh - r}` +
      `V${-hh + r}` +
      `Q${-hw},${-hh} ${-hw + r},${-hh}` +
      `Z`
    );
  }
  if (shape === 'ellipse') {
    // Use cubic-bezier-approximated ellipse (cleaner than two arcs at
    // small sizes; the visual result is identical to a true ellipse).
    return (
      `M${-hw},0` +
      `A${hw},${hh} 0 1,0 ${hw},0` +
      `A${hw},${hh} 0 1,0 ${-hw},0` +
      `Z`
    );
  }
  // hexagon: flat top/bottom edges, two slanted sides.
  const slope = hw * 0.35;
  return (
    `M${-hw + slope},${-hh}` +
    `L${hw - slope},${-hh}` +
    `L${hw},0` +
    `L${hw - slope},${hh}` +
    `L${-hw + slope},${hh}` +
    `L${-hw},0` +
    `Z`
  );
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
