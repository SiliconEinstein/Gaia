import { Select, Space } from "antd";

const NODE_TYPES = [
  { label: "All Types", value: "" },
  { label: "paper-extract", value: "paper-extract" },
  { label: "join", value: "join" },
  { label: "deduction", value: "deduction" },
  { label: "conjecture", value: "conjecture" },
];

interface Props {
  selectedType: string;
  onTypeChange: (type: string) => void;
}

export function FilterBar({ selectedType, onTypeChange }: Props) {
  return (
    <Space style={{ marginBottom: 16 }}>
      <span>Type:</span>
      <Select
        value={selectedType}
        onChange={onTypeChange}
        options={NODE_TYPES}
        style={{ width: 160 }}
      />
    </Space>
  );
}
