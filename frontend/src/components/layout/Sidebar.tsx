import { Link, useLocation } from "react-router-dom";
import { Menu } from "antd";
import {
  HomeOutlined,
  TableOutlined,
  WarningOutlined,
  BranchesOutlined,
  SendOutlined,
  DatabaseOutlined,
} from "@ant-design/icons";

const items = [
  { key: "/", icon: <HomeOutlined />, label: <Link to="/">Dashboard</Link> },
  {
    key: "/browse/nodes",
    icon: <TableOutlined />,
    label: <Link to="/browse/nodes">Nodes</Link>,
  },
  {
    key: "/browse/edges",
    icon: <BranchesOutlined />,
    label: <Link to="/browse/edges">Edges</Link>,
  },
  {
    key: "/browse/contradictions",
    icon: <WarningOutlined />,
    label: <Link to="/browse/contradictions">Contradictions</Link>,
  },
  {
    key: "/commits",
    icon: <SendOutlined />,
    label: <Link to="/commits">Commits</Link>,
  },
  {
    key: "v2",
    icon: <DatabaseOutlined />,
    label: "V2",
    children: [
      {
        key: "/v2/packages",
        label: <Link to="/v2/packages">Packages</Link>,
      },
      {
        key: "/v2/knowledge",
        label: <Link to="/v2/knowledge">Knowledge</Link>,
      },
      {
        key: "/v2/graph",
        label: <Link to="/v2/graph">Graph</Link>,
      },
    ],
  },
];

export function Sidebar() {
  const location = useLocation();
  return (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      defaultOpenKeys={location.pathname.startsWith("/v2") ? ["v2"] : []}
      items={items}
      style={{ height: "100%", borderRight: 0 }}
    />
  );
}
