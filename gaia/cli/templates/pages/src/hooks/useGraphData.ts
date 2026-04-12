import { useState, useEffect } from 'react'
import type { GraphData, GraphNode, GraphEdge, MetaData } from '../types'

export interface ExternalRef {
  id: string
  label: string
  sourceModule: string
}

export function filterNodesByModule(nodes: GraphNode[], moduleId: string): GraphNode[] {
  return nodes.filter(n => 'module' in n && n.module === moduleId)
}

export function getExternalRefs(
  edges: GraphEdge[],
  moduleNodeIds: Set<string>,
  allNodes: GraphNode[],
): ExternalRef[] {
  const nodesById = new Map(allNodes.map(n => [n.id, n]))
  const externalIds = new Set<string>()
  const refs: ExternalRef[] = []

  for (const e of edges) {
    for (const endpoint of [e.source, e.target]) {
      if (!moduleNodeIds.has(endpoint) && !externalIds.has(endpoint)) {
        externalIds.add(endpoint)
        const node = nodesById.get(endpoint)
        if (node) {
          refs.push({
            id: node.id,
            label: 'label' in node ? node.label : node.id,
            sourceModule: ('module' in node && node.module) || '',
          })
        }
      }
    }
  }
  return refs
}

export function filterEdgesForModule(edges: GraphEdge[], nodeIds: Set<string>): GraphEdge[] {
  return edges.filter(e => nodeIds.has(e.source) || nodeIds.has(e.target))
}

export type LoadState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; graph: GraphData; meta: MetaData }

export function useGraphData(): LoadState {
  const [state, setState] = useState<LoadState>({ status: 'loading' })

  useEffect(() => {
    Promise.all([
      fetch('data/graph.json').then(r => {
        if (!r.ok) throw new Error(`graph.json: ${r.status}`)
        return r.json() as Promise<GraphData>
      }),
      fetch('data/meta.json').then(r => {
        if (!r.ok) throw new Error(`meta.json: ${r.status}`)
        return r.json() as Promise<MetaData>
      }),
    ])
      .then(([graph, meta]) => setState({ status: 'ready', graph, meta }))
      .catch((err: Error) => setState({ status: 'error', message: err.message }))
  }, [])

  return state
}
