import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
import type { GraphNode, GraphEdge } from '../types'
import styles from './KnowledgeGraph.module.css'

// Register dagre layout (guard against double-registration in HMR)
try { cytoscape.use(dagre) } catch { /* already registered */ }

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onSelectNode: (id: string) => void
}

function beliefColor(belief?: number | null): string {
  if (belief == null) return '#999'
  if (belief >= 0.7) return '#4caf50'
  if (belief >= 0.4) return '#ff9800'
  return '#f44336'
}

function edgeStyle(edge: GraphEdge): { lineStyle: string; lineColor: string } {
  if (edge.type === 'strategy') {
    if (edge.strategy_type === 'abduction') {
      return { lineStyle: 'dashed', lineColor: '#7c3aed' }
    }
    const deterministic = ['deduction', 'analogy']
    const isDeterministic = edge.strategy_type != null && deterministic.includes(edge.strategy_type)
    return { lineStyle: isDeterministic ? 'solid' : 'dashed', lineColor: '#666' }
  }
  if (edge.operator_type === 'contradiction') {
    return { lineStyle: 'dashed', lineColor: '#c00' }
  }
  return { lineStyle: 'dashed', lineColor: '#999' }
}

export default function KnowledgeGraph({ nodes, edges, onSelectNode }: Props) {
  const containerRef = useRef<HTMLDivElement>(null)
  const cyRef = useRef<cytoscape.Core | null>(null)

  useEffect(() => {
    if (!containerRef.current) return

    const nodeIds = new Set(nodes.map((n) => n.id))

    const cyNodes = nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.title || n.label,
        bgColor: beliefColor(n.belief),
        borderWidth: n.exported ? 4 : 1,
      },
    }))

    const validEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target))
    const cyEdges = validEdges.map((e, i) => {
      const style = edgeStyle(e)
      return {
        data: {
          id: `e${i}`,
          source: e.source,
          target: e.target,
          lineStyle: style.lineStyle,
          lineColor: style.lineColor,
        },
      }
    })

    const cy = cytoscape({
      container: containerRef.current,
      elements: [...cyNodes, ...cyEdges],
      style: [
        {
          selector: 'node',
          style: {
            'label': 'data(label)',
            'background-color': 'data(bgColor)',
            'border-width': 'data(borderWidth)',
            'border-color': '#333',
            'color': '#222',
            'font-size': '11px',
            'text-valign': 'bottom',
            'text-halign': 'center',
            'text-margin-y': 4,
            'width': 40,
            'height': 40,
            'text-wrap': 'wrap',
            'text-max-width': '100px',
          },
        },
        {
          selector: 'edge',
          style: {
            'width': 2,
            'line-color': 'data(lineColor)',
            'target-arrow-color': 'data(lineColor)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'data(lineStyle)' as unknown as cytoscape.Css.LineStyle,
          },
        },
      ],
    })

    // Run dagre layout
    cy.layout({ name: 'dagre', rankDir: 'TB', nodeSep: 50, rankSep: 80 } as cytoscape.LayoutOptions).run()
    cy.fit(undefined, 20)

    cy.on('tap', 'node', (evt) => {
      const nodeId = evt.target.data('id') as string
      onSelectNode(nodeId)
    })

    cyRef.current = cy

    return () => {
      cy.destroy()
      cyRef.current = null
    }
  }, [nodes, edges, onSelectNode])

  return (
    <div ref={containerRef} className={styles.container} data-testid="cy-container" />
  )
}
