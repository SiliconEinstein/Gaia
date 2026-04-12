import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

vi.mock('elkjs/lib/elk.bundled.js', () => ({
  default: class {
    layout(graph: { children?: { id: string; width: number; height: number }[] }) {
      return Promise.resolve({
        ...graph,
        width: 800,
        height: 600,
        children: (graph.children ?? []).map((c, i) => ({
          ...c,
          x: i * 150,
          y: i * 80,
        })),
        edges: [],
      })
    }
  },
}))

import App from '../App'

const mockGraph = {
  modules: [{ id: 'm1', order: 0, node_count: 1, strategy_count: 0 }],
  cross_module_edges: [],
  nodes: [
    { id: 'a', label: 'A', type: 'claim', module: 'm1', content: 'Test',
      exported: false, metadata: {}, prior: null, belief: null },
  ],
  edges: [],
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

  it('shows error on fetch failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })),
    )
    render(<App />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })
})
