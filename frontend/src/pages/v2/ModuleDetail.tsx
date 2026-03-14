// frontend/src/pages/v2/ModuleDetail.tsx
import { Breadcrumb, Card, Descriptions, List, Tag, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { useModule, useModuleChains } from "../../api/v2";

export function ModuleDetail() {
  const { id } = useParams<{ id: string }>();
  const moduleId = decodeURIComponent(id ?? "");
  const { data: mod, isLoading: modLoading } = useModule(moduleId);
  const { data: chains, isLoading: chainsLoading } = useModuleChains(moduleId);

  if (modLoading) return <Spin />;
  if (!mod) return <Typography.Text type="danger">Module not found</Typography.Text>;

  const pkgId = mod.package_id;

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/v2/packages">Packages</Link> },
          { title: <Link to={`/v2/packages/${encodeURIComponent(pkgId)}`}>{pkgId}</Link> },
          { title: mod.name },
        ]}
      />
      <Typography.Title level={3}>{mod.module_id}</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Role">{mod.role}</Descriptions.Item>
          <Descriptions.Item label="Package">
            <Link to={`/v2/packages/${encodeURIComponent(pkgId)}`}>{pkgId}</Link>
          </Descriptions.Item>
          <Descriptions.Item label="Imports">{mod.imports.length}</Descriptions.Item>
          <Descriptions.Item label="Exports">{mod.export_ids.length}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title={`Chains (${chains?.length ?? 0})`} loading={chainsLoading}>
        <List
          dataSource={chains ?? []}
          renderItem={(c) => (
            <List.Item>
              <Link to={`/v2/chains/${encodeURIComponent(c.chain_id)}`}>{c.chain_id}</Link>
              <Tag style={{ marginLeft: 8 }}>{c.type}</Tag>
              <span style={{ marginLeft: 8, color: "#888" }}>{c.steps.length} steps</span>
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
