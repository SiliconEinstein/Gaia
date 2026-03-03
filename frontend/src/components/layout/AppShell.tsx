import { Outlet } from "react-router-dom";
import { Layout, Typography } from "antd";
import { Sidebar } from "./Sidebar";

const { Header, Sider, Content } = Layout;

export function AppShell() {
  return (
    <Layout style={{ minHeight: "100vh" }}>
      <Header
        style={{
          display: "flex",
          alignItems: "center",
          padding: "0 24px",
          background: "#001529",
        }}
      >
        <Typography.Title level={4} style={{ color: "#fff", margin: 0 }}>
          Gaia Dashboard
        </Typography.Title>
      </Header>
      <Layout>
        <Sider width={200} style={{ background: "#fff" }}>
          <Sidebar />
        </Sider>
        <Content style={{ padding: 24, background: "#f0f2f5", minHeight: 280 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
