import type { GraphNode, GraphEdge } from '../types'
import styles from './ClaimDetail.module.css'

interface Props {
  node: GraphNode | null
  edges: GraphEdge[]
  nodesById: Record<string, GraphNode>
  onClose: () => void
}

function formatProb(v: number | null | undefined): string {
  return v != null ? v.toFixed(2) : '\u2014'
}

export default function ClaimDetail({ node, edges, nodesById, onClose }: Props) {
  const incomingEdges = node ? edges.filter((e) => e.target === node.id) : []

  return (
    <div className={`${styles.panel} ${node ? '' : styles.hidden}`}>
      {node && (
        <>
          <button className={styles.closeBtn} onClick={onClose} aria-label="close">
            &times;
          </button>

          <div className={styles.header}>
            <h2>{node.label}</h2>
            <span className={styles.badge}>{node.type}</span>
            {node.exported && <span className={styles.exported}>{'\u2605'}</span>}
          </div>

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

          {incomingEdges.length > 0 && (
            <div className={styles.reasoning}>
              <h3>Reasoning Chain</h3>
              {incomingEdges.map((edge, i) => {
                const premiseNode = nodesById[edge.source]
                return (
                  <div key={i} className={styles.chainItem}>
                    <span className={styles.strategyType}>
                      {edge.strategy_type ?? edge.type}
                    </span>
                    {' from '}
                    <span>{premiseNode?.label ?? edge.source}</span>
                  </div>
                )
              })}
            </div>
          )}

          {typeof node.metadata.figure === 'string' && (
            <div className={styles.figure}>
              <img src={node.metadata.figure} alt={`${node.label} figure`} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
