import { useEffect, useState } from "react";
import { Card, Col, Row, Statistic, Spin } from "antd";
import { api } from "../api";
import type { Stats } from "../api";

export default function StatsPage() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.stats().then(setStats).finally(() => setLoading(false));
  }, []);

  if (loading) return <Spin size="large" />;
  if (!stats) return <div>Failed to load stats</div>;

  const groups = [
    {
      title: "Local Layer",
      items: [
        { label: "Variable Nodes", key: "local_variable_nodes" },
        { label: "Factor Nodes", key: "local_factor_nodes" },
      ],
    },
    {
      title: "Global Layer",
      items: [
        { label: "Variable Nodes", key: "global_variable_nodes" },
        { label: "Factor Nodes", key: "global_factor_nodes" },
      ],
    },
    {
      title: "Bindings & Params",
      items: [
        { label: "Canonical Bindings", key: "canonical_bindings" },
        { label: "Prior Records", key: "prior_records" },
        { label: "Factor Params", key: "factor_param_records" },
        { label: "Param Sources", key: "param_sources" },
      ],
    },
  ];

  return (
    <>
      {groups.map((group) => (
        <div key={group.title} style={{ marginBottom: 24 }}>
          <h3>{group.title}</h3>
          <Row gutter={16}>
            {group.items.map((item) => (
              <Col span={6} key={item.key}>
                <Card>
                  <Statistic title={item.label} value={stats[item.key] ?? 0} />
                </Card>
              </Col>
            ))}
          </Row>
        </div>
      ))}
    </>
  );
}
