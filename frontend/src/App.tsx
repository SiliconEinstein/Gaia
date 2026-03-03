import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AppShell } from "./components/layout/AppShell";
import { DashboardHome } from "./pages/DashboardHome";
import { GraphExplorer } from "./pages/GraphExplorer";
import { DataBrowser } from "./pages/DataBrowser";
import { NodePage } from "./pages/NodePage";
import { EdgePage } from "./pages/EdgePage";
import { CommitPanel } from "./pages/CommitPanel";

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
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
