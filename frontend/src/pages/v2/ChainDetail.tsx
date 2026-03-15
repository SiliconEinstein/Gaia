// frontend/src/pages/v2/ChainDetail.tsx
import { Breadcrumb, Card, List, Table, Tag, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { useChain, useChainProbabilities } from "../../api/v2";
import type { ChainStep, V2ProbabilityRecord } from "../../api/v2-types";

export function ChainDetail() {
  const { id } = useParams<{ id: string }>();
  const chainId = decodeURIComponent(id ?? "");
  const { data: chain, isLoading } = useChain(chainId);
  const { data: probs } = useChainProbabilities(chainId);

  if (isLoading) return <Spin />;
  if (!chain) return <Typography.Text type="danger">Chain not found</Typography.Text>;

  const probColumns = [
    { title: "Step", dataIndex: "step_index", width: 60 },
    { title: "Value", dataIndex: "value", render: (v: number) => v.toFixed(4) },
    { title: "Source", dataIndex: "source" },
    { title: "Recorded At", dataIndex: "recorded_at" },
  ];

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to={`/v2/modules/${encodeURIComponent(chain.module_id)}`}>{chain.module_id}</Link> },
          { title: "Chain" },
        ]}
      />
      <Typography.Title level={3}>
        <Tag>{chain.type}</Tag> {chain.chain_id}
      </Typography.Title>
      <List
        header={<Typography.Text strong>Steps ({chain.steps.length})</Typography.Text>}
        dataSource={chain.steps}
        renderItem={(step: ChainStep) => (
          <List.Item>
            <Card style={{ width: "100%" }} size="small" title={`Step ${step.step_index}`}>
              <Typography.Text type="secondary">Premises:</Typography.Text>
              <List
                size="small"
                dataSource={step.premises}
                renderItem={(p) => (
                  <List.Item>
                    <Link to={`/v2/knowledge/${encodeURIComponent(p.knowledge_id)}`}>
                      {p.knowledge_id}@{p.version}
                    </Link>
                  </List.Item>
                )}
              />
              {step.reasoning && (
                <Typography.Paragraph style={{ marginTop: 8 }}>
                  <Typography.Text type="secondary">Reasoning: </Typography.Text>
                  {step.reasoning}
                </Typography.Paragraph>
              )}
              <Typography.Text type="secondary">Conclusion: </Typography.Text>
              <Link to={`/v2/knowledge/${encodeURIComponent(step.conclusion.knowledge_id)}`}>
                {step.conclusion.knowledge_id}@{step.conclusion.version}
              </Link>
            </Card>
          </List.Item>
        )}
      />
      {probs && probs.length > 0 && (
        <Card title="Probabilities" style={{ marginTop: 16 }}>
          <Table<V2ProbabilityRecord>
            rowKey={(r) => `${r.step_index}-${r.source}`}
            columns={probColumns}
            dataSource={probs}
            pagination={false}
          />
        </Card>
      )}
    </div>
  );
}
