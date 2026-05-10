// Starmap Replay v4 — IR-tick playback on a pinned graphviz layout.
//
// Reads `window.TIMELINE_DATA` (a payload baked by `gaia starmap-replay`).
// Composes:
//
//   1. Pinned graph canvas (graph.ts) — every node placed at its DOT-derived
//      `(x, y)`; cluster boxes drawn as rounded rectangles matching the
//      `gaia starmap --format dot` SVG styling.
//   2. Timeline lanes — event-index axis with IR-tick markers (timeline.ts).
//   3. Structured detail panel (detail.ts).
//   4. Chapter chip strip (chapters.ts).
//
// The player advances one IR-tick per step. Each tick lands a single
// `gaia_actions[]` entry on the canonical store, possibly admitting nodes /
// edges and possibly staging an LKM overlay. Round boundaries trigger a
// belief tween across the visible claim nodes.

import './style/replay.css';
import { ChapterStrip } from './replay/chapters';
import { DetailPanel } from './replay/detail';
import { GraphCanvas } from './replay/graph';
import { CanonicalStore } from './replay/store';
import { TimelineLanes } from './replay/timeline';
import type { IrTick, TimelineEvent, TimelinePayload } from './replay/types';

const BASE_TICK_MS = 380;

class Player {
  ticks: IrTick[];
  store: CanonicalStore;
  cursorTick = -1; // last applied tick index
  private playing = false;
  private speed = 1;
  private timer: number | null = null;
  private onTick: (
    cursorTick: number,
    cursorEvent: number,
    result: ReturnType<CanonicalStore['advanceTo']>
  ) => void = () => {};

  constructor(ticks: IrTick[], store: CanonicalStore) {
    this.ticks = ticks;
    this.store = store;
  }

  setTickHandler(fn: typeof this.onTick) {
    this.onTick = fn;
  }

  total() {
    return this.ticks.length;
  }

  reset() {
    this.cursorTick = -1;
    const result = this.store.advanceTo(-1);
    this.onTick(-1, -1, result);
  }

  setSpeed(s: number) {
    this.speed = s;
    if (this.playing) {
      this.stop();
      this.start();
    }
  }

  tickDurationMs(): number {
    return BASE_TICK_MS / Math.max(0.1, this.speed);
  }

  start() {
    if (this.cursorTick >= this.ticks.length - 1) return;
    this.playing = true;
    setPlayLabel('pause');
    // If we're currently parked on an orphan tick (e.g. user scrubbed to
    // one and hit play) the next tick should fire immediately, not after
    // BASE_TICK_MS of dead air.
    const upcoming = this.ticks[this.cursorTick + 1];
    const upcomingIsOrphan = upcoming?.survives_to_final === false;
    this.scheduleNext(upcomingIsOrphan ? 0 : this.tickDurationMs());
  }

  stop() {
    this.playing = false;
    setPlayLabel('play');
    if (this.timer != null) {
      window.clearTimeout(this.timer);
      this.timer = null;
    }
  }

  /**
   * Schedule the next forward step. Auto-play uses `setTimeout` (not
   * `setInterval`) so each step can pick its own delay: orphan ticks
   * (`survives_to_final === false`) advance with zero delay, since they
   * leave the canvas unchanged and the standard 380 ms beat would
   * otherwise show as dead air. A run of consecutive orphans is therefore
   * traversed as a frame-burst, then the next surviving tick resumes the
   * normal cadence. Only the *next* tick's identity matters; whether the
   * current tick was an orphan is irrelevant to the upcoming delay.
   */
  private scheduleNext(delayMs: number) {
    if (!this.playing) return;
    if (this.timer != null) {
      window.clearTimeout(this.timer);
      this.timer = null;
    }
    this.timer = window.setTimeout(() => {
      this.timer = null;
      if (!this.playing) return;
      if (this.cursorTick >= this.ticks.length - 1) {
        this.stop();
        return;
      }
      const nextIdx = this.cursorTick + 1;
      this.advanceTo(nextIdx);
      if (this.cursorTick >= this.ticks.length - 1) {
        this.stop();
        return;
      }
      const upcoming = this.ticks[this.cursorTick + 1];
      const upcomingIsOrphan = upcoming?.survives_to_final === false;
      this.scheduleNext(upcomingIsOrphan ? 0 : this.tickDurationMs());
    }, delayMs);
  }

  toggle() {
    if (this.playing) this.stop();
    else this.start();
  }

  advanceTo(target: number) {
    target = Math.max(-1, Math.min(this.ticks.length - 1, target));
    const result = this.store.advanceTo(target);
    this.cursorTick = target;
    const cursorEvent = target >= 0 ? this.ticks[target].event_index : -1;
    this.onTick(target, cursorEvent, result);
  }

  /** Find the latest tick whose event_index <= *eventIdx*. */
  tickForEvent(eventIdx: number): number {
    let last = -1;
    for (let i = 0; i < this.ticks.length; i++) {
      if (this.ticks[i].event_index <= eventIdx) last = i;
      else break;
    }
    return last;
  }
}

function setPlayLabel(label: string) {
  const btn = document.getElementById('btn-play');
  if (btn) btn.textContent = label;
}

async function loadTimeline(): Promise<TimelinePayload> {
  if (window.TIMELINE_DATA && Array.isArray(window.TIMELINE_DATA.events)) {
    return window.TIMELINE_DATA;
  }
  try {
    const r = await fetch('/sample-timeline.json');
    if (r.ok) return (await r.json()) as TimelinePayload;
  } catch {
    // ignore
  }
  return {
    schema_version: '1',
    package_name: null,
    retrieval_count: 0,
    growth_count: 0,
    events: [],
    ticks: [],
    rounds: [],
    round_beliefs: {},
    final_layout: null,
  };
}

function setStatus(msg: string) {
  const stage = document.getElementById('stage-badge');
  if (stage) stage.textContent = msg;
}

async function main() {
  const data = await loadTimeline();
  if (!data.events.length) {
    setStatus('no timeline data');
    return;
  }

  const pkgEl = document.getElementById('pkg-name');
  if (pkgEl) pkgEl.textContent = data.package_name || '';

  // ── Modules ──
  const detail = new DetailPanel(document.getElementById('event-panel')!);
  const chapterStrip = new ChapterStrip(
    document.getElementById('chapter-strip')!,
    data.events,
    data.ticks
  );
  const timeline = new TimelineLanes(
    document.getElementById('lanes')!,
    data.events,
    data.ticks
  );
  const store = new CanonicalStore({
    events: data.events,
    ticks: data.ticks,
    layout: data.final_layout,
    roundBeliefs: data.round_beliefs,
  });
  const graph = new GraphCanvas(
    document.getElementById('canvas-region')!,
    store,
    data.events
  );
  const player = new Player(data.ticks, store);

  // Total denominator for the scrub control + position counter — the UI
  // surface is *surviving-only*, so we use the count of surviving ticks
  // (orphans are zero-skipped and never get their own slider position).
  // If there are no ticks at all, fall back to event count so the slider
  // still has range.
  const survivingTotal = timeline.survivingCount();
  const total = survivingTotal || data.events.length;

  player.setTickHandler((cursorTick, cursorEvent, result) => {
    graph.applyTick({
      admittedNodeIds: result.admittedNodeIds,
      lkmTicks: result.lkmTicks,
      activeRoundId: result.activeRoundId,
      cursorTick,
      totalTicks: data.ticks.length,
    });

    const cursorForUi = cursorEvent >= 0 ? cursorEvent : -1;
    timeline.setCursor(cursorForUi);
    chapterStrip.setCursor(cursorForUi);
    timeline.setPlayheadTick(cursorTick);

    const stageEl = document.getElementById('stage-badge')!;
    const roundEl = document.getElementById('round-badge')!;
    if (cursorEvent >= 0) {
      const e = data.events[cursorEvent];
      stageEl.textContent = e.stage ? `stage: ${e.stage}` : '';
      roundEl.textContent = result.activeRoundId
        ? `round: ${result.activeRoundId}`
        : e.round_id
        ? `round: ${e.round_id}`
        : '';
    } else {
      stageEl.textContent = '';
      roundEl.textContent = '';
    }
    // Position counter + scrub bar both speak surviving-tick coordinates.
    // While the player is on an orphan, the counter sits at the most-
    // recent surviving tick (matches the playhead's visual position).
    const survIdx = timeline.survivingIndexFor(cursorTick);
    const pos = document.getElementById('position');
    if (pos) pos.textContent = `${survIdx + 1} / ${total}`;
    const scrub = document.getElementById('scrub') as HTMLInputElement;
    if (scrub) scrub.value = String(survIdx + 1);
  });

  player.reset();
  graph.reset();

  // ── Inter-module wiring ──
  timeline.setHandlers({
    onEventClick: (idx) => {
      const ev = data.events[idx];
      detail.show(ev);
    },
    onSeek: (eventIdx) => {
      player.stop();
      const t = player.tickForEvent(eventIdx);
      // Snap to a tick: if the clicked event has no IR-tick, advance to the
      // tick whose event_index is the latest <= clicked. -1 is a clean state.
      player.advanceTo(t);
    },
    onTickSeek: (tickIdx) => {
      // Marker click — jumps directly to that surviving tick by its
      // *original* tick index (event-index lookup is ambiguous when
      // several ticks share an event, so we bypass it here).
      player.stop();
      player.advanceTo(tickIdx);
    },
  });
  chapterStrip.setSeekHandler((eventIdx) => {
    player.stop();
    player.advanceTo(player.tickForEvent(eventIdx));
  });
  graph.setSelectHandler((nodeId) => {
    // Find the most recent event whose gaia_actions or graph_delta first
    // referenced this node, up to the current cursor.
    const upTo = player.cursorTick >= 0 ? data.ticks[player.cursorTick].event_index : data.events.length - 1;
    for (let i = upTo; i >= 0; i--) {
      const ev = data.events[i];
      if (eventReferencesNode(ev, nodeId)) {
        detail.show(ev);
        return;
      }
    }
  });

  // ── Controls ──
  // The scrub bar speaks *surviving-tick* coordinates: every detent on
  // the slider lands on a surviving IR-tick. Dragging through an orphan
  // is impossible from the UI surface (intentional — orphans produce no
  // animation). Internal player state still walks all ticks.
  const scrub = document.getElementById('scrub') as HTMLInputElement;
  scrub.max = String(total);
  scrub.value = '0';
  scrub.addEventListener('input', () => {
    player.stop();
    if (survivingTotal === 0) {
      player.advanceTo(Number(scrub.value) - 1);
      return;
    }
    const survIdx = Number(scrub.value) - 1;
    if (survIdx < 0) {
      player.advanceTo(-1);
    } else {
      player.advanceTo(timeline.tickIndexForSurviving(survIdx));
    }
  });

  document.getElementById('btn-play')!.addEventListener('click', () => {
    player.toggle();
  });
  document.getElementById('btn-restart')!.addEventListener('click', () => {
    player.stop();
    player.reset();
    graph.reset();
  });
  const btnPrev = document.getElementById('btn-step-prev');
  if (btnPrev) {
    btnPrev.addEventListener('click', () => {
      player.stop();
      player.advanceTo(player.cursorTick - 1);
    });
  }
  const btnNext = document.getElementById('btn-step-next');
  if (btnNext) {
    btnNext.addEventListener('click', () => {
      player.stop();
      player.advanceTo(player.cursorTick + 1);
    });
  }
  const speedSel = document.getElementById('speed') as HTMLSelectElement;
  speedSel.addEventListener('change', () => {
    player.setSpeed(Number(speedSel.value));
  });

  let resizeTimer: number | null = null;
  window.addEventListener('resize', () => {
    if (resizeTimer != null) window.clearTimeout(resizeTimer);
    resizeTimer = window.setTimeout(() => {
      timeline.resize();
      graph.resize();
    }, 80);
  });

  window.addEventListener('keydown', (event) => {
    if ((event.target as HTMLElement)?.tagName === 'INPUT') return;
    if (event.code === 'Space') {
      event.preventDefault();
      player.toggle();
    } else if (event.code === 'ArrowRight') {
      event.preventDefault();
      player.stop();
      player.advanceTo(player.cursorTick + 1);
    } else if (event.code === 'ArrowLeft') {
      event.preventDefault();
      player.stop();
      player.advanceTo(player.cursorTick - 1);
    }
  });
}

function eventReferencesNode(ev: TimelineEvent, id: string): boolean {
  for (const a of ev.gaia_actions || []) {
    if (a.symbol === id) return true;
  }
  for (const n of ev.graph_delta?.nodes_added || []) {
    if (n.id === id) return true;
  }
  for (const e of ev.graph_delta?.edges_added || []) {
    if (e.from === id || e.to === id) return true;
  }
  return false;
}

main().catch((err) => {
  // eslint-disable-next-line no-console
  console.error(err);
  setStatus(`error: ${(err as Error).message}`);
});
