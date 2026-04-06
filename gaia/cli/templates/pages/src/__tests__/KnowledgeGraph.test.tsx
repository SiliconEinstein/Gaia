import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import type { GraphEdge } from '../types'

let lastCyElements: unknown[] = []

// Mock cytoscape before importing the component
vi.mock('cytoscape', () => ({
  default: Object.assign(
    vi.fn((opts?: { elements?: unknown[] }) => {
      if (opts?.elements) lastCyElements = opts.elements
      return {
        on: vi.fn(),
        layout: () => ({ run: vi.fn() }),
        destroy: vi.fn(),
        fit: vi.fn(),
      }
    }),
    { use: vi.fn() },
  ),
}))
vi.mock('cytoscape-dagre', () => ({ default: vi.fn() }))

import KnowledgeGraph from '../components/KnowledgeGraph'

describe('KnowledgeGraph', () => {
  it('renders container', () => {
    render(<KnowledgeGraph nodes={[]} edges={[]} onSelectNode={() => {}} />)
    expect(screen.getByTestId('cy-container')).toBeInTheDocument()
  })

  it('styles abduction edges as dashed purple', () => {
    const nodes = [
      { id: 'h1', label: 'H1', type: 'claim' as const, content: '', exported: false, metadata: {} },
      { id: 'obs', label: 'Obs', type: 'claim' as const, content: '', exported: false, metadata: {} },
    ]
    const edges: GraphEdge[] = [
      { source: 'h1', target: 'obs', type: 'strategy', strategy_type: 'abduction' },
    ]
    render(<KnowledgeGraph nodes={nodes} edges={edges} onSelectNode={() => {}} />)

    // Find the edge element in cytoscape data
    const edgeEl = lastCyElements.find(
      (el: unknown) => (el as { data: { id: string } }).data.id === 'e0',
    ) as { data: { lineStyle: string; lineColor: string } }

    expect(edgeEl.data.lineStyle).toBe('dashed')
    expect(edgeEl.data.lineColor).toBe('#7c3aed')
  })

  it('styles contradiction operator edges as dashed red', () => {
    const nodes = [
      { id: 'a', label: 'A', type: 'claim' as const, content: '', exported: false, metadata: {} },
      { id: 'b', label: 'B', type: 'claim' as const, content: '', exported: false, metadata: {} },
    ]
    const edges: GraphEdge[] = [
      { source: 'a', target: 'b', type: 'operator', operator_type: 'contradiction' },
    ]
    render(<KnowledgeGraph nodes={nodes} edges={edges} onSelectNode={() => {}} />)

    const edgeEl = lastCyElements.find(
      (el: unknown) => (el as { data: { id: string } }).data.id === 'e0',
    ) as { data: { lineStyle: string; lineColor: string } }

    expect(edgeEl.data.lineStyle).toBe('dashed')
    expect(edgeEl.data.lineColor).toBe('#c00')
  })
})
