import './style/style.css';
import type { GraphData } from './types';
import { buildGraph, initSigma, runLayout } from './starmap';
import { mountPanel } from './ui/panel';
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
