import type Graph from 'graphology';
import type Sigma from 'sigma';

export interface FilterHandle {
  refresh(): void;
}

export function mountFilter(host: HTMLElement, graph: Graph, sigma: Sigma): FilterHandle {
  // collect type buckets
  const counts = new Map<string, number>();
  graph.forEachNode((_id, attrs) => {
    const k = (attrs.kind as string) || 'unknown';
    counts.set(k, (counts.get(k) ?? 0) + 1);
  });

  const types = Array.from(counts.keys()).sort();
  const enabled = new Map<string, boolean>(types.map((t) => [t, true]));

  const root = document.createElement('div');
  root.className = 'filter-panel';
  root.innerHTML = `
    <div class="filter-toggle">
      <span>filter · types</span>
      <span class="caret">▾</span>
    </div>
    <div class="filter-body">
      ${types
        .map(
          (t) => `
        <label class="filter-row">
          <input type="checkbox" data-type="${t}" checked />
          <span>${t}</span>
          <span class="count">${counts.get(t)}</span>
        </label>`,
        )
        .join('')}
    </div>
  `;
  host.appendChild(root);

  const toggle = root.querySelector<HTMLElement>('.filter-toggle')!;
  const body = root.querySelector<HTMLElement>('.filter-body')!;
  const caret = root.querySelector<HTMLElement>('.caret')!;

  toggle.addEventListener('click', () => {
    body.classList.toggle('collapsed');
    caret.textContent = body.classList.contains('collapsed') ? '▸' : '▾';
  });

  function apply() {
    graph.forEachNode((id, attrs) => {
      const k = (attrs.kind as string) || 'unknown';
      const visible = enabled.get(k) !== false;
      graph.setNodeAttribute(id, 'hidden', !visible);
    });
    graph.forEachEdge((id, _attrs, _s, _t, sAttrs, tAttrs) => {
      const sHidden = sAttrs.hidden === true;
      const tHidden = tAttrs.hidden === true;
      graph.setEdgeAttribute(id, 'hidden', sHidden || tHidden);
    });
    sigma.refresh();
  }

  body.querySelectorAll<HTMLInputElement>('input[type="checkbox"]').forEach((cb) => {
    cb.addEventListener('change', () => {
      enabled.set(cb.dataset.type!, cb.checked);
      apply();
    });
  });

  return { refresh: apply };
}
