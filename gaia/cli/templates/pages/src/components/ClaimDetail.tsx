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

/**
 * Find abduction comparisons for the selected node.
 * If this node is a premise of an abduction edge, find sibling hypotheses
 * that target the same conclusion (i.e., competing explanations).
 */
function findAbductionComparisons(
  node: GraphNode,
  edges: GraphEdge[],
  nodesById: Record<string, GraphNode>,
): { hypothesis: GraphNode; alternative: GraphNode; conclusion: GraphNode }[] {
  // Find abduction edges where this node is a source (premise)
  const abductionEdges = edges.filter(
    (e) => e.source === node.id && e.strategy_type === 'abduction',
  )

  const comparisons: { hypothesis: GraphNode; alternative: GraphNode; conclusion: GraphNode }[] = []

  for (const edge of abductionEdges) {
    const conclusion = nodesById[edge.target]
    if (!conclusion) continue

    // Find other sources (siblings) targeting the same conclusion via abduction
    const siblings = edges.filter(
      (e) =>
        e.target === edge.target &&
        e.source !== node.id &&
        e.strategy_type === 'abduction',
    )

    for (const sib of siblings) {
      const alt = nodesById[sib.source]
      if (alt) {
        comparisons.push({ hypothesis: node, alternative: alt, conclusion })
      }
    }
  }

  return comparisons
}

export default function ClaimDetail({ node, edges, nodesById, onClose }: Props) {
  const incomingEdges = node ? edges.filter((e) => e.target === node.id) : []
  const abductionComparisons = node ? findAbductionComparisons(node, edges, nodesById) : []

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

          {abductionComparisons.length > 0 && (
            <div className={styles.abduction}>
              <h3>Abduction Comparison</h3>
              {abductionComparisons.map((comp, i) => (
                <div key={i} className={styles.abductionRow}>
                  <div className={styles.abductionHypothesis}>
                    <span className={styles.abductionLabel}>Hypothesis:</span>
                    <span>{comp.hypothesis.label}</span>
                    <span className={styles.probValue}>
                      ({formatProb(comp.hypothesis.belief)})
                    </span>
                  </div>
                  <span className={styles.abductionVs}>vs</span>
                  <div className={styles.abductionAlternative}>
                    <span className={styles.abductionLabel}>Alternative:</span>
                    <span>{comp.alternative.label}</span>
                    <span className={styles.probValue}>
                      ({formatProb(comp.alternative.belief)})
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}

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
