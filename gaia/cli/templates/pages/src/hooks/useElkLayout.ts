import { useState, useEffect } from 'react'
import ELK from 'elkjs/lib/elk.bundled.js'
import type { GraphNode, GraphEdge } from '../types'

const elk = new ELK()

export interface ElkNode {
  id: string
  x: number
  y: number
  width: number
  height: number
}

export interface ElkEdge {
  id: string
  source: string
  target: string
  sections?: Array<{
    startPoint: { x: number; y: number }
    bendPoints?: Array<{ x: number; y: number }>
    endPoint: { x: number; y: number }
  }>
}

export interface LayoutResult {
  nodes: ElkNode[]
  edges: ElkEdge[]
  width: number
  height: number
}

function nodeDimensions(node: GraphNode): { width: number; height: number } {
  if (node.type === 'strategy') return { width: 100, height: 40 }
  if (node.type === 'operator') return { width: 48, height: 48 }
  // KnowledgeNode: claim, setting, question, action
  const label = node.label
  const charWidth = 8
  const padding = 32
  return { width: Math.max(120, Math.min(label.length * charWidth + padding, 240)), height: 48 }
}

export function buildElkGraph(nodes: GraphNode[], edges: GraphEdge[]) {
  const nodeIds = new Set(nodes.map(n => n.id))
  return {
    id: 'root',
    layoutOptions: {
      'elk.algorithm': 'layered',
      'elk.direction': 'DOWN',
      'elk.spacing.nodeNode': '30',
      'elk.layered.spacing.nodeNodeBetweenLayers': '60',
      'elk.layered.crossingMinimization.strategy': 'LAYER_SWEEP',
    },
    children: nodes.map(n => {
      const dims = nodeDimensions(n)
      return { id: n.id, width: dims.width, height: dims.height }
    }),
    edges: edges
      .filter(e => nodeIds.has(e.source) && nodeIds.has(e.target))
      .map((e, i) => ({
        id: `e${i}`,
        sources: [e.source],
        targets: [e.target],
      })),
  }
}

export function useElkLayout(nodes: GraphNode[], edges: GraphEdge[]): LayoutResult | null {
  const [layout, setLayout] = useState<LayoutResult | null>(null)

  useEffect(() => {
    let isStale = false

    if (nodes.length === 0) {
      setLayout(null)
      return () => {
        isStale = true
      }
    }
    const graph = buildElkGraph(nodes, edges)
    elk.layout(graph)
      .then(result => {
        if (isStale) {
          return
        }
        const layoutNodes: ElkNode[] = (result.children ?? []).map(c => ({
          id: c.id, x: c.x ?? 0, y: c.y ?? 0, width: c.width ?? 100, height: c.height ?? 40,
        }))
        const layoutEdges: ElkEdge[] = (result.edges ?? []).map(e => ({
          id: e.id, source: (e.sources ?? [])[0] ?? '', target: (e.targets ?? [])[0] ?? '',
          sections: e.sections,
        }))
        setLayout({ nodes: layoutNodes, edges: layoutEdges, width: result.width ?? 800, height: result.height ?? 600 })
      })
      .catch(() => {
        if (isStale) {
          return
        }
        setLayout(null)
      })

    return () => {
      isStale = true
    }
  }, [nodes, edges])

  return layout
}
