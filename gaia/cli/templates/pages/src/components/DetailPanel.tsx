import type { GraphNode, GraphEdge } from '../types'
import { isKnowledgeNode, isStrategyNode, isOperatorNode } from '../types'
import styles from './DetailPanel.module.css'

interface Props {
  node: GraphNode | null
  edges: GraphEdge[]
  nodesById: Record<string, GraphNode>
  onClose: () => void
}

interface ParsedKnowledgeContent {
  body: string
  metadata: Array<{ label: string; value: string }>
}

function formatProb(v: number | null | undefined): string {
  return v != null ? v.toFixed(2) : '\u2014'
}

function formatValue(value: unknown): string {
  if (value == null) return '\u2014'
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return String(value)
    if (Number.isInteger(value)) return String(value)
    return Number(value.toPrecision(6)).toString()
  }
  if (typeof value === 'string') return value
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  return JSON.stringify(value)
}

function scoreSummary(node: GraphNode): string | null {
  if (!isStrategyNode(node)) return null
  const score = node.method?.score
  if (!score) return null
  const value = formatValue(score.value)
  return score.score_type ? `${score.score_type}=${value}` : value
}

function parseStructuredKnowledgeContent(content: string): ParsedKnowledgeContent | null {
  const lines = content
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)

  if (lines.length < 2) return null

  const knownLabels = new Map<string, string>([
    ['qid', 'QID'],
    ['type', 'Type'],
    ['role', 'Role'],
    ['content', 'Content'],
    ['source_ref', 'source_ref'],
  ])

  const metadata: Array<{ label: string; value: string }> = []
  let body: string | null = null

  for (const line of lines) {
    const match = line.match(/^([A-Za-z_]+):\s*(.*)$/)
    if (!match) return null

    const [, rawKey, rawValue] = match
    const key = rawKey.toLowerCase()
    const value = rawValue.trim()

    if (!value) return null

    if (key === 'content') {
      if (body != null) return null
      body = value
      continue
    }

    const label = knownLabels.get(key)
    if (!label) return null
    metadata.push({ label, value })
  }

  if (!body) return null

  return { body, metadata }
}

export default function DetailPanel({ node, edges, nodesById, onClose }: Props) {
  const incomingEdges = node ? edges.filter(e => e.target === node.id) : []
  const outgoingEdges = node ? edges.filter(e => e.source === node.id) : []
  const parsedKnowledgeContent = node && isKnowledgeNode(node)
    ? parseStructuredKnowledgeContent(node.content)
    : null

  return (
    <div className={`${styles.panel} ${node ? '' : styles.hidden}`}>
      {node && (
        <>
          <button className={styles.closeBtn} onClick={onClose} aria-label="close">
            &times;
          </button>

          <div className={styles.header}>
            <h2>{'label' in node ? node.label : node.id}</h2>
            <span className={styles.badge}>{node.type}</span>
            {isKnowledgeNode(node) && node.exported && (
              <span className={styles.exported}>{'\u2605'}</span>
            )}
          </div>

          {isKnowledgeNode(node) && (
            <>
              <div className={styles.probBar}>
                <span>Prior:</span>
                <span className={styles.probValue}>{formatProb(node.prior)}</span>
                <span>&rarr;</span>
                <span>Belief:</span>
                <span className={styles.probValue}>{formatProb(node.belief)}</span>
              </div>
              <div className={styles.content}>
                {parsedKnowledgeContent ? (
                  <>
                    <p className={styles.contentBody}>{parsedKnowledgeContent.body}</p>
                    <p className={styles.contentMeta}>
                      {parsedKnowledgeContent.metadata
                        .filter(m => m.label !== 'Content')
                        .map(m => `${m.label}: ${m.value}`)
                        .join(' · ')}
                    </p>
                  </>
                ) : (
                  <p>{node.content}</p>
                )}
              </div>
            </>
          )}

          {isStrategyNode(node) && (
            <div className={styles.content}>
              <p><strong>Strategy:</strong> {node.strategy_type}</p>
              {node.reason && <p>{node.reason}</p>}
            </div>
          )}

          {isStrategyNode(node) && node.method && (
            <div className={styles.method}>
              <h3>Method</h3>
              <dl className={styles.methodGrid}>
                <dt>kind</dt>
                <dd>{node.method.kind}</dd>
                {node.method.module_ref && (
                  <>
                    <dt>module</dt>
                    <dd>{node.method.module_ref}</dd>
                  </>
                )}
                {node.method.function_ref && (
                  <>
                    <dt>function</dt>
                    <dd>{node.method.function_ref}</dd>
                  </>
                )}
                {scoreSummary(node) && (
                  <>
                    <dt>score</dt>
                    <dd>{scoreSummary(node)}</dd>
                  </>
                )}
                {node.method.score?.query != null && (
                  <>
                    <dt>query</dt>
                    <dd>{formatValue(node.method.score.query)}</dd>
                  </>
                )}
                {node.method.score?.rationale && (
                  <>
                    <dt>rationale</dt>
                    <dd>{node.method.score.rationale}</dd>
                  </>
                )}
                {!node.method.score && node.method.score_ref && (
                  <>
                    <dt>score ref</dt>
                    <dd>{node.method.score_ref}</dd>
                  </>
                )}
              </dl>
            </div>
          )}

          {isOperatorNode(node) && (
            <div className={styles.content}>
              <p><strong>Operator:</strong> {node.operator_type}</p>
            </div>
          )}

          {incomingEdges.length > 0 && (
            <div className={styles.reasoning}>
              <h3>Incoming</h3>
              {incomingEdges.map((edge, i) => {
                const src = nodesById[edge.source]
                return (
                  <div key={i} className={styles.chainItem}>
                    <span className={styles.strategyType}>{edge.role}</span>
                    {' from '}
                    <span>{src && 'label' in src ? src.label : edge.source}</span>
                  </div>
                )
              })}
            </div>
          )}

          {outgoingEdges.length > 0 && (
            <div className={styles.reasoning}>
              <h3>Outgoing</h3>
              {outgoingEdges.map((edge, i) => {
                const tgt = nodesById[edge.target]
                return (
                  <div key={i} className={styles.chainItem}>
                    <span className={styles.strategyType}>{edge.role}</span>
                    {' to '}
                    <span>{tgt && 'label' in tgt ? tgt.label : edge.target}</span>
                  </div>
                )
              })}
            </div>
          )}

          {isKnowledgeNode(node) && typeof node.metadata.figure === 'string' && (
            <div className={styles.figure}>
              <img src={node.metadata.figure} alt={`${node.label} figure`} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
