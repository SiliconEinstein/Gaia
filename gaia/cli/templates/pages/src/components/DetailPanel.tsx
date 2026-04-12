import type { GraphNode, GraphEdge } from '../types'
import { isKnowledgeNode, isStrategyNode, isOperatorNode } from '../types'
import styles from './DetailPanel.module.css'

interface Props {
  node: GraphNode | null
  edges: GraphEdge[]
  nodesById: Record<string, GraphNode>
  onClose: () => void
}

function formatProb(v: number | null | undefined): string {
  return v != null ? v.toFixed(2) : '\u2014'
}

export default function DetailPanel({ node, edges, nodesById, onClose }: Props) {
  const incomingEdges = node ? edges.filter(e => e.target === node.id) : []
  const outgoingEdges = node ? edges.filter(e => e.source === node.id) : []

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
                <p>{node.content}</p>
              </div>
            </>
          )}

          {isStrategyNode(node) && (
            <div className={styles.content}>
              <p><strong>Strategy:</strong> {node.strategy_type}</p>
              {node.reason && <p>{node.reason}</p>}
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
