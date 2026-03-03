import { InputNumber, Switch, Space, Button } from "antd";
import { ReloadOutlined } from "@ant-design/icons";

interface Props {
  nodeId: number | null;
  hops: number;
  physicsEnabled: boolean;
  onNodeIdChange: (id: number | null) => void;
  onHopsChange: (hops: number) => void;
  onPhysicsToggle: (enabled: boolean) => void;
  onReload: () => void;
  loading?: boolean;
}

export function GraphControls({
  nodeId,
  hops,
  physicsEnabled,
  onNodeIdChange,
  onHopsChange,
  onPhysicsToggle,
  onReload,
  loading,
}: Props) {
  return (
    <Space wrap style={{ marginBottom: 16 }}>
      <Space>
        <span>Node ID:</span>
        <InputNumber
          value={nodeId}
          onChange={(v) => onNodeIdChange(v)}
          placeholder="Enter node ID"
          min={0}
          style={{ width: 120 }}
        />
      </Space>
      <Space>
        <span>Hops:</span>
        <InputNumber
          value={hops}
          onChange={(v) => onHopsChange(v ?? 1)}
          min={1}
          max={5}
          style={{ width: 80 }}
        />
      </Space>
      <Space>
        <span>Physics:</span>
        <Switch checked={physicsEnabled} onChange={onPhysicsToggle} />
      </Space>
      <Button
        icon={<ReloadOutlined />}
        onClick={onReload}
        loading={loading}
        type="primary"
      >
        Load
      </Button>
    </Space>
  );
}
