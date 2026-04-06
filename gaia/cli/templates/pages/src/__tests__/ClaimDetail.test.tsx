import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import ClaimDetail from '../components/ClaimDetail'
import type { GraphNode, GraphEdge } from '../types'

const sampleNode: GraphNode = {
  id: 'c1',
  label: 'Claim 1',
  type: 'claim',
  content: 'Bodies fall at the same rate regardless of mass.',
  prior: 0.5,
  belief: 0.85,
  exported: true,
  metadata: { figure: 'assets/fig1.png' },
}

const premiseNode: GraphNode = {
  id: 's1',
  label: 'Setting 1',
  type: 'setting',
  content: 'Vacuum conditions assumed.',
  prior: 0.9,
  belief: 0.9,
  exported: false,
  metadata: {},
}

const nodesById: Record<string, GraphNode> = {
  c1: sampleNode,
  s1: premiseNode,
}

const edges: GraphEdge[] = [
  {
    source: 's1',
    target: 'c1',
    type: 'strategy',
    strategy_type: 'deduction',
  },
]

describe('ClaimDetail', () => {
  it('is hidden when node is null', () => {
    const { container } = render(
      <ClaimDetail node={null} edges={[]} nodesById={{}} onClose={() => {}} />,
    )
    const panel = container.firstChild as HTMLElement
    expect(panel.className).toMatch(/hidden/)
  })

  it('shows claim content, prior, belief, and figure', () => {
    render(
      <ClaimDetail node={sampleNode} edges={edges} nodesById={nodesById} onClose={() => {}} />,
    )
    expect(screen.getByText(/Bodies fall at the same rate/)).toBeInTheDocument()
    expect(screen.getByText('0.85')).toBeInTheDocument()
    expect(screen.getByText('0.50')).toBeInTheDocument()
    const img = screen.getByRole('img') as HTMLImageElement
    expect(img.src).toContain('fig1.png')
  })

  it('shows reasoning chain with strategy type and premise label', () => {
    render(
      <ClaimDetail node={sampleNode} edges={edges} nodesById={nodesById} onClose={() => {}} />,
    )
    expect(screen.getByText(/deduction/)).toBeInTheDocument()
    expect(screen.getByText(/Setting 1/)).toBeInTheDocument()
  })

  it('calls onClose when close button clicked', () => {
    const onClose = vi.fn()
    render(
      <ClaimDetail node={sampleNode} edges={edges} nodesById={nodesById} onClose={onClose} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /close/i }))
    expect(onClose).toHaveBeenCalledOnce()
  })
})
