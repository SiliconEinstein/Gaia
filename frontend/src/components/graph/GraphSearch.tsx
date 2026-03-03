import { useState, useCallback } from "react";
import { AutoComplete, Input } from "antd";
import { SearchOutlined } from "@ant-design/icons";
import { useTextSearch } from "../../hooks/useSearch";

interface Props {
  onSelectNode: (nodeId: number) => void;
}

export function GraphSearch({ onSelectNode }: Props) {
  const [query, setQuery] = useState("");
  const { data: results } = useTextSearch(query);

  const options = (results ?? []).slice(0, 10).map((r) => ({
    value: String(r.node.id),
    label: (
      <div style={{ display: "flex", justifyContent: "space-between" }}>
        <span>
          <strong>{r.node.id}</strong>{" "}
          {r.node.title ?? (typeof r.node.content === "string" ? r.node.content.slice(0, 50) : "...")}
        </span>
        <span style={{ color: "#999", fontSize: 11 }}>{r.score.toFixed(2)}</span>
      </div>
    ),
  }));

  const handleSelect = useCallback(
    (value: string) => {
      onSelectNode(Number(value));
      setQuery("");
    },
    [onSelectNode]
  );

  return (
    <AutoComplete
      options={options}
      onSelect={handleSelect}
      onSearch={setQuery}
      value={query}
      style={{ width: 320 }}
    >
      <Input
        prefix={<SearchOutlined />}
        placeholder="Search nodes by text..."
        allowClear
      />
    </AutoComplete>
  );
}
