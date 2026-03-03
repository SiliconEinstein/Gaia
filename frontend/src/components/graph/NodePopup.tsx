import { Drawer, Descriptions, Tag, Typography, Divider } from "antd";
import type { Node, HyperEdge } from "../../api/types";
import { ContentRenderer } from "../shared/ContentRenderer";
import { ReasoningSteps } from "../shared/ReasoningSteps";
import { NODE_STYLES, FACTOR_STYLES } from "../../lib/node-styles";

const { Text } = Typography;

interface Props {
  node?: Node;
  edge?: HyperEdge;
  open: boolean;
  onClose: () => void;
}

function typeColor(type: string, isEdge: boolean): string {
  if (isEdge) return FACTOR_STYLES[type]?.color.border ?? "#6B7280";
  return NODE_STYLES[type]?.color.border ?? "#9CA3AF";
}

export function NodePopup({ node, edge, open, onClose }: Props) {
  return (
    <Drawer
      title={
        node
          ? `Node ${node.id}`
          : edge
            ? `HyperEdge ${edge.id}`
            : "Details"
      }
      open={open}
      onClose={onClose}
      width={480}
    >
      {node && <NodeDetail node={node} />}
      {edge && <EdgeDetail edge={edge} />}
    </Drawer>
  );
}

function NodeDetail({ node }: { node: Node }) {
  return (
    <>
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="ID">{node.id}</Descriptions.Item>
        <Descriptions.Item label="Type">
          <Tag color={typeColor(node.type, false)}>{node.type}</Tag>
        </Descriptions.Item>
        {node.subtype && (
          <Descriptions.Item label="Subtype">{node.subtype}</Descriptions.Item>
        )}
        {node.title && (
          <Descriptions.Item label="Title">{node.title}</Descriptions.Item>
        )}
        <Descriptions.Item label="Prior">{node.prior}</Descriptions.Item>
        <Descriptions.Item label="Belief">
          {node.belief !== null ? node.belief : <Text type="secondary">—</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="Status">
          <Tag color={node.status === "active" ? "green" : "red"}>
            {node.status}
          </Tag>
        </Descriptions.Item>
        {node.keywords.length > 0 && (
          <Descriptions.Item label="Keywords">
            {node.keywords.map((kw) => (
              <Tag key={kw}>{kw}</Tag>
            ))}
          </Descriptions.Item>
        )}
      </Descriptions>

      <Divider orientation="left">Content</Divider>
      <ContentRenderer content={node.content} />
    </>
  );
}

function EdgeDetail({ edge }: { edge: HyperEdge }) {
  return (
    <>
      <Descriptions column={1} size="small" bordered>
        <Descriptions.Item label="ID">{edge.id}</Descriptions.Item>
        <Descriptions.Item label="Type">
          <Tag color={typeColor(edge.type, true)}>{edge.type}</Tag>
        </Descriptions.Item>
        {edge.subtype && (
          <Descriptions.Item label="Subtype">{edge.subtype}</Descriptions.Item>
        )}
        <Descriptions.Item label="Tail">
          {edge.tail.map((id) => (
            <Tag key={id}>Node {id}</Tag>
          ))}
        </Descriptions.Item>
        <Descriptions.Item label="Head">
          {edge.head.map((id) => (
            <Tag key={id}>Node {id}</Tag>
          ))}
        </Descriptions.Item>
        <Descriptions.Item label="Probability">
          {edge.probability !== null ? edge.probability : <Text type="secondary">—</Text>}
        </Descriptions.Item>
        <Descriptions.Item label="Verified">
          <Tag color={edge.verified ? "green" : "default"}>
            {edge.verified ? "Yes" : "No"}
          </Tag>
        </Descriptions.Item>
      </Descriptions>

      <Divider orientation="left">Reasoning Steps</Divider>
      <ReasoningSteps steps={edge.reasoning} />
    </>
  );
}
