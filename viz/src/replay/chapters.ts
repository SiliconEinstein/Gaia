// Chapter strip — v3 (event-index sub-labels).
//
// Compact horizontal chip rail: one chip per stage_transition, round_open,
// and round_close. Click a chip to seek the player. Sub-labels now read
// "events #N–#M" (or simply "open"/"close"/"from <stage>") — never time
// strings.
//
// v4 polish: chapter chips reflect the *surviving* tick population only.
// A chapter whose event-span contains no surviving IR-ticks (i.e. nothing
// the player will actually animate) is dropped. The "events #N–#M" range
// is rebuilt from the first/last *surviving-tick* event indices inside
// the chapter's span, so labels never advertise orphan event ranges.

import type { IrTick, TimelineEvent } from './types';

interface Chapter {
  evIdx: number; // index into the merged events array
  endEvIdx: number; // last event index belonging to this chapter
  label: string;
  sub: string;
  kind: 'stage' | 'round_open' | 'round_close';
}

export class ChapterStrip {
  private host: HTMLElement;
  private events: TimelineEvent[];
  private ticks: IrTick[];
  private chapters: Chapter[] = [];
  private onSeek: (idx: number) => void = () => {};

  constructor(host: HTMLElement, events: TimelineEvent[], ticks: IrTick[] = []) {
    this.host = host;
    this.events = events;
    this.ticks = ticks;
    this.host.classList.add('chapter-strip');
    this.computeChapters();
    this.render();
  }

  setSeekHandler(fn: (idx: number) => void) {
    this.onSeek = fn;
  }

  private computeChapters() {
    if (this.events.length === 0) return;
    const raw: Chapter[] = [];
    for (let i = 0; i < this.events.length; i++) {
      const ev = this.events[i];
      if (ev.decision === 'stage_transition') {
        const payload = (ev.payload as Record<string, unknown> | undefined) || {};
        const from = String(payload['from'] ?? '?');
        const to = String(payload['to'] ?? '?');
        raw.push({
          evIdx: i,
          endEvIdx: this.events.length - 1,
          label: String(to),
          sub: `from ${from}`,
          kind: 'stage',
        });
      } else if (ev.decision === 'round_open') {
        raw.push({
          evIdx: i,
          endEvIdx: this.events.length - 1,
          label: ev.round_id || 'round',
          sub: 'open',
          kind: 'round_open',
        });
      } else if (ev.decision === 'round_close') {
        raw.push({
          evIdx: i,
          endEvIdx: this.events.length - 1,
          label: ev.round_id || 'round',
          sub: 'close',
          kind: 'round_close',
        });
      }
    }
    // Compute end-of-chapter as one before the next chapter's start.
    for (let k = 0; k < raw.length - 1; k++) {
      raw[k].endEvIdx = Math.max(raw[k].evIdx, raw[k + 1].evIdx - 1);
    }

    // Surviving-tick event indices, sorted ascending. A chapter is kept
    // iff at least one surviving tick falls within its [evIdx, endEvIdx]
    // span; the displayed range is built from the first/last such tick.
    const survEvIdxs = Array.from(
      new Set(
        this.ticks
          .filter((t) => t.survives_to_final !== false)
          .map((t) => t.event_index)
      )
    ).sort((a, b) => a - b);

    const kept: Chapter[] = [];
    for (const c of raw) {
      const inside = survEvIdxs.filter(
        (e) => e >= c.evIdx && e <= c.endEvIdx
      );
      if (inside.length === 0) {
        // Chapter spans only orphan / non-IR events — nothing to animate.
        continue;
      }
      const first = inside[0];
      const last = inside[inside.length - 1];
      const range =
        first === last
          ? `event #${first + 1}`
          : `events #${first + 1}–#${last + 1}`;
      kept.push({ ...c, sub: `${c.sub} · ${range}` });
    }
    this.chapters = kept;
  }

  private render() {
    this.host.innerHTML = '';
    for (const ch of this.chapters) {
      const chip = document.createElement('button');
      chip.className = `chip chip-${ch.kind}`;
      chip.dataset.evIdx = String(ch.evIdx);
      chip.title = `seek to event #${ch.evIdx + 1}`;
      const lbl = document.createElement('span');
      lbl.className = 'chip-label';
      lbl.textContent = ch.label;
      const sub = document.createElement('span');
      sub.className = 'chip-sub';
      sub.textContent = ch.sub;
      chip.appendChild(lbl);
      chip.appendChild(sub);
      chip.addEventListener('click', () => this.onSeek(ch.evIdx));
      this.host.appendChild(chip);
    }
  }

  setCursor(eventIdx: number) {
    if (this.chapters.length === 0) return;
    // Active chapter = last chapter whose evIdx <= cursor.
    let active = -1;
    for (let i = 0; i < this.chapters.length; i++) {
      if (this.chapters[i].evIdx <= eventIdx) active = i;
      else break;
    }
    const chips = this.host.querySelectorAll<HTMLButtonElement>('.chip');
    chips.forEach((c, i) => {
      c.classList.toggle('active', i === active);
      c.classList.toggle('past', i < active);
    });
  }
}
