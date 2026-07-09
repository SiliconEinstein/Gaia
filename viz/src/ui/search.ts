import type Graph from 'graphology';
import type Sigma from 'sigma';

export interface SearchHandle {
  clear(): void;
}

export function mountSearch(host: HTMLElement, graph: Graph, sigma: Sigma): SearchHandle {
  const root = document.createElement('div');
  root.className = 'search-box';
  root.innerHTML = `
    <input type="text" placeholder="search label / id…" spellcheck="false" />
    <button type="button" title="clear">×</button>
  `;
  host.appendChild(root);

  const input = root.querySelector<HTMLInputElement>('input')!;
  const clearBtn = root.querySelector<HTMLButtonElement>('button')!;

  // remember original highlight state
  const originalSizes = new Map<string, number>();

  function clear() {
    input.value = '';
    graph.forEachNode((id) => {
      const orig = originalSizes.get(id);
      if (orig != null) graph.setNodeAttribute(id, 'size', orig);
      graph.removeNodeAttribute(id, 'highlighted');
    });
    originalSizes.clear();
    sigma.refresh();
  }

  function applyQuery(q: string) {
    const query = q.trim().toLowerCase();
    if (!query) {
      clear();
      return;
    }
    const matches: string[] = [];
    graph.forEachNode((id, attrs) => {
      const label = String(attrs.label || '').toLowerCase();
      const idLow = id.toLowerCase();
      // Hidden nodes (filtered-out kinds, incl. the default-collapsed
      // generated helpers) never MATCH — highlighting an invisible node and
      // recentering the camera on it reads as a no-op — but they still take
      // the restore branch, so a node highlighted by an earlier query and
      // then hidden via the filter sheds its boosted state instead of
      // reappearing highlighted when its bucket is re-enabled.
      const visible = attrs.hidden !== true;
      if (visible && (label.includes(query) || idLow.includes(query))) {
        matches.push(id);
        if (!originalSizes.has(id)) originalSizes.set(id, attrs.size as number);
        graph.setNodeAttribute(id, 'size', (attrs.size as number) * 1.6);
        graph.setNodeAttribute(id, 'highlighted', true);
      } else {
        const orig = originalSizes.get(id);
        if (orig != null) graph.setNodeAttribute(id, 'size', orig);
        graph.removeNodeAttribute(id, 'highlighted');
      }
    });
    sigma.refresh();
    if (matches.length === 0) return;

    // recenter camera on centroid of matches
    let sx = 0, sy = 0;
    matches.forEach((id) => {
      const a = graph.getNodeAttributes(id);
      sx += a.x as number;
      sy += a.y as number;
    });
    sx /= matches.length;
    sy /= matches.length;

    const camera = sigma.getCamera();
    const viewport = sigma.graphToViewport({ x: sx, y: sy });
    const containerRect = sigma.getContainer().getBoundingClientRect();
    const cx = containerRect.width / 2;
    const cy = containerRect.height / 2;

    // animate camera to graph point
    const state = camera.getState();
    const dx = (viewport.x - cx) / containerRect.width;
    const dy = (viewport.y - cy) / containerRect.height;
    camera.animate(
      { x: state.x + dx, y: state.y + dy, ratio: Math.min(state.ratio, 0.6) },
      { duration: 400 },
    );
  }

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      applyQuery(input.value);
    } else if (e.key === 'Escape') {
      clear();
    }
  });
  input.addEventListener('input', () => {
    if (!input.value) clear();
  });
  clearBtn.addEventListener('click', clear);

  return { clear };
}
