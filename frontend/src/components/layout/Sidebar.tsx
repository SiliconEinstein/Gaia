import { Link, useLocation } from "react-router-dom";
import { Menu } from "antd";
import {
  HomeOutlined,
  DeploymentUnitOutlined,
  TableOutlined,
  WarningOutlined,
  BranchesOutlined,
  SendOutlined,
} from "@ant-design/icons";

const items = [
  { key: "/", icon: <HomeOutlined />, label: <Link to="/">Dashboard</Link> },
  {
    key: "/graph",
    icon: <DeploymentUnitOutlined />,
    label: <Link to="/graph">Graph Explorer</Link>,
  },
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
];

export function Sidebar() {
  const location = useLocation();
  return (
    <Menu
      mode="inline"
      selectedKeys={[location.pathname]}
      items={items}
      style={{ height: "100%", borderRight: 0 }}
    />
  );
}
