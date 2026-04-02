import { useEffect, useState } from "react";
import { Table, Spin, Tag } from "antd";
import { Link } from "react-router-dom";

interface Prior {
  variable_id: string;
  value: number;
  source_id: string;
  created_at: string;
  content: string | null;
}

interface ParamSource {
  source_id: string;
  source_class: string;
  model: string;
  policy: string | null;
  created_at: string;
}

const classColors: Record<string, string> = {
  official: "green",
  heuristic: "orange",
  provisional: "red",
};

export default function PriorsPage() {
  const [priors, setPriors] = useState<Prior[]>([]);
  const [sources, setSources] = useState<ParamSource[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch("/api/priors").then((r) => r.json()),
      fetch("/api/param-sources").then((r) => r.json()),
    ])
      .then(([p, s]) => {
        setPriors(p);
        setSources(s);
      })
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" />;

  const priorColumns = [
    {
      title: "Variable",
      dataIndex: "variable_id",
      key: "variable_id",
      width: 200,
      ellipsis: true,
      render: (id: string) => (
        <Link to={`/variables/${encodeURIComponent(id)}`}>
          <code>{id}</code>
        </Link>
      ),
    },
    {
      title: "Prior",
      dataIndex: "value",
      key: "value",
      width: 80,
      render: (v: number) => v.toFixed(3),
      sorter: (a: Prior, b: Prior) => a.value - b.value,
    },
    {
      title: "Content",
      dataIndex: "content",
      key: "content",
      ellipsis: true,
    },
    {
      title: "Source",
      dataIndex: "source_id",
      key: "source_id",
      width: 250,
      ellipsis: true,
    },
  ];

  const sourceColumns = [
    {
      title: "Source ID",
      dataIndex: "source_id",
      key: "source_id",
      ellipsis: true,
    },
    {
      title: "Class",
      dataIndex: "source_class",
      key: "source_class",
      width: 120,
      render: (c: string) => <Tag color={classColors[c]}>{c}</Tag>,
    },
    {
      title: "Model",
      dataIndex: "model",
      key: "model",
      width: 150,
    },
    {
      title: "Created",
      dataIndex: "created_at",
      key: "created_at",
      width: 200,
    },
  ];

  return (
    <>
      <h3>Prior Records ({priors.length})</h3>
      <Table
        dataSource={priors}
        columns={priorColumns}
        rowKey={(r) => `${r.variable_id}:${r.source_id}`}
        pagination={{ pageSize: 15 }}
        size="small"
        style={{ marginBottom: 32 }}
      />
      <h3>Parameterization Sources ({sources.length})</h3>
      <Table
        dataSource={sources}
        columns={sourceColumns}
        rowKey="source_id"
        pagination={false}
        size="small"
      />
    </>
  );
}
