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

  it('shows abduction comparison with hypothesis vs alternative', () => {
    const hypothesis: GraphNode = {
      id: 'h1',
      label: 'Gravity Hypothesis',
      type: 'claim',
      content: 'Objects fall due to gravity.',
      prior: 0.7,
      belief: 0.82,
      exported: false,
      metadata: {},
    }
    const alternative: GraphNode = {
      id: 'h2',
      label: 'Impetus Hypothesis',
      type: 'claim',
      content: 'Objects fall due to impetus.',
      prior: 0.3,
      belief: 0.18,
      exported: false,
      metadata: {},
    }
    const conclusion: GraphNode = {
      id: 'obs1',
      label: 'Falling Observation',
      type: 'claim',
      content: 'Heavy and light objects hit the ground at the same time.',
      prior: 0.9,
      belief: 0.95,
      exported: true,
      metadata: {},
    }
    const abductionNodes: Record<string, GraphNode> = {
      h1: hypothesis,
      h2: alternative,
      obs1: conclusion,
    }
    const abductionEdges: GraphEdge[] = [
      { source: 'h1', target: 'obs1', type: 'strategy', strategy_type: 'abduction' },
      { source: 'h2', target: 'obs1', type: 'strategy', strategy_type: 'abduction' },
    ]

    render(
      <ClaimDetail
        node={hypothesis}
        edges={abductionEdges}
        nodesById={abductionNodes}
        onClose={() => {}}
      />,
    )

    expect(screen.getByText('Abduction Comparison')).toBeInTheDocument()
    expect(screen.getByText('Hypothesis:')).toBeInTheDocument()
    expect(screen.getByText('Alternative:')).toBeInTheDocument()
    expect(screen.getByText('vs')).toBeInTheDocument()
    // "Gravity Hypothesis" appears both in the header and in the comparison row
    expect(screen.getAllByText('Gravity Hypothesis')).toHaveLength(2)
    expect(screen.getByText('Impetus Hypothesis')).toBeInTheDocument()
  })
})
