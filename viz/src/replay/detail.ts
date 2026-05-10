// Move 3 — LangSmith-style structured detail panel.
//
// Type-aware renderer: each event kind gets its own template, pulling the
// most operationally-meaningful fields up to the top, then dropping the full
// JSON in a collapsible "Raw JSON" section at the bottom.

import type { TimelineEvent } from './types';

export class DetailPanel {
  private root: HTMLElement;
  private titleEl: HTMLElement;
  private bodyEl: HTMLElement;

  constructor(root: HTMLElement) {
    this.root = root;
    this.root.classList.add('detail-panel');
    this.root.innerHTML = `
      <div class="panel-head">
        <div class="panel-titles">
          <div class="panel-kind" id="panel-kind"></div>
          <div class="panel-title" id="panel-title">Select an event</div>
        </div>
        <button id="panel-close" class="btn-close" aria-label="close">×</button>
      </div>
      <div class="panel-body" id="panel-body">
        <div class="panel-empty">Click any block, node, or chapter chip to inspect an event.</div>
      </div>
    `;
    this.titleEl = this.root.querySelector('#panel-title')!;
    this.bodyEl = this.root.querySelector('#panel-body')!;
    const closeBtn = this.root.querySelector('#panel-close') as HTMLElement;
    closeBtn.addEventListener('click', () => this.hide());
  }

  show(ev: TimelineEvent) {
    const kindEl = this.root.querySelector('#panel-kind') as HTMLElement;
    kindEl.textContent =
      ev.event_kind === 'retrieval'
        ? `retrieval · ${ev.channel || '?'}`
        : `growth · ${ev.decision || '?'}`;
    const tail = ev.event_id.split('__').pop() || '';
    this.titleEl.textContent = `seq ${ev.seq ?? '?'} · ${ev.actor || ev.actor_id || '?'} · #${tail}`;
    this.bodyEl.innerHTML = '';
    this.bodyEl.appendChild(this.renderTemplate(ev));
    this.bodyEl.appendChild(this.renderGaiaActionsSection(ev));
    this.bodyEl.appendChild(this.renderRawJsonSection(ev));
    this.root.classList.remove('hidden');
  }

  private renderGaiaActionsSection(ev: TimelineEvent): HTMLElement {
    const wrap = elt('div', 'gaia-actions');
    const ga = ev.gaia_actions;
    if (!Array.isArray(ga) || ga.length === 0) return wrap;
    const lines = ga.map((a) => {
      const sym = a.symbol ? `${a.symbol}` : '(no symbol)';
      const file = a.file ? `  ${a.file}` : '';
      return `${a.action}: ${sym}${file}`;
    });
    appendKv(wrap, 'gaia_actions', lines.join('\n'), true);
    return wrap;
  }

  hide() {
    this.root.classList.add('hidden');
  }

  private renderTemplate(ev: TimelineEvent): HTMLElement {
    const kind = ev.event_kind;
    if (kind === 'retrieval') return this.renderRetrieval(ev);
    return this.renderGrowth(ev);
  }

  private renderRetrieval(ev: TimelineEvent): HTMLElement {
    const root = elt('div', 'tmpl');
    const req = (ev.request as Record<string, unknown> | undefined) || {};
    const summary = (ev.result_summary as Record<string, unknown> | undefined) || {};
    const queryText = typeof req['text'] === 'string' ? (req['text'] as string) : undefined;
    const lkmId = typeof req['lkm_id'] === 'string' ? (req['lkm_id'] as string) : undefined;
    const topK = typeof req['top_k'] === 'number' ? (req['top_k'] as number) : undefined;
    const candCount = typeof summary['candidate_count'] === 'number' ? summary['candidate_count'] : undefined;

    appendKv(root, 'Channel', ev.channel || '?');
    if (ev.frontier_claim?.label) appendKv(root, 'Frontier', ev.frontier_claim.label);
    if (queryText) appendKv(root, 'Query', queryText);
    if (lkmId) appendKv(root, 'LKM ID', lkmId);
    if (topK != null) appendKv(root, 'Top-k', String(topK));
    if (candCount != null) appendKv(root, 'Returned', `${candCount} candidate(s)`);
    if (Array.isArray(summary['candidate_ids'])) {
      appendKv(root, 'Candidates', (summary['candidate_ids'] as string[]).join(', '));
    }
    if (Array.isArray(summary['evidence_ids']) && (summary['evidence_ids'] as string[]).length > 0) {
      appendKv(root, 'Evidence', (summary['evidence_ids'] as string[]).join(', '));
    }
    if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
    return root;
  }

  private renderGrowth(ev: TimelineEvent): HTMLElement {
    const root = elt('div', 'tmpl');
    const dec = ev.decision || 'unknown';
    const payload = (ev.payload as Record<string, unknown> | undefined) || {};

    switch (dec) {
      case 'candidate_considered': {
        const frontierLbl =
          (payload['frontier_claim'] as { label?: string } | null)?.label ||
          ev.frontier_claim?.label ||
          '(none)';
        appendKv(root, 'Frontier', frontierLbl);
        appendKv(root, 'Candidate', String(payload['candidate_lkm_id'] || '?'));
        if (payload['evidence_status']) appendKv(root, 'Evidence', String(payload['evidence_status']));
        if (payload['preliminary_verdict']) appendKv(root, 'Verdict', String(payload['preliminary_verdict']));
        appendScopeTuple(root, ev);
        appendScopeDiff(root, ev);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'accepted_support':
      case 'accepted_claim':
      case 'accepted_deduction':
      case 'accepted_contradiction': {
        appendKv(root, 'Candidate', String(payload['candidate_lkm_id'] || '?'));
        const strength =
          payload['support_strength'] || payload['contradiction_strength'] || payload['strength'];
        if (strength) appendKv(root, 'Strength', String(strength));
        if (ev.warrant_prior != null) appendKv(root, 'Warrant prior', String(ev.warrant_prior));
        appendEdgesAdded(root, ev);
        appendScopeTuple(root, ev);
        appendScopeDiff(root, ev);
        if (ev.open_problem) appendKv(root, 'Open problem', ev.open_problem, true);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'dismissed':
      case 'support_not_found':
      case 'conflict_not_found':
      case 'not_found':
      case 'needs_more_evidence': {
        appendKv(
          root,
          'Frontier',
          ev.frontier_claim?.label || (payload['frontier_claim'] as { label?: string } | null)?.label || '(none)'
        );
        if (payload['candidate_lkm_id']) appendKv(root, 'Candidate', String(payload['candidate_lkm_id']));
        if (ev.rejection_reason) appendKv(root, 'Reason', ev.rejection_reason, true);
        if (ev.open_problem) appendKv(root, 'Open problem', ev.open_problem, true);
        appendScopeDiff(root, ev);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'equivalence': {
        const peers = payload['equivalent_lkm_ids'] || payload['absorbed_lkm_ids'] || payload['members'];
        if (Array.isArray(peers)) appendKv(root, 'Equivalent', (peers as string[]).join(' ≡ '));
        if (payload['canonical_lkm_id']) appendKv(root, 'Canonical (planned)', String(payload['canonical_lkm_id']));
        if (ev.warrant_prior != null) appendKv(root, 'Warrant prior', String(ev.warrant_prior));
        appendNodesAdded(root, ev);
        appendEdgesAdded(root, ev);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'merge':
      case 'keep_distinct': {
        const absorbed = payload['absorbed_lkm_ids'] || payload['merged_lkm_ids'];
        if (Array.isArray(absorbed)) appendKv(root, 'Absorbed', (absorbed as string[]).join(', '));
        if (payload['canonical_lkm_id']) appendKv(root, 'Canonical', String(payload['canonical_lkm_id']));
        if (ev.warrant_prior != null) appendKv(root, 'Warrant prior', String(ev.warrant_prior));
        appendNodesAdded(root, ev);
        appendNodesRemoved(root, ev);
        appendEdgesRemoved(root, ev);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'round_open': {
        appendKv(root, 'Round', String(payload['round_id'] || ev.round_id || '?'));
        const fIn = payload['frontier_in'];
        if (Array.isArray(fIn)) {
          const labels = (fIn as Array<{ label?: string; lkm_id?: string }>).map(
            (f) => f.label || f.lkm_id || '?'
          );
          appendKv(root, 'Frontier in', labels.length ? labels.join(', ') : '(empty)');
        }
        const fSeen = payload['frontier_visited_so_far'];
        if (Array.isArray(fSeen)) {
          const labels = (fSeen as Array<{ label?: string; lkm_id?: string }>).map(
            (f) => f.label || f.lkm_id || '?'
          );
          appendKv(root, 'Visited so far', labels.length ? labels.join(', ') : '(none)');
        }
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'round_close': {
        appendKv(root, 'Round', String(payload['round_id'] || ev.round_id || '?'));
        const summary = payload['decisions_summary'];
        if (summary && typeof summary === 'object') {
          const entries = Object.entries(summary as Record<string, unknown>);
          appendKv(
            root,
            'Decisions',
            entries.map(([k, v]) => `${k}: ${v}`).join(', ')
          );
        }
        const fOut = payload['next_frontier'];
        if (Array.isArray(fOut)) {
          const labels = (fOut as Array<{ label?: string; lkm_id?: string }>).map(
            (f) => f.label || f.lkm_id || '?'
          );
          appendKv(root, 'Next frontier', labels.length ? labels.join(', ') : '(empty)');
        }
        if (payload['exhausted'] != null) appendKv(root, 'Exhausted', String(payload['exhausted']));
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'stage_transition': {
        const from = payload['from'] || '?';
        const to = payload['to'] || '?';
        appendKv(root, 'Transition', `${from} → ${to}`);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'hypothesis_added':
      case 'obligation_added': {
        appendKv(root, 'Inquiry kind', String(payload['inquiry_kind'] || dec.replace('_added', '')));
        if (payload['text']) appendKv(root, 'Text', String(payload['text']), true);
        if (payload['scope']) appendKv(root, 'Scope', String(payload['scope']));
        if (payload['cli_command']) appendKv(root, 'CLI', String(payload['cli_command']), true);
        if (ev.open_problem) appendKv(root, 'Open problem', ev.open_problem, true);
        appendNodesAdded(root, ev);
        appendEdgesAdded(root, ev);
        break;
      }
      case 'selected_root': {
        appendKv(root, 'Selected', String(payload['selected_lkm_id'] || '?'));
        if (payload['selected_by']) appendKv(root, 'By', String(payload['selected_by']));
        if (payload['rationale']) appendKv(root, 'Rationale', String(payload['rationale']), true);
        if (ev.warrant_prior != null) appendKv(root, 'Warrant prior', String(ev.warrant_prior));
        appendNodesAdded(root, ev);
        appendScopeTuple(root, ev);
        break;
      }
      case 'package_initialized': {
        if (payload['package_name']) appendKv(root, 'Package', String(payload['package_name']));
        if (payload['import_name']) appendKv(root, 'Import name', String(payload['import_name']));
        if (payload['package_uuid']) appendKv(root, 'UUID', String(payload['package_uuid']));
        if (payload['search_query']) appendKv(root, 'Search query', String(payload['search_query']), true);
        if (payload['generated_by']) appendKv(root, 'Generated by', String(payload['generated_by']));
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'user_selection_checkpoint_opened':
      case 'user_selection_checkpoint_closed': {
        if (payload['prompt']) appendKv(root, 'Prompt', String(payload['prompt']), true);
        const pool = payload['candidate_pool'];
        if (Array.isArray(pool)) {
          const labels = (pool as Array<{ label?: string; lkm_id?: string }>).map(
            (p) => p.label || p.lkm_id || '?'
          );
          appendKv(root, 'Candidate pool', labels.join(', '));
        }
        if (payload['selected_lkm_id']) appendKv(root, 'Selected', String(payload['selected_lkm_id']));
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'quality_gate_result': {
        if (payload['status']) appendKv(root, 'Status', String(payload['status']));
        const cmds = payload['commands'];
        if (Array.isArray(cmds)) {
          appendKv(
            root,
            'Commands',
            (cmds as unknown[]).map((c) => (typeof c === 'string' ? c : JSON.stringify(c))).join('\n'),
            true
          );
        }
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'prior_added': {
        if (payload['target_lkm_id']) appendKv(root, 'Target', String(payload['target_lkm_id']));
        if (ev.warrant_prior != null) appendKv(root, 'Prior', String(ev.warrant_prior));
        if (payload['by']) appendKv(root, 'By', String(payload['by']));
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      case 'repair': {
        if (ev['supersedes_event_id']) appendKv(root, 'Supersedes', String(ev['supersedes_event_id']));
        if (ev.warrant_prior != null) appendKv(root, 'Warrant prior', String(ev.warrant_prior));
        appendScopeTuple(root, ev);
        appendScopeDiff(root, ev);
        if (ev.notes) appendKv(root, 'Notes', ev.notes, true);
        break;
      }
      default: {
        // Fallback: legible labelled key/value list for any decision we
        // haven't templated explicitly. Better than `<pre>`.
        appendKv(root, 'Decision', dec);
        if (ev.frontier_claim?.label) appendKv(root, 'Frontier', ev.frontier_claim.label);
        const interesting: string[] = [
          'open_problem', 'rejection_reason', 'warrant_prior', 'notes',
        ];
        for (const k of interesting) {
          const v = (ev as Record<string, unknown>)[k];
          if (v != null && v !== '') appendKv(root, prettyKey(k), String(v), true);
        }
        // Spread payload top-level entries.
        for (const [k, v] of Object.entries(payload)) {
          if (v == null) continue;
          if (typeof v === 'object') {
            appendKv(root, prettyKey(k), JSON.stringify(v), true);
          } else {
            appendKv(root, prettyKey(k), String(v));
          }
        }
        break;
      }
    }
    return root;
  }

  private renderRawJsonSection(ev: TimelineEvent): HTMLElement {
    const wrap = elt('details', 'raw-json');
    const summary = elt('summary', '');
    summary.textContent = 'Raw JSON';
    wrap.appendChild(summary);
    const pre = elt('pre', '');
    pre.textContent = JSON.stringify(ev, null, 2);
    wrap.appendChild(pre);
    return wrap;
  }
}

// ── helpers ──

function elt(tag: string, cls: string): HTMLElement {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  return e;
}

function appendKv(parent: HTMLElement, label: string, value: string, multiline = false) {
  const row = elt('div', `kv${multiline ? ' kv-multi' : ''}`);
  const k = elt('div', 'kv-key');
  k.textContent = label;
  const v = elt('div', 'kv-val');
  v.textContent = value;
  row.appendChild(k);
  row.appendChild(v);
  parent.appendChild(row);
}

function appendScopeTuple(parent: HTMLElement, ev: TimelineEvent) {
  const sc = ev.scope_tuple;
  if (!sc) return;
  const lines: string[] = [];
  for (const [k, v] of Object.entries(sc)) {
    if (v == null) continue;
    lines.push(`${k}: ${v}`);
  }
  if (lines.length) appendKv(parent, 'Scope tuple', lines.join('\n'), true);
}

function appendScopeDiff(parent: HTMLElement, ev: TimelineEvent) {
  const sd = ev.scope_diff;
  if (!sd) return;
  const lines: string[] = [];
  for (const [k, v] of Object.entries(sd)) {
    if (v == null) continue;
    lines.push(`${k}: ${v}`);
  }
  if (lines.length) appendKv(parent, 'Scope diff', lines.join('\n'), true);
}

function appendNodesAdded(parent: HTMLElement, ev: TimelineEvent) {
  const d = ev.graph_delta;
  if (!d || !d.nodes_added.length) return;
  const lines = d.nodes_added.map(
    (n) => `+ ${n.id}${n.kind ? ` [${n.kind}]` : ''}${n.label ? ` — ${n.label}` : ''}`
  );
  appendKv(parent, 'Nodes added', lines.join('\n'), true);
}

function appendNodesRemoved(parent: HTMLElement, ev: TimelineEvent) {
  const d = ev.graph_delta;
  if (!d || !d.nodes_removed.length) return;
  const lines = d.nodes_removed.map(
    (n) => `− ${n.id}${n.kind ? ` [${n.kind}]` : ''}${n.reason ? ` — ${n.reason}` : ''}`
  );
  appendKv(parent, 'Nodes removed', lines.join('\n'), true);
}

function appendEdgesAdded(parent: HTMLElement, ev: TimelineEvent) {
  const d = ev.graph_delta;
  if (!d || !d.edges_added.length) return;
  const lines = d.edges_added.map(
    (e) => `+ ${e.from} → ${e.to}${e.kind ? ` [${e.kind}]` : ''}${e.reason_excerpt ? ` — ${e.reason_excerpt}` : ''}`
  );
  appendKv(parent, 'Edges added', lines.join('\n'), true);
}

function appendEdgesRemoved(parent: HTMLElement, ev: TimelineEvent) {
  const d = ev.graph_delta;
  if (!d || !d.edges_removed.length) return;
  const lines = d.edges_removed.map(
    (e) => `− ${e.from} → ${e.to}${e.kind ? ` [${e.kind}]` : ''}`
  );
  appendKv(parent, 'Edges removed', lines.join('\n'), true);
}

function prettyKey(k: string): string {
  return String(k).replace(/_/g, ' ').replace(/\b\w/g, (c) => c.toUpperCase());
}
