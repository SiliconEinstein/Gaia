export interface GraphNode {
  id: string
  label: string
  title?: string
  type: 'claim' | 'setting' | 'question'
  module?: string
  content: string
  prior?: number | null
  belief?: number | null
  exported: boolean
  metadata: Record<string, unknown>
}

export interface GraphEdge {
  source: string
  target: string
  type: 'strategy' | 'operator'
  strategy_type?: string
  operator_type?: string
  reason?: string
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
}

export interface MetaData {
  package_name: string
  namespace: string
  description?: string
}
