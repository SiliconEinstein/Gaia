import './style/style.css';
import type { GraphData, KnowledgeNode } from './types';
import { isStrategy, isOperator } from './types';
import { buildGraph, initSigma, runLayout } from './starmap';
import { mountPanel, escapeHtml } from './ui/panel';
import { mountSearch } from './ui/search';
import { mountFilter } from './ui/filter';
import { mountMinimap } from './ui/minimap';

declare global {
  interface Window {
    GRAPH_DATA?: GraphData;
  }
}

async function loadData(): Promise<GraphData> {
  if (window.GRAPH_DATA && Array.isArray(window.GRAPH_DATA.nodes)) {
    return window.GRAPH_DATA;
  }
  // dev fallback: fetch sample fixture
  try {
    const r = await fetch('/sample-graph.json');
    if (!r.ok) throw new Error(`status ${r.status}`);
    return (await r.json()) as GraphData;
  } catch (err) {
    console.error('[starmap] failed to load sample-graph.json', err);
    return { modules: [], cross_module_edges: [], nodes: [], edges: [] };
  }
}

/**
 * Hide legend rows for kinds/signals this graph doesn't actually have —
 * e.g. the "operator" swatch is dead weight on a graph with zero operators
 * (a common case: this portfolio's infer-based idea graphs never use
 * operators at all).
 */
function updateLegend(data: GraphData) {
  const hasStrategy = data.nodes.some(isStrategy);
  const hasOperator = data.nodes.some(isOperator);
  const hasEffect = data.edges.some((e) => typeof e.effect === 'number');
  const visibility: Record<string, boolean> = {
    strategy: hasStrategy,
    operator: hasOperator,
    effect: hasEffect,
  };
  document.querySelectorAll<HTMLElement>('#legend [data-legend-for]').forEach((row) => {
    const kind = row.dataset.legendFor!;
    row.classList.toggle('hidden', visibility[kind] === false);
  });
}

/**
 * Populate the topbar's root-claim banner: one item per exported knowledge
 * node (★, the belief-propagation root(s) — `_dot.py`'s gold "root" box
 * uses the same `exported` flag), each showing the current posterior. A
 * package can export more than one root claim, or none; the banner adapts
 * to both. Clicking an item opens that node's side panel — the fuller
 * detail (reason, effect, CPT) lives there rather than being crammed into
 * the topbar.
 */
function renderRootBanner(data: GraphData): void {
  const el = document.getElementById('root-banner')!;
  const roots = data.nodes.filter(
    (n) => !isStrategy(n) && !isOperator(n) && (n as KnowledgeNode).exported === true,
  ) as KnowledgeNode[];

  if (!roots.length) {
    el.classList.add('hidden');
    el.innerHTML = '';
    return;
  }
  el.classList.remove('hidden');
  el.innerHTML = roots
    .map((n) => {
      const label = escapeHtml(n.title || n.label || n.id);
      const belief = n.belief == null ? 'unknown' : n.belief.toFixed(3);
      return (
        `<span class="item" data-node-id="${escapeHtml(n.id)}" title="${label}">` +
        `<span class="star">★</span><span class="label">${label}</span>` +
        `<span class="belief">${belief}</span></span>`
      );
    })
    .join('');
}

function setStatus(msg: string | null) {
  const el = document.getElementById('status');
  if (!el) return;
  if (msg == null) {
    el.classList.add('hidden');
  } else {
    el.classList.remove('hidden');
    el.textContent = msg;
  }
}

async function main() {
  setStatus('loading…');
  const data = await loadData();

  if (!data.nodes.length) {
    setStatus('no graph data');
    return;
  }

  setStatus(`building graph (${data.nodes.length} nodes, ${data.edges.length} edges)…`);
  updateLegend(data);
  renderRootBanner(data);
  const graph = buildGraph(data);

  const container = document.getElementById('sigma-container')!;
  const sigma = initSigma(container, graph);

  // UI
  mountSearch(document.getElementById('search-host')!, graph, sigma);
  mountFilter(document.getElementById('filter-host')!, graph, sigma);
  const panel = mountPanel(document.getElementById('panel-host')!, graph);
  mountMinimap(document.getElementById('minimap-host')!, graph, sigma);

  // Click to open panel
  sigma.on('clickNode', ({ node }) => {
    panel.show(node);
  });
  // Click on empty space dismisses
  sigma.on('clickStage', () => panel.hide());
  // Root-claim banner items open the same panel as clicking the node.
  document.getElementById('root-banner')!.addEventListener('click', (e) => {
    const item = (e.target as HTMLElement).closest<HTMLElement>('[data-node-id]');
    if (item?.dataset.nodeId) panel.show(item.dataset.nodeId);
  });

  // Hover labels for low-importance nodes:
  // we leverage Sigma's built-in highlighted state — when the user hovers a
  // small/low-belief node Sigma already shows its label via the hover layer.
  // We additionally bump labelRenderedSizeThreshold dynamically based on zoom
  // to reveal more labels when the user zooms in.
  const camera = sigma.getCamera();
  camera.on('updated', () => {
    const ratio = camera.getState().ratio;
    // Smaller ratio = zoomed in, threshold lower
    const threshold = Math.max(2, Math.min(10, 6 * ratio));
    sigma.setSetting('labelRenderedSizeThreshold', threshold);
  });

  // Run layout in worker
  setStatus('running layout…');
  const layout = runLayout(graph, 1000);
  layout.start();

  // hide status after a moment regardless; layout keeps running async
  window.setTimeout(() => setStatus(null), 1200);
  // safeguard: ensure layout is stopped if user leaves
  window.addEventListener('beforeunload', () => layout.stop());
}

main().catch((err) => {
  console.error(err);
  setStatus(`error: ${(err as Error).message}`);
});
