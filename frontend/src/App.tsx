import { Layout, Menu } from "antd";
import {
  DatabaseOutlined,
  NodeIndexOutlined,
  LinkOutlined,
  DashboardOutlined,
} from "@ant-design/icons";
import { Routes, Route, useNavigate, useLocation } from "react-router-dom";
import StatsPage from "./pages/StatsPage";
import VariablesPage from "./pages/VariablesPage";
import VariableDetailPage from "./pages/VariableDetailPage";
import FactorsPage from "./pages/FactorsPage";
import FactorDetailPage from "./pages/FactorDetailPage";
import BindingsPage from "./pages/BindingsPage";

const { Header, Content, Sider } = Layout;

const menuItems = [
  { key: "/", icon: <DashboardOutlined />, label: "Stats" },
  { key: "/variables", icon: <DatabaseOutlined />, label: "Variables" },
  { key: "/factors", icon: <NodeIndexOutlined />, label: "Factors" },
  { key: "/bindings", icon: <LinkOutlined />, label: "Bindings" },
];

export default function App() {
  const navigate = useNavigate();
  const location = useLocation();

  const selectedKey =
    menuItems
      .filter((m) => location.pathname.startsWith(m.key) && m.key !== "/")
      .sort((a, b) => b.key.length - a.key.length)[0]?.key || "/";

  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Sider width={200} theme="light">
        <div
          style={{
            padding: "16px",
            fontWeight: "bold",
            fontSize: 18,
            textAlign: "center",
          }}
        >
          Gaia LKM
        </div>
        <Menu
          mode="inline"
          selectedKeys={[selectedKey]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <Layout>
        <Header
          style={{
            background: "#fff",
            padding: "0 24px",
            borderBottom: "1px solid #f0f0f0",
          }}
        >
          <h2 style={{ margin: 0, lineHeight: "64px" }}>
            LKM Storage Browser
          </h2>
        </Header>
        <Content style={{ margin: "24px", minHeight: 280 }}>
          <Routes>
            <Route path="/" element={<StatsPage />} />
            <Route path="/variables" element={<VariablesPage />} />
            <Route path="/variables/:id" element={<VariableDetailPage />} />
            <Route path="/factors" element={<FactorsPage />} />
            <Route path="/factors/:id" element={<FactorDetailPage />} />
            <Route path="/bindings" element={<BindingsPage />} />
          </Routes>
        </Content>
      </Layout>
    </Layout>
  );
}
