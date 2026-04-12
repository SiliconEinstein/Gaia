import { useState, useCallback } from 'react'
import { useGraphData } from './hooks/useGraphData'
import ModuleOverview from './components/ModuleOverview'
import ModuleSubgraph from './components/ModuleSubgraph'
import LanguageSwitch from './components/LanguageSwitch'
import SectionView from './components/SectionView'

type ViewState =
  | { level: 'overview' }
  | { level: 'module'; moduleId: string; focusNodeId?: string }

export default function App() {
  const state = useGraphData()
  const [view, setView] = useState<ViewState>({ level: 'overview' })
  const [lang, setLang] = useState<'en' | 'zh'>('en')

  const sections = state.status === 'ready'
    ? state.graph.modules.map(m => m.id)
    : []

  const handleSelectModule = useCallback((moduleId: string) => {
    setView({ level: 'module', moduleId })
  }, [])

  const handleBack = useCallback(() => {
    setView({ level: 'overview' })
  }, [])

  const handleNavigateToModule = useCallback((moduleId: string, nodeId: string) => {
    setView({ level: 'module', moduleId, focusNodeId: nodeId })
  }, [])

  if (state.status === 'loading') {
    return <div style={{ padding: 40, textAlign: 'center' }}>Loading...</div>
  }

  if (state.status === 'error') {
    return <div role="alert" style={{ padding: 40, color: '#c00' }}>{state.message}</div>
  }

  const { graph, meta } = state

  return (
    <div className="app-layout">
      <div className="app-header">
        <h1>{meta.package_name}</h1>
        <LanguageSwitch lang={lang} onChange={setLang} />
      </div>

      <div className="graph-panel">
        {view.level === 'overview' ? (
          <ModuleOverview
            modules={graph.modules}
            crossModuleEdges={graph.cross_module_edges}
            onSelectModule={handleSelectModule}
          />
        ) : (
          <ModuleSubgraph
            moduleId={view.moduleId}
            allNodes={graph.nodes}
            allEdges={graph.edges}
            onBack={handleBack}
            onNavigateToModule={handleNavigateToModule}
          />
        )}
      </div>

      <div className="section-panel">
        <SectionView sections={sections} lang={lang} />
      </div>
    </div>
  )
}
