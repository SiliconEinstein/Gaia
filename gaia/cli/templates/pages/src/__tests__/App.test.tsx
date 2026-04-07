import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

// Mock cytoscape (no canvas in jsdom)
vi.mock('cytoscape', () => ({
  default: Object.assign(
    vi.fn(() => ({
      on: vi.fn(),
      layout: () => ({ run: vi.fn() }),
      fit: vi.fn(),
      destroy: vi.fn(),
      nodes: () => ({ length: 0 }),
    })),
    { use: vi.fn() },
  ),
}))
vi.mock('cytoscape-dagre', () => ({ default: vi.fn() }))

import App from '../App'

const mockGraph = {
  nodes: [
    { id: 'a', label: 'A', type: 'claim', content: 'Test', exported: false, metadata: {} },
  ],
  edges: [],
}
const mockMeta = { package_name: 'test-pkg', namespace: 'github' }
const mockBeliefs = { beliefs: [] }

beforeEach(() => {
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      let data: unknown = {}
      if (url.includes('graph.json')) data = mockGraph
      if (url.includes('meta.json')) data = mockMeta
      if (url.includes('beliefs.json')) data = mockBeliefs
      return Promise.resolve({ ok: true, json: () => Promise.resolve(data) })
    }),
  )
})

describe('App', () => {
  it('shows loading then title', async () => {
    render(<App />)
    expect(screen.getByText(/loading/i)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
  })

  it('renders graph and language switch when ready', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
    expect(screen.getByTestId('cy-container')).toBeInTheDocument()
    expect(screen.getByText('EN')).toBeInTheDocument()
  })

  it('shows error on fetch failure', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) })),
    )
    render(<App />)
    await waitFor(() => expect(screen.getByRole('alert')).toBeInTheDocument())
  })

  it('uses app-layout CSS grid container', async () => {
    const { container } = render(<App />)
    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
    const layout = container.querySelector('.app-layout')
    expect(layout).toBeInTheDocument()
  })
})
