import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import Layout from './components/Layout';
import TableBrowser from './pages/TableBrowser';
import Neo4jStats from './pages/Neo4jStats';
import GraphViewer from './pages/GraphViewer';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/tables" element={<TableBrowser />} />
          <Route path="/neo4j" element={<Neo4jStats />} />
          <Route path="/graph" element={<GraphViewer />} />
          <Route path="*" element={<Navigate to="/tables" replace />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
