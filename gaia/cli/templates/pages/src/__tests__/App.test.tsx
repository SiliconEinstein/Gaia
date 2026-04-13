import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

vi.mock('elkjs/lib/elk.bundled.js', () => ({
  default: class {
    layout(graph: { children?: { id: string; width: number; height: number }[]; edges?: { id: string; sources: string[]; targets: string[] }[] }) {
      return Promise.resolve({
        ...graph,
        width: 800,
        height: 600,
        children: (graph.children ?? []).map((c, i) => ({
          ...c,
          x: i * 150,
          y: i * 80,
        })),
        edges: (graph.edges ?? []).map((edge: { id: string; sources: string[]; targets: string[] }, i: number) => ({
          id: edge.id,
          source: edge.sources[0],
          target: edge.targets[0],
          sections: [{
            startPoint: { x: i * 150 + 120, y: i * 80 + 24 },
            endPoint: { x: i * 150 + 240, y: i * 80 + 24 },
          }],
        })),
      })
    }
  },
}))

import App from '../App'

const mockGraph = {
  modules: [
    { id: 'm1', order: 0, node_count: 1, strategy_count: 0 },
    { id: 'm2', order: 1, node_count: 1, strategy_count: 0 },
  ],
  cross_module_edges: [{ from_module: 'm2', to_module: 'm1', count: 1 }],
  nodes: [
    { id: 'a', label: 'A', type: 'claim', module: 'm1', content: 'Test',
      exported: false, metadata: {}, prior: null, belief: null },
    { id: 'b', label: 'B', type: 'claim', module: 'm2', content: 'External node',
      exported: false, metadata: {}, prior: null, belief: null },
  ],
  edges: [{ source: 'b', target: 'a', role: 'premise' }],
}
const mockMeta = { package_name: 'test-pkg', namespace: 'github' }

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      let data: unknown = {}
      if (url.includes('graph.json')) data = mockGraph
      if (url.includes('meta.json')) data = mockMeta
      return Promise.resolve({
        ok: true,
        json: () => Promise.resolve(data),
        text: () => Promise.resolve(''),
      })
    }),
  )
})

describe('App', () => {
  it('shows loading then title', async () => {
    render(<App />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
  })

  it('renders module overview when ready', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
    await waitFor(() => expect(screen.getAllByText('m1').length).toBeGreaterThan(0))
  })

  it('renders grouped external node labels after navigating into a module view', async () => {
    render(<App />)

    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
    expect(screen.queryByText('↗ B')).not.toBeInTheDocument()

    const moduleLink = screen.getAllByText('m1').find(element => element.closest('svg'))
    expect(moduleLink).toBeTruthy()
    fireEvent.click(moduleLink!)

    await waitFor(() => expect(screen.getByText('↗ B')).toBeInTheDocument())
  })

  it('shows error on fetch failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })),
    )
    render(<App />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
