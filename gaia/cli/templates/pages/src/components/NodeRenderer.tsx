import type { GraphNode } from '../types'
import { isKnowledgeNode, isStrategyNode, isOperatorNode } from '../types'

interface Props {
  node: GraphNode
  x: number
  y: number
  width: number
  height: number
  highlighted: boolean | null
  onSelect: (id: string) => void
}

const BELIEF_COLORS = {
  high: '#4caf50',
  mid: '#ff9800',
  low: '#f44336',
  none: '#999',
} as const

function beliefColor(belief?: number | null): string {
  if (belief == null) return BELIEF_COLORS.none
  if (belief >= 0.7) return BELIEF_COLORS.high
  if (belief >= 0.4) return BELIEF_COLORS.mid
  return BELIEF_COLORS.low
}

const DETERMINISTIC = new Set(['deduction', 'reductio', 'elimination', 'mathematical_induction', 'case_analysis'])

const OP_SYMBOLS: Record<string, string> = {
  contradiction: '\u2297',
  equivalence: '\u2261',
  complement: '\u2295',
  disjunction: '\u2228',
  conjunction: '\u2227',
  implication: '\u2192',
}

function isNoteNodeType(type: string): boolean {
  return type === 'note' || type === 'setting' || type === 'context'
}

export default function NodeRenderer({ node, x, y, width, height, highlighted, onSelect }: Props) {
  const opacity = highlighted === false ? 0.2 : 1

  if (isKnowledgeNode(node)) {
    const isExternal = node.metadata?._external === true
    const fill = isExternal ? '#fff'
      : isNoteNodeType(node.type) ? '#f0f0f0'
      : node.type === 'question' ? '#fff3dd'
      : '#ddeeff'
    const stroke = isExternal ? '#aaa'
      : isNoteNodeType(node.type) ? '#999'
      : node.type === 'question' ? '#cc9944'
      : '#4488bb'
    const dashArray = isExternal ? '5,3' : undefined
    const rx = isExternal ? 8
      : isNoteNodeType(node.type) ? 2
      : node.type === 'question' ? height / 2
      : 8
    const label = node.title || node.label
    const truncated = label.length > 28 ? label.slice(0, 25) + '...' : label

    return (
      <g className="graph-node" opacity={opacity} cursor="pointer" onClick={() => onSelect(node.id)}>
        <rect x={x} y={y} width={width} height={height} rx={rx} ry={rx}
          fill={fill} stroke={stroke} strokeWidth={node.exported ? 3 : 1.5}
          strokeDasharray={dashArray} />
        <text x={x + width / 2} y={y + height / 2 + 1} textAnchor="middle"
          dominantBaseline="middle" fontSize={11} fill="#333">
          {truncated}
        </text>
        {node.belief != null && (
          <g>
            <circle cx={x + width - 6} cy={y + 6} r={8} fill={beliefColor(node.belief)} />
            <text x={x + width - 6} y={y + 6 + 1} textAnchor="middle"
              dominantBaseline="middle" fontSize={7} fill="#fff" fontWeight="bold">
              {node.belief.toFixed(1)}
            </text>
          </g>
        )}
        <title>{`${label}\nPrior: ${node.prior ?? '—'} → Belief: ${node.belief ?? '—'}`}</title>
      </g>
    )
  }

  if (isStrategyNode(node)) {
    const isDeterministic = DETERMINISTIC.has(node.strategy_type)
    const fill = isDeterministic ? '#e8f5e9' : '#fff9c4'
    const stroke = isDeterministic ? '#44bb44' : '#f9a825'
    const dashArray = isDeterministic ? undefined : '5,3'
    const cx = x + width / 2
    const cy = y + height / 2
    const inset = (width / 2) * 0.25
    const points = [
      `${x + inset},${y}`,
      `${x + width - inset},${y}`,
      `${x + width},${cy}`,
      `${x + width - inset},${y + height}`,
      `${x + inset},${y + height}`,
      `${x},${cy}`,
    ].join(' ')

    return (
      <g className="graph-node" opacity={opacity} cursor="pointer" onClick={() => onSelect(node.id)}>
        <polygon points={points} fill={fill} stroke={stroke} strokeWidth={1.5}
          strokeDasharray={dashArray} />
        <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={10} fill="#333">
          {node.strategy_type}
        </text>
        {node.reason && <title>{node.reason}</title>}
      </g>
    )
  }

  if (isOperatorNode(node)) {
    const cx = x + width / 2
    const cy = y + height / 2
    const r = Math.min(width, height) / 2
    const isContra = node.operator_type === 'contradiction'
    const symbol = OP_SYMBOLS[node.operator_type] ?? node.operator_type

    return (
      <g className="graph-node" opacity={opacity} cursor="pointer" onClick={() => onSelect(node.id)}>
        <circle cx={cx} cy={cy} r={r} fill={isContra ? '#ffebee' : '#fff'}
          stroke={isContra ? '#c62828' : '#999'} strokeWidth={1.5} />
        <text x={cx} y={cy + 1} textAnchor="middle" dominantBaseline="middle"
          fontSize={16} fill="#333">
          {symbol}
        </text>
      </g>
    )
  }

  return null
}
