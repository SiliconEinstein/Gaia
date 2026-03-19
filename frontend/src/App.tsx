import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./components/layout/AppShell";
import { DashboardHome } from "./pages/DashboardHome";
import { GraphExplorer } from "./pages/GraphExplorer";
import { DataBrowser } from "./pages/DataBrowser";
import { NodePage } from "./pages/NodePage";
import { EdgePage } from "./pages/EdgePage";
import { CommitPanel } from "./pages/CommitPanel";
import { PaperViewer } from "./pages/PaperViewer";
import { PackageList } from "./pages/v2/PackageList";
import { KnowledgeList } from "./pages/v2/KnowledgeList";
import { PackageDetail } from "./pages/v2/PackageDetail";
import { ModuleDetail } from "./pages/v2/ModuleDetail";
import { KnowledgeDetail } from "./pages/v2/KnowledgeDetail";
import { ChainDetail } from "./pages/v2/ChainDetail";
import { GraphViewer } from "./pages/v2/GraphViewer";
import { GraphIRViewer } from "./pages/v2/GraphIRViewer";
import { GlobalGraphViewer } from "./pages/v2/GlobalGraphViewer";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<DashboardHome />} />
            <Route path="graph" element={<GraphExplorer />} />
            <Route path="browse/nodes" element={<DataBrowser />} />
            <Route path="browse/edges" element={<DataBrowser />} />
            <Route path="browse/contradictions" element={<DataBrowser />} />
            <Route path="nodes/:id" element={<NodePage />} />
            <Route path="edges/:id" element={<EdgePage />} />
            <Route path="commits" element={<CommitPanel />} />
            <Route path="papers" element={<PaperViewer />} />
            <Route path="v2/packages" element={<PackageList />} />
            <Route path="v2/packages/:id" element={<PackageDetail />} />
            <Route path="v2/knowledge" element={<KnowledgeList />} />
            <Route path="v2/knowledge/:id" element={<KnowledgeDetail />} />
            <Route path="v2/modules/:id" element={<ModuleDetail />} />
            <Route path="v2/chains/:id" element={<ChainDetail />} />
            <Route path="v2/graph" element={<GraphViewer />} />
            <Route path="v2/graph-ir" element={<GraphIRViewer />} />
            <Route path="v2/global-graph" element={<GlobalGraphViewer />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
