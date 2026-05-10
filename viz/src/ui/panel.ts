import type Graph from 'graphology';
import type { AnyNode } from '../types';
import { isStrategy, isOperator } from '../types';

function escapeHtml(s: unknown): string {
  if (s == null) return '';
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function fmtBelief(b: number | null | undefined): string {
  if (b == null) return '<span class="badge">unknown</span>';
  return b.toFixed(3);
}

export interface PanelHandle {
  show(nodeId: string): void;
  hide(): void;
}

export function mountPanel(host: HTMLElement, graph: Graph): PanelHandle {
  const root = document.createElement('div');
  root.className = 'side-panel';
  root.innerHTML = `
    <header>
      <h2 id="panel-title">node</h2>
      <button id="panel-close" aria-label="close">×</button>
    </header>
    <div class="body" id="panel-body"></div>
  `;
  host.appendChild(root);

  const titleEl = root.querySelector<HTMLElement>('#panel-title')!;
  const bodyEl = root.querySelector<HTMLElement>('#panel-body')!;
  const closeBtn = root.querySelector<HTMLElement>('#panel-close')!;

  closeBtn.addEventListener('click', () => hide());

  // dismiss on outside click
  document.addEventListener('mousedown', (e) => {
    if (!root.classList.contains('open')) return;
    const target = e.target as Node;
    if (root.contains(target)) return;
    // ignore clicks on sigma container — node clicks reopen via show()
    hide();
  });

  function hide() {
    root.classList.remove('open');
  }

  function show(nodeId: string) {
    if (!graph.hasNode(nodeId)) return;
    const attrs = graph.getNodeAttributes(nodeId) as { raw: AnyNode };
    const node = attrs.raw;

    let title: string;
    let kind: string;
    if (isStrategy(node)) {
      title = `strategy · ${node.strategy_type || ''}`;
      kind = 'strategy';
    } else if (isOperator(node)) {
      title = `operator · ${node.operator_type || ''}`;
      kind = 'operator';
    } else {
      title = node.label || node.id;
      kind = node.type || 'unknown';
    }
    titleEl.textContent = title;

    const inDeg = graph.inDegree(nodeId);
    const outDeg = graph.outDegree(nodeId);

    const rows: Array<[string, string]> = [
      ['id', escapeHtml(node.id)],
      ['type', `<span class="badge">${escapeHtml(kind)}</span>`],
    ];

    if (isStrategy(node)) {
      if (node.reason) rows.push(['reason', escapeHtml(node.reason)]);
    } else if (isOperator(node)) {
      rows.push(['operator', escapeHtml(node.operator_type)]);
    } else {
      const k = node;
      if (k.title) rows.push(['title', escapeHtml(k.title)]);
      if (k.module) rows.push(['module', escapeHtml(k.module)]);
      rows.push(['prior', k.prior == null ? '—' : k.prior.toFixed(3)]);
      rows.push(['belief', fmtBelief(k.belief)]);
      if (k.exported) rows.push(['exported', '✓']);
    }

    if ((node as { module?: string }).module && !rows.find((r) => r[0] === 'module')) {
      rows.push(['module', escapeHtml((node as { module?: string }).module)]);
    }

    rows.push(['edges', `in: ${inDeg} · out: ${outDeg}`]);

    let html = '<dl>';
    for (const [k, v] of rows) {
      html += `<dt>${escapeHtml(k)}</dt><dd>${v}</dd>`;
    }
    html += '</dl>';

    const content = (node as { content?: string }).content;
    if (content && content.trim()) {
      const truncated = content.length > 1500 ? content.slice(0, 1500) + '…' : content;
      html += `<pre class="content">${escapeHtml(truncated)}</pre>`;
    }

    bodyEl.innerHTML = html;
    root.classList.add('open');
  }

  return { show, hide };
}
