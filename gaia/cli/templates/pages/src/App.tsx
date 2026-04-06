import { useEffect, useState } from 'react'
import type { GraphData, MetaData } from './types'

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

  const { graph, meta, beliefs } = state

  return (
    <div className="app-layout">
      <div className="app-header">
        <h1>{meta.package_name}</h1>
        <div data-testid="language-switch">
          {/* LanguageSwitch placeholder */}
        </div>
      </div>

      <div className="graph-panel" data-testid="graph-panel">
        {/* KnowledgeGraph placeholder */}
      </div>

      <div className="detail-panel" data-testid="detail-panel">
        {/* ClaimDetail placeholder */}
      </div>

      <div className="section-panel" data-testid="section-panel">
        {/* SectionView placeholder */}
      </div>

      {/* Expose state setters for future child components */}
      <span hidden data-selected={selectedNodeId} data-lang={lang}
        data-node-count={graph.nodes.length}
        data-edge-count={graph.edges.length}
        data-beliefs={JSON.stringify(beliefs)}
        data-set-node={String(setSelectedNodeId)}
        data-set-lang={String(setLang)}
      />
    </div>
  )
}
