import type Graph from 'graphology';
import type Sigma from 'sigma';

/**
 * Minimal DIY minimap: paints node positions onto a canvas; draws a viewport
 * rectangle indicating the camera frame; clicking pans the main camera.
 *
 * Not a high-fidelity renderer — node colors are sampled from the graph attrs;
 * it refreshes on camera state and on a periodic timer (cheap because the
 * vertex count we draw is bounded).
 */
export interface MinimapHandle {
  destroy(): void;
}

export function mountMinimap(host: HTMLElement, graph: Graph, sigma: Sigma): MinimapHandle {
  // Find the canvas size
  const W = host.clientWidth || 180;
  const H = host.clientHeight || 130;

  const canvas = document.createElement('canvas');
  canvas.width = W * window.devicePixelRatio;
  canvas.height = H * window.devicePixelRatio;
  canvas.style.width = `${W}px`;
  canvas.style.height = `${H}px`;
  host.appendChild(canvas);

  const viewportEl = document.createElement('div');
  viewportEl.className = 'viewport';
  host.appendChild(viewportEl);

  const ctx = canvas.getContext('2d')!;
  ctx.scale(window.devicePixelRatio, window.devicePixelRatio);

  // compute graph bounding box once (positions stabilize after layout)
  let bbox = { minX: -100, maxX: 100, minY: -100, maxY: 100 };
  function recomputeBbox() {
    let minX = Infinity, maxX = -Infinity, minY = Infinity, maxY = -Infinity;
    graph.forEachNode((_id, attrs) => {
      const x = attrs.x as number;
      const y = attrs.y as number;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
    });
    if (!Number.isFinite(minX)) return;
    const padX = (maxX - minX) * 0.05 || 10;
    const padY = (maxY - minY) * 0.05 || 10;
    bbox = { minX: minX - padX, maxX: maxX + padX, minY: minY - padY, maxY: maxY + padY };
  }

  function project(x: number, y: number): [number, number] {
    const fx = (x - bbox.minX) / (bbox.maxX - bbox.minX || 1);
    const fy = (y - bbox.minY) / (bbox.maxY - bbox.minY || 1);
    return [fx * W, fy * H];
  }

  function paint() {
    ctx.clearRect(0, 0, W, H);
    ctx.fillStyle = 'rgba(255,255,255,0.05)';
    ctx.fillRect(0, 0, W, H);

    graph.forEachNode((_id, attrs) => {
      if (attrs.hidden) return;
      const [px, py] = project(attrs.x as number, attrs.y as number);
      ctx.fillStyle = (attrs.color as string) || '#888';
      ctx.fillRect(px - 1, py - 1, 2, 2);
    });
  }

  function paintViewport() {
    // Map the four screen corners back to graph space, then onto minimap.
    const containerRect = sigma.getContainer().getBoundingClientRect();
    const tl = sigma.viewportToGraph({ x: 0, y: 0 });
    const br = sigma.viewportToGraph({ x: containerRect.width, y: containerRect.height });
    const [x1, y1] = project(tl.x, tl.y);
    const [x2, y2] = project(br.x, br.y);
    const left = Math.max(0, Math.min(x1, x2));
    const top = Math.max(0, Math.min(y1, y2));
    const width = Math.min(W, Math.abs(x2 - x1));
    const height = Math.min(H, Math.abs(y2 - y1));
    viewportEl.style.left = `${left}px`;
    viewportEl.style.top = `${top}px`;
    viewportEl.style.width = `${width}px`;
    viewportEl.style.height = `${height}px`;
  }

  function refresh() {
    recomputeBbox();
    paint();
    paintViewport();
  }

  // Click to pan
  canvas.addEventListener('click', (e) => {
    const rect = canvas.getBoundingClientRect();
    const fx = (e.clientX - rect.left) / rect.width;
    const fy = (e.clientY - rect.top) / rect.height;
    const gx = bbox.minX + fx * (bbox.maxX - bbox.minX);
    const gy = bbox.minY + fy * (bbox.maxY - bbox.minY);
    const camera = sigma.getCamera();
    const containerRect = sigma.getContainer().getBoundingClientRect();
    const vp = sigma.graphToViewport({ x: gx, y: gy });
    const cx = containerRect.width / 2;
    const cy = containerRect.height / 2;
    const state = camera.getState();
    const dx = (vp.x - cx) / containerRect.width;
    const dy = (vp.y - cy) / containerRect.height;
    camera.animate({ x: state.x + dx, y: state.y + dy }, { duration: 250 });
  });

  // Sync with camera changes
  const camera = sigma.getCamera();
  const cameraSub = () => paintViewport();
  camera.on('updated', cameraSub);

  // Periodic refresh while layout runs
  const interval = window.setInterval(refresh, 800);

  // initial
  refresh();

  return {
    destroy() {
      window.clearInterval(interval);
      camera.off('updated', cameraSub);
      host.innerHTML = '';
    },
  };
}
