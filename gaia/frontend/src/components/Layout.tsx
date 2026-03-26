import { Layout as AntLayout, Menu } from 'antd';
import {
  TableOutlined,
  BarChartOutlined,
  ShareAltOutlined,
} from '@ant-design/icons';
import { Outlet, useNavigate, useLocation } from 'react-router-dom';

const { Sider, Content, Header } = AntLayout;

const menuItems = [
  { key: '/tables', icon: <TableOutlined />, label: 'Table Browser' },
  { key: '/neo4j', icon: <BarChartOutlined />, label: 'Neo4j Stats' },
  { key: '/graph', icon: <ShareAltOutlined />, label: 'Graph Viewer' },
];

export default function Layout() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider breakpoint="lg" collapsedWidth={60}>
        <div
          style={{
            height: 48,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            color: '#fff',
            fontWeight: 700,
            fontSize: 18,
            letterSpacing: 2,
          }}
        >
          GAIA
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          onClick={({ key }) => navigate(key)}
        />
      </Sider>
      <AntLayout>
        <Header
          style={{
            background: '#fff',
            padding: '0 24px',
            borderBottom: '1px solid #f0f0f0',
            fontSize: 16,
            fontWeight: 600,
          }}
        >
          Gaia LKM Explorer
        </Header>
        <Content style={{ margin: 16, padding: 24, background: '#fff', borderRadius: 8 }}>
          <Outlet />
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
