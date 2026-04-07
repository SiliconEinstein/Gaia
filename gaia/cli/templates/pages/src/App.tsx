import { useEffect, useState, useMemo } from 'react'
import type { GraphData, GraphNode, MetaData } from './types'
import KnowledgeGraph from './components/KnowledgeGraph'
import ClaimDetail from './components/ClaimDetail'
import SectionView from './components/SectionView'
import LanguageSwitch from './components/LanguageSwitch'

type AppState =
  | { status: 'loading' }
  | { status: 'error'; message: string }
  | { status: 'ready'; graph: GraphData; meta: MetaData; beliefs: unknown }

export default function App() {
  const [state, setState] = useState<AppState>({ status: 'loading' })
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null)
  const [lang, setLang] = useState<'en' | 'zh'>('en')

  useEffect(() => {
    Promise.all([
      fetch('data/graph.json').then((r) => {
        if (!r.ok) throw new Error(`graph.json: ${r.status}`)
        return r.json() as Promise<GraphData>
      }),
      fetch('data/meta.json').then((r) => {
        if (!r.ok) throw new Error(`meta.json: ${r.status}`)
        return r.json() as Promise<MetaData>
      }),
      fetch('data/beliefs.json').then((r) => {
        if (!r.ok) throw new Error(`beliefs.json: ${r.status}`)
        return r.json() as Promise<unknown>
      }),
    ])
      .then(([graph, meta, beliefs]) => {
        setState({ status: 'ready', graph, meta, beliefs })
      })
      .catch((err: Error) => {
        setState({ status: 'error', message: err.message })
      })
  }, [])

  if (state.status === 'loading') {
    return <div>Loading...</div>
  }

  if (state.status === 'error') {
    return <div role="alert">{state.message}</div>
  }

  const { graph, meta } = state

  const nodesById = useMemo(() => {
    const map: Record<string, GraphNode> = {}
    for (const n of graph.nodes) {
      map[n.id] = n
    }
    return map
  }, [graph.nodes])

  const selectedNode = selectedNodeId ? nodesById[selectedNodeId] ?? null : null

  // Extract unique module names for sections
  const sections = useMemo(() => {
    const seen = new Set<string>()
    for (const n of graph.nodes) {
      if (n.module && !seen.has(n.module)) {
        seen.add(n.module)
      }
    }
    return Array.from(seen)
  }, [graph.nodes])

  return (
    <div className="app-layout">
      <div className="app-header">
        <h1>{meta.package_name}</h1>
        <LanguageSwitch lang={lang} onChange={setLang} />
      </div>

      <div className="graph-panel">
        <KnowledgeGraph
          nodes={graph.nodes}
          edges={graph.edges}
          onSelectNode={(id) => setSelectedNodeId(id)}
        />
      </div>

      <ClaimDetail
        node={selectedNode}
        edges={graph.edges}
        nodesById={nodesById}
        onClose={() => setSelectedNodeId(null)}
      />

      <div className="section-panel">
        <SectionView sections={sections} lang={lang} />
      </div>
    </div>
  )
}
