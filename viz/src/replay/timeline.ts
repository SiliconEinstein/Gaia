// Timeline lanes — v3 (event-index axis).
//
// In v2 the x-axis was wall-clock; that was useless because real packages
// have events 50ms apart followed by minute-long quiet gaps. v3 switches to
// a discrete event-index axis: each event is one block, all blocks the same
// width within a lane. Ticks are labelled "#1, #20, #50, #100, …" — no more
// "+1.2s".

import { axisTop } from 'd3-axis';
import { scaleLinear, type ScaleLinear } from 'd3-scale';
import { select, type Selection } from 'd3-selection';
import { zoom, zoomIdentity, type D3ZoomEvent, type ZoomBehavior, type ZoomTransform } from 'd3-zoom';

import {
  GROWTH_FAMILY,
  PALETTE,
  RETRIEVAL_COLOURS,
  type IrTick,
  type TimelineEvent,
} from './types';

interface RoundBoundary {
  evIdx: number;
  kind: 'open' | 'close';
  roundId: string;
}

interface TickMarker {
  // Surviving-only index: position along the [0, N_survivors-1] axis that
  // determines the marker's x-coordinate. Orphan ticks are filtered out
  // before this struct is built.
  survIdx: number;
  evIdx: number;
  tickIdx: number;
  lkmDriven: boolean;
}

export class TimelineLanes {
  private host: HTMLElement;
  private events: TimelineEvent[];
  private ticks: IrTick[];
  private xScale!: ScaleLinear<number, number>; // base scale in event-index space
  private currentTransform: ZoomTransform = zoomIdentity;
  private zoomBehaviour!: ZoomBehavior<SVGSVGElement, unknown>;
  private svg!: Selection<SVGSVGElement, unknown, null, undefined>;
  private viewport!: Selection<SVGGElement, unknown, null, undefined>;
  private axisGroup!: Selection<SVGGElement, unknown, null, undefined>;
  private roundsGroup!: Selection<SVGGElement, unknown, null, undefined>;
  private tickMarkerGroup!: Selection<SVGGElement, unknown, null, undefined>;
  private retrievalLane!: Selection<SVGGElement, unknown, null, undefined>;
  private growthLane!: Selection<SVGGElement, unknown, null, undefined>;
  private playhead!: Selection<SVGLineElement, unknown, null, undefined>;
  private hoverhead!: Selection<SVGLineElement, unknown, null, undefined>;
  private hoverLabel!: Selection<SVGTextElement, unknown, null, undefined>;
  private tooltip!: HTMLElement;

  private onEventClick: (idx: number) => void = () => {};
  private onSeek: (idx: number) => void = () => {};
  // Tick-marker click — passes the *original* tick index so the player can
  // jump straight to that surviving tick (bypassing event-index lookup,
  // which is ambiguous when several ticks share an event_index).
  private onTickSeek: (tickIdx: number) => void = () => {};

  // Surviving ticks only, in original tick order. The i-th entry's marker
  // sits at fraction i/(N-1) of the lane width.
  private survivors: IrTick[] = [];
  // For tick T (0..ticks.length-1), survIdxByTick[T] is the surviving-index
  // the playhead should sit at while T is the active cursor. Orphan ticks
  // inherit the index of the most recent prior surviving tick, so the
  // playhead doesn't jump as the player burns through them.
  private survIdxByTick: number[] = [];
  // Last tick cursor passed to `setPlayheadTick`, retained so we can
  // re-place the playhead under zoom/pan or after a resize.
  private lastTickCursor = -1;

  // Layout constants.
  private readonly PAD_LEFT = 80;
  private readonly PAD_RIGHT = 24;
  private readonly AXIS_HEIGHT = 26;
  private readonly LANE_HEIGHT = 44;
  private readonly LANE_GAP = 6;

  constructor(host: HTMLElement, events: TimelineEvent[], ticks: IrTick[] = []) {
    this.host = host;
    this.events = events;
    this.ticks = ticks;
    this.recomputeSurvivors();
    this.mount();
    this.render();
  }

  setHandlers(opts: {
    onEventClick?: (idx: number) => void;
    onSeek?: (idx: number) => void;
    onTickSeek?: (tickIdx: number) => void;
  }) {
    if (opts.onEventClick) this.onEventClick = opts.onEventClick;
    if (opts.onSeek) this.onSeek = opts.onSeek;
    if (opts.onTickSeek) this.onTickSeek = opts.onTickSeek;
  }

  // Build `survivors` (surviving-only ticks) and `survIdxByTick`
  // (cursor-tick → surviving-index used for playhead placement).
  private recomputeSurvivors() {
    this.survivors = this.ticks.filter((t) => t.survives_to_final !== false);
    this.survIdxByTick = new Array(this.ticks.length);
    let lastSurv = -1;
    let nextSurvCursor = 0;
    for (let i = 0; i < this.ticks.length; i++) {
      const t = this.ticks[i];
      if (t.survives_to_final !== false) {
        // Find this tick's index in `survivors`. We march `nextSurvCursor`
        // forward in lockstep so this is O(N) overall.
        while (
          nextSurvCursor < this.survivors.length &&
          this.survivors[nextSurvCursor] !== t
        ) {
          nextSurvCursor++;
        }
        lastSurv = nextSurvCursor;
        nextSurvCursor++;
      }
      this.survIdxByTick[i] = lastSurv;
    }
  }

  private innerWidth(): number {
    return Math.max(40, this.host.clientWidth - this.PAD_LEFT - this.PAD_RIGHT);
  }

  private totalHeight(): number {
    return this.AXIS_HEIGHT + this.LANE_HEIGHT * 2 + this.LANE_GAP + 8;
  }

  // Domain extent in event-index space. We use [-0.5, N - 0.5] so the first
  // and last blocks have padding around them and aren't clipped.
  private domainMax(): number {
    return Math.max(1, this.events.length) - 0.5;
  }
  private domainMin(): number {
    return -0.5;
  }

  private mount() {
    // Preserve any static marker children (e.g. legacy id="lane-*-track"
    // spans the smoke tests grep for). Remove only existing svg/tooltip nodes.
    select(this.host).selectAll('svg.timeline-svg, .timeline-tip').remove();
    select(this.host).style('position', 'relative');

    this.svg = select(this.host)
      .append('svg')
      .attr('class', 'timeline-svg')
      .attr('width', '100%')
      .attr('height', this.totalHeight())
      .style('display', 'block');

    // Tooltip (DOM, not SVG).
    this.tooltip = document.createElement('div');
    this.tooltip.className = 'timeline-tip';
    this.tooltip.style.position = 'absolute';
    this.tooltip.style.pointerEvents = 'none';
    this.tooltip.style.opacity = '0';
    this.tooltip.style.background = PALETTE.bgPanel;
    this.tooltip.style.border = `1px solid ${PALETTE.grid}`;
    this.tooltip.style.color = PALETTE.fg;
    this.tooltip.style.padding = '5px 8px';
    this.tooltip.style.borderRadius = '3px';
    this.tooltip.style.font = '11px ui-sans-serif, system-ui';
    this.tooltip.style.maxWidth = '320px';
    this.tooltip.style.whiteSpace = 'nowrap';
    this.tooltip.style.zIndex = '5';
    this.tooltip.style.transition = 'opacity 0.1s';
    this.host.appendChild(this.tooltip);

    // Lane labels (left gutter).
    const labels = this.svg.append('g').attr('class', 'lane-labels');
    labels
      .append('text')
      .attr('x', 14)
      .attr('y', this.AXIS_HEIGHT + this.LANE_HEIGHT / 2 + 4)
      .attr('font-size', 11)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('fill', PALETTE.fgMute)
      .attr('text-transform', 'uppercase')
      .attr('letter-spacing', '0.08em')
      .text('retrievals');
    labels
      .append('text')
      .attr('x', 14)
      .attr('y', this.AXIS_HEIGHT + this.LANE_HEIGHT + this.LANE_GAP + this.LANE_HEIGHT / 2 + 4)
      .attr('font-size', 11)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('fill', PALETTE.fgMute)
      .attr('text-transform', 'uppercase')
      .attr('letter-spacing', '0.08em')
      .text('growth');

    this.viewport = this.svg.append('g').attr('class', 'viewport');
    // Background rect for the lane area, captures pan/zoom + click-to-seek.
    this.viewport
      .append('rect')
      .attr('class', 'lane-bg')
      .attr('x', this.PAD_LEFT)
      .attr('y', this.AXIS_HEIGHT)
      .attr('width', this.innerWidth())
      .attr('height', this.LANE_HEIGHT * 2 + this.LANE_GAP)
      .attr('fill', 'rgba(255,255,255,0.02)')
      .attr('stroke', PALETTE.grid);

    this.axisGroup = this.viewport
      .append('g')
      .attr('class', 'time-axis')
      .attr('transform', `translate(0, ${this.AXIS_HEIGHT})`);

    this.roundsGroup = this.viewport.append('g').attr('class', 'round-dividers');
    // IR-tick markers ride above the retrieval lane (between axis and lanes).
    this.tickMarkerGroup = this.viewport
      .append('g')
      .attr('class', 'tick-markers')
      .attr('transform', `translate(0, ${this.AXIS_HEIGHT - 4})`);

    this.retrievalLane = this.viewport
      .append('g')
      .attr('id', 'lane-retrieval-track')
      .attr('class', 'lane lane-retrieval')
      .attr('transform', `translate(0, ${this.AXIS_HEIGHT})`);

    this.growthLane = this.viewport
      .append('g')
      .attr('id', 'lane-growth-track')
      .attr('class', 'lane lane-growth')
      .attr(
        'transform',
        `translate(0, ${this.AXIS_HEIGHT + this.LANE_HEIGHT + this.LANE_GAP})`
      );

    this.hoverhead = this.viewport
      .append('line')
      .attr('class', 'hoverhead')
      .attr('y1', this.AXIS_HEIGHT)
      .attr('y2', this.AXIS_HEIGHT + this.LANE_HEIGHT * 2 + this.LANE_GAP)
      .attr('stroke', PALETTE.fgMute)
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', '3 3')
      .attr('opacity', 0)
      .attr('pointer-events', 'none');

    this.hoverLabel = this.viewport
      .append('text')
      .attr('class', 'hover-label')
      .attr('y', this.AXIS_HEIGHT - 8)
      .attr('font-size', 10)
      .attr('font-family', 'ui-monospace, monospace')
      .attr('fill', PALETTE.fgMute)
      .attr('text-anchor', 'middle')
      .attr('opacity', 0)
      .attr('pointer-events', 'none');

    this.playhead = this.viewport
      .append('line')
      .attr('class', 'playhead')
      .attr('y1', this.AXIS_HEIGHT)
      .attr('y2', this.AXIS_HEIGHT + this.LANE_HEIGHT * 2 + this.LANE_GAP)
      .attr('stroke', PALETTE.accent)
      .attr('stroke-width', 2)
      .attr('pointer-events', 'none');

    // Base scale: event-index → x in [PAD_LEFT, PAD_LEFT + innerWidth].
    this.xScale = scaleLinear()
      .domain([this.domainMin(), this.domainMax()])
      .range([this.PAD_LEFT, this.PAD_LEFT + this.innerWidth()]);

    // Zoom: scale x along the index axis. Pan also enabled (translate).
    this.zoomBehaviour = zoom<SVGSVGElement, unknown>()
      .scaleExtent([1, 10])
      .translateExtent([
        [this.PAD_LEFT, 0],
        [this.PAD_LEFT + this.innerWidth(), this.totalHeight()],
      ])
      .filter((event) => {
        // Allow wheel and middle-button drag to zoom/pan.
        if (event.type === 'wheel') return true;
        if (event.type === 'mousedown' && event.button !== 0) return true;
        // Disallow primary-button drag (so click-to-seek stays clean).
        return false;
      })
      .on('zoom', (event: D3ZoomEvent<SVGSVGElement, unknown>) => {
        this.currentTransform = event.transform;
        this.render();
      });
    this.svg.call(this.zoomBehaviour);

    // Hover + click handlers on the background rect.
    const bg = this.viewport.select<SVGRectElement>('rect.lane-bg');
    bg.on('mousemove', (event: MouseEvent) => {
      const [mx] = pointerOffset(event, this.svg.node()!);
      this.showHover(mx);
    });
    bg.on('mouseleave', () => {
      this.hoverhead.attr('opacity', 0);
      this.hoverLabel.attr('opacity', 0);
      this.tooltip.style.opacity = '0';
    });
    bg.on('click', (event: MouseEvent) => {
      const [mx] = pointerOffset(event, this.svg.node()!);
      const xs = this.currentXScale();
      const idx = Math.round(xs.invert(mx));
      const clamped = Math.max(0, Math.min(this.events.length - 1, idx));
      this.onSeek(clamped);
    });
  }

  private currentXScale(): ScaleLinear<number, number> {
    return this.currentTransform.rescaleX(this.xScale);
  }

  // X-coordinate for the i-th surviving tick — evenly spread across the
  // lane width independent of event_index. Honours the current zoom/pan
  // transform so markers stay aligned with everything else under d3-zoom.
  private xForSurvivor(i: number): number {
    const n = this.survivors.length;
    const left = this.PAD_LEFT;
    const right = this.PAD_LEFT + this.innerWidth();
    let raw: number;
    if (n <= 1) {
      raw = (left + right) / 2;
    } else {
      raw = left + ((right - left) * i) / (n - 1);
    }
    // Apply the same x-transform d3-zoom uses so markers track the axis
    // when the user pans/zooms the timeline.
    return this.currentTransform.applyX(raw);
  }

  resize() {
    this.xScale.range([this.PAD_LEFT, this.PAD_LEFT + this.innerWidth()]);
    this.viewport
      .select<SVGRectElement>('rect.lane-bg')
      .attr('width', this.innerWidth());
    this.zoomBehaviour.translateExtent([
      [this.PAD_LEFT, 0],
      [this.PAD_LEFT + this.innerWidth(), this.totalHeight()],
    ]);
    this.render();
  }

  private render() {
    const xs = this.currentXScale();

    // ── Axis (event-index labels) ──
    const axis = axisTop<number>(xs)
      .ticks(8)
      .tickFormat((d) => {
        const i = Math.round(Number(d));
        if (i < 0 || i >= this.events.length) return '';
        return `#${i + 1}`;
      });
    this.axisGroup.call(axis);
    this.axisGroup.selectAll<SVGLineElement, unknown>('line').attr('stroke', PALETTE.grid);
    this.axisGroup.selectAll<SVGPathElement, unknown>('path.domain').attr('stroke', PALETTE.grid);
    this.axisGroup.selectAll<SVGTextElement, unknown>('text').attr('fill', PALETTE.fgMute).attr('font-size', 10);

    // ── Round dividers (now at event-index positions) ──
    const boundaries = this.collectRoundBoundaries();
    const lineSel = this.roundsGroup
      .selectAll<SVGLineElement, RoundBoundary>('line.round-divider')
      .data(boundaries, (d) => `${d.roundId}:${d.kind}`);
    lineSel.exit().remove();
    const lineEnter = lineSel
      .enter()
      .append('line')
      .attr('class', 'round-divider')
      .attr('y1', this.AXIS_HEIGHT)
      .attr('y2', this.AXIS_HEIGHT + this.LANE_HEIGHT * 2 + this.LANE_GAP)
      .attr('stroke', PALETTE.grid)
      .attr('stroke-width', 1)
      .attr('stroke-dasharray', (d) => (d.kind === 'open' ? null : '2 4'));
    lineEnter.merge(lineSel)
      .attr('x1', (d) => xs(d.evIdx))
      .attr('x2', (d) => xs(d.evIdx))
      .attr('opacity', 0.55);

    // Round labels at top of axis, positioned at round_open boundaries.
    const labelSel = this.roundsGroup
      .selectAll<SVGTextElement, RoundBoundary>('text.round-label')
      .data(boundaries.filter((b) => b.kind === 'open'), (d) => d.roundId);
    labelSel.exit().remove();
    const labelEnter = labelSel
      .enter()
      .append('text')
      .attr('class', 'round-label')
      .attr('y', 12)
      .attr('font-size', 10)
      .attr('font-family', 'system-ui, sans-serif')
      .attr('fill', PALETTE.fgMute)
      .attr('opacity', 0.85);
    labelEnter.merge(labelSel)
      .attr('x', (d) => xs(d.evIdx) + 4)
      .text((d) => d.roundId);

    // ── Event blocks (equal width within a lane) ──
    const retrievalEvents = this.events
      .map((e, idx) => ({ ev: e, idx }))
      .filter((p) => p.ev.event_kind === 'retrieval');
    const growthEvents = this.events
      .map((e, idx) => ({ ev: e, idx }))
      .filter((p) => p.ev.event_kind === 'growth');

    this.renderLane(this.retrievalLane, retrievalEvents, 'retrieval', xs);
    this.renderLane(this.growthLane, growthEvents, 'growth', xs);
    this.renderTickMarkers();
    // Keep the playhead glued to the right surviving-tick column under
    // zoom/pan and resize. setPlayheadTick reads the current transform.
    if (this.lastTickCursor !== -1 || this.survivors.length > 0) {
      this.setPlayheadTick(this.lastTickCursor);
    }
  }

  private renderTickMarkers() {
    // One small triangle per *surviving* IR-tick. Markers are spread
    // evenly across the lane width (surviving-tick index, not event
    // index) — orphan ticks no longer render at all, since the auto-
    // player zero-skips them and they produce no animation. LKM-driven
    // ticks are filled (retrieval blue); pure-IR ticks are open.
    const markers: TickMarker[] = this.survivors.map((t, i) => ({
      survIdx: i,
      evIdx: t.event_index,
      tickIdx: t.tick_index,
      lkmDriven: t.lkm_driven,
    }));
    const sel = this.tickMarkerGroup
      .selectAll<SVGPathElement, TickMarker>('path.tick-marker')
      .data(markers, (d) => String(d.tickIdx));
    sel.exit().remove();
    const enter = sel
      .enter()
      .append('path')
      .attr('class', 'tick-marker')
      .attr('cursor', 'pointer')
      .on('click', (event: MouseEvent, d) => {
        event.stopPropagation();
        this.onTickSeek(d.tickIdx);
      });
    enter.merge(sel)
      .attr('d', 'M-3,0 L3,0 L0,5 Z')
      .attr('transform', (d) => `translate(${this.xForSurvivor(d.survIdx)}, 0)`)
      .attr('fill', (d) => (d.lkmDriven ? PALETTE.retrieval : 'transparent'))
      .attr('stroke', PALETTE.retrieval)
      .attr('stroke-width', 1)
      .attr('opacity', 0.85);
  }

  private renderLane(
    laneSel: Selection<SVGGElement, unknown, null, undefined>,
    items: Array<{ ev: TimelineEvent; idx: number }>,
    kind: 'retrieval' | 'growth',
    xs: ScaleLinear<number, number>
  ) {
    // Block half-width: half the spacing between two adjacent events on the
    // global index axis. We compute it dynamically so that zooming widens
    // each block proportionally.
    const blockHalf = Math.max(1.5, (xs(1) - xs(0)) * 0.42);

    const blocks = laneSel
      .selectAll<SVGRectElement, { ev: TimelineEvent; idx: number }>('rect.evt-block')
      .data(items, (d) => d.ev.event_id);
    blocks.exit().remove();
    const enter = blocks
      .enter()
      .append('rect')
      .attr('class', 'evt-block')
      .attr('y', 6)
      .attr('height', this.LANE_HEIGHT - 12)
      .attr('rx', 1.5)
      .attr('cursor', 'pointer')
      .on('click', (event: MouseEvent, d) => {
        event.stopPropagation();
        this.onEventClick(d.idx);
      })
      .on('mousemove', (event: MouseEvent, d) => {
        this.showTooltipFor(d.ev, d.idx, event);
      })
      .on('mouseleave', () => {
        this.tooltip.style.opacity = '0';
      });

    const merge = enter.merge(blocks);
    merge
      .attr('x', (d) => xs(d.idx) - blockHalf)
      .attr('width', blockHalf * 2)
      .attr('fill', (d) =>
        kind === 'retrieval'
          ? RETRIEVAL_COLOURS[d.ev.channel || ''] || PALETTE.retrieval
          : GROWTH_FAMILY[d.ev.decision || ''] || PALETTE.neutral
      )
      .attr('opacity', 0.9);
  }

  private collectRoundBoundaries(): RoundBoundary[] {
    const out: RoundBoundary[] = [];
    for (let i = 0; i < this.events.length; i++) {
      const ev = this.events[i];
      if (ev.decision === 'round_open' && ev.round_id) {
        out.push({ evIdx: i, kind: 'open', roundId: ev.round_id });
      } else if (ev.decision === 'round_close' && ev.round_id) {
        out.push({ evIdx: i, kind: 'close', roundId: ev.round_id });
      }
    }
    return out;
  }

  /**
   * Position the playhead by *tick* cursor. Pass -1 to park at start.
   * Maps the cursor tick to a surviving-tick index (orphans inherit the
   * most recent prior surviving tick's index, so the playhead stays put
   * while the player burns through them) and projects to the surviving-
   * tick x-axis.
   */
  setPlayheadTick(tickIdx: number) {
    this.lastTickCursor = tickIdx;
    if (this.survivors.length === 0) {
      // Park outside the lane area when there's nothing to show.
      this.playhead.attr('x1', -10).attr('x2', -10);
      return;
    }
    let survIdx: number;
    if (tickIdx < 0) {
      // Park just to the left of the first surviving marker.
      const first = this.xForSurvivor(0);
      const second =
        this.survivors.length > 1 ? this.xForSurvivor(1) : first + 12;
      const x = first - (second - first) * 0.5;
      this.playhead.attr('x1', x).attr('x2', x);
      return;
    } else if (tickIdx >= this.survIdxByTick.length) {
      survIdx = this.survivors.length - 1;
    } else {
      survIdx = this.survIdxByTick[tickIdx];
      if (survIdx < 0) survIdx = 0;
    }
    const x = this.xForSurvivor(survIdx);
    this.playhead.attr('x1', x).attr('x2', x);
  }

  /**
   * Total number of surviving ticks (the UI-visible denominator for
   * the scrub control + position counter).
   */
  survivingCount(): number {
    return this.survivors.length;
  }

  /**
   * Map a cursor tick index to its surviving-tick index for UI display.
   * Returns -1 when no surviving tick has been reached yet.
   */
  survivingIndexFor(tickIdx: number): number {
    if (tickIdx < 0 || this.survIdxByTick.length === 0) return -1;
    if (tickIdx >= this.survIdxByTick.length) {
      return this.survivors.length - 1;
    }
    return this.survIdxByTick[tickIdx];
  }

  /**
   * Inverse of `survivingIndexFor`: given a surviving index (0-based),
   * return the original tick index of that surviving tick. Used by the
   * scrub bar to snap to surviving-tick boundaries.
   */
  tickIndexForSurviving(survIdx: number): number {
    if (this.survivors.length === 0) return -1;
    const clamped = Math.max(0, Math.min(this.survivors.length - 1, survIdx));
    return this.survivors[clamped].tick_index;
  }

  /**
   * Highlight blocks for events with index <= cursor.
   */
  setCursor(idx: number) {
    this.svg.selectAll<SVGRectElement, { ev: TimelineEvent; idx: number }>('rect.evt-block')
      .attr('opacity', (d) => (d.idx <= idx ? 1 : 0.35))
      .attr('stroke', (d) => (d.idx === idx ? PALETTE.fg : 'none'))
      .attr('stroke-width', (d) => (d.idx === idx ? 1.5 : 0));
  }

  private showHover(mx: number) {
    const xs = this.currentXScale();
    const idx = Math.round(xs.invert(mx));
    if (idx < 0 || idx >= this.events.length) {
      this.hoverhead.attr('opacity', 0);
      this.hoverLabel.attr('opacity', 0);
      return;
    }
    const x = xs(idx);
    this.hoverhead.attr('x1', x).attr('x2', x).attr('opacity', 0.6);
    this.hoverLabel.attr('x', x).attr('opacity', 0.85).text(`event #${idx + 1}`);
  }

  private showTooltipFor(ev: TimelineEvent, idx: number, event: MouseEvent) {
    const tail = ev.event_id.split('__').slice(-2).join('__'); // last two slots
    const what =
      ev.event_kind === 'retrieval'
        ? `${ev.channel ?? '?'}`
        : `${ev.decision ?? '?'}`;
    const frontier =
      ev.frontier_claim && (ev.frontier_claim.label || ev.frontier_claim.lkm_id)
        ? ` · frontier=${ev.frontier_claim.label || ev.frontier_claim.lkm_id}`
        : '';
    this.tooltip.textContent = `event #${idx + 1} · ${what} · ${tail}${frontier}`;
    const rect = this.host.getBoundingClientRect();
    const x = event.clientX - rect.left + 10;
    const y = event.clientY - rect.top - 28;
    this.tooltip.style.left = `${x}px`;
    this.tooltip.style.top = `${y}px`;
    this.tooltip.style.opacity = '1';
  }
}

function pointerOffset(event: MouseEvent, target: SVGSVGElement): [number, number] {
  const rect = target.getBoundingClientRect();
  return [event.clientX - rect.left, event.clientY - rect.top];
}
