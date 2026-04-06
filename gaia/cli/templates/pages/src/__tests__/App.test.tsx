import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

  it('renders all placeholder panels when ready', async () => {
    render(<App />)
    await waitFor(() => expect(screen.getByText('test-pkg')).toBeInTheDocument())
    expect(screen.getByTestId('graph-panel')).toBeInTheDocument()
    expect(screen.getByTestId('detail-panel')).toBeInTheDocument()
    expect(screen.getByTestId('section-panel')).toBeInTheDocument()
    expect(screen.getByTestId('language-switch')).toBeInTheDocument()
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
