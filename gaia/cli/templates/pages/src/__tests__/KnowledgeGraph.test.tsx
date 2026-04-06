import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'

// Mock cytoscape before importing the component
vi.mock('cytoscape', () => ({
  default: Object.assign(
    vi.fn(() => ({
      on: vi.fn(),
      layout: () => ({ run: vi.fn() }),
      destroy: vi.fn(),
      fit: vi.fn(),
    })),
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
})
