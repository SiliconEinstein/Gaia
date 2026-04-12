import { useMemo } from 'react'
import { useElkLayout } from '../hooks/useElkLayout'
import type { ModuleInfo, CrossModuleEdge, GraphNode, GraphEdge } from '../types'

interface Props {
  modules: ModuleInfo[]
  crossModuleEdges: CrossModuleEdge[]
  onSelectModule: (moduleId: string) => void
}

const MODULE_COLORS = [
  { fill: '#ddeeff', stroke: '#4488bb' },
  { fill: '#ddffdd', stroke: '#44bb44' },
  { fill: '#fff3dd', stroke: '#cc9944' },
  { fill: '#f3e8ff', stroke: '#7c3aed' },
  { fill: '#fce4ec', stroke: '#c62828' },
  { fill: '#e0f7fa', stroke: '#00838f' },
]

export default function ModuleOverview({ modules, crossModuleEdges, onSelectModule }: Props) {
  const { pseudoNodes, pseudoEdges } = useMemo(() => {
    const pNodes: GraphNode[] = modules.map(m => ({
      id: m.id,
      label: m.id,
      type: 'setting' as const,
      module: m.id,
      content: '',
      exported: false,
      metadata: {},
    }))
    const pEdges: GraphEdge[] = crossModuleEdges.map(e => ({
      source: e.from_module,
      target: e.to_module,
      role: 'premise' as const,
    }))
    return { pseudoNodes: pNodes, pseudoEdges: pEdges }
  }, [modules, crossModuleEdges])

  const layout = useElkLayout(pseudoNodes, pseudoEdges)

  if (!layout) return <div style={{ padding: 40, textAlign: 'center', color: '#888' }}>Computing layout...</div>

  const padding = 40

  return (
    <svg
      width="100%"
      height="100%"
      viewBox={`${-padding} ${-padding} ${layout.width + padding * 2} ${layout.height + padding * 2}`}
      style={{ maxHeight: '80vh' }}
    >
      {layout.edges.map(e => {
        const section = e.sections?.[0]
        if (!section) return null
        return (
          <g key={e.id}>
            <defs>
              <marker id={`mo-${e.id}`} viewBox="0 0 10 10" refX="9" refY="5"
                markerWidth="6" markerHeight="6" orient="auto">
                <path d="M 0 0 L 10 5 L 0 10 z" fill="#999" />
              </marker>
            </defs>
            <line
              x1={section.startPoint.x} y1={section.startPoint.y}
              x2={section.endPoint.x} y2={section.endPoint.y}
              stroke="#999" strokeWidth={2} markerEnd={`url(#mo-${e.id})`}
            />
          </g>
        )
      })}
      {layout.nodes.map((ln, i) => {
        const mod = modules.find(m => m.id === ln.id)
        if (!mod) return null
        const color = MODULE_COLORS[i % MODULE_COLORS.length]
        return (
          <g key={ln.id} cursor="pointer" onClick={() => onSelectModule(ln.id)}>
            <rect
              x={ln.x} y={ln.y} width={ln.width} height={ln.height}
              rx={8} ry={8} fill={color.fill} stroke={color.stroke} strokeWidth={2}
            />
            <text x={ln.x + ln.width / 2} y={ln.y + 20} textAnchor="middle"
              fontSize={13} fontWeight="bold" fill="#333">
              {mod.id}
            </text>
            <text x={ln.x + ln.width / 2} y={ln.y + 36} textAnchor="middle"
              fontSize={11} fill="#666">
              {mod.node_count} nodes, {mod.strategy_count} strategies
            </text>
          </g>
        )
      })}
    </svg>
  )
}
