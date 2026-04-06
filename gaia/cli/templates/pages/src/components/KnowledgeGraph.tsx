import { useEffect, useRef } from 'react'
import cytoscape from 'cytoscape'
import dagre from 'cytoscape-dagre'
import type { GraphNode, GraphEdge } from '../types'
import styles from './KnowledgeGraph.module.css'

// Register dagre layout
cytoscape.use(dagre)

interface Props {
  nodes: GraphNode[]
  edges: GraphEdge[]
  onSelectNode: (id: string) => void
}

function beliefColor(belief?: number | null): string {
  if (belief == null) return '#999'
  if (belief >= 0.7)
    return `rgb(${Math.round(40 + (1 - belief) * 200)}, ${Math.round(160 + belief * 40)}, 40)`
  if (belief >= 0.4)
    return `rgb(${Math.round(200 + (0.7 - belief) * 180)}, ${Math.round(180 - (0.7 - belief) * 80)}, 40)`
  return `rgb(200, ${Math.round(60 + belief * 200)}, 40)`
}

function edgeStyle(edge: GraphEdge): { lineStyle: string; lineColor: string } {
  if (edge.type === 'strategy') {
    // Abduction: dashed purple to highlight hypothesis-vs-alternative
    if (edge.strategy_type === 'abduction') {
      return { lineStyle: 'dashed', lineColor: '#7c3aed' }
    }
    const deterministic = ['deduction', 'analogy']
    const isDeterministic = edge.strategy_type != null && deterministic.includes(edge.strategy_type)
    return {
      lineStyle: isDeterministic ? 'solid' : 'dashed',
      lineColor: '#666',
    }
  }
  // operator edges
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

    const cyNodes = nodes.map((n) => ({
      data: {
        id: n.id,
        label: n.label,
        belief: n.belief,
        exported: n.exported,
        nodeType: n.type,
      },
    }))

    const cyEdges = edges.map((e, i) => {
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
            label: 'data(label)',
            'background-color': ((ele: cytoscape.NodeSingular) =>
              beliefColor(ele.data('belief'))) as unknown as string,
            'border-width': ((ele: cytoscape.NodeSingular) =>
              ele.data('exported') ? 4 : 1) as unknown as number,
            'border-color': '#333',
            color: '#222',
            'font-size': '12px',
            'text-valign': 'center',
            'text-halign': 'center',
            width: 60,
            height: 60,
            'text-wrap': 'wrap' as const,
            'text-max-width': '80px',
          } as cytoscape.Css.Node,
        },
        {
          selector: 'edge',
          style: {
            width: 2,
            'line-color': 'data(lineColor)',
            'target-arrow-color': 'data(lineColor)',
            'target-arrow-shape': 'triangle',
            'curve-style': 'bezier',
            'line-style': 'data(lineStyle)' as cytoscape.Css.LineStyle,
          } as cytoscape.Css.Edge,
        },
      ],
      layout: {
        name: 'dagre',
        rankDir: 'TB',
      } as cytoscape.LayoutOptions,
    })

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
