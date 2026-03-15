// frontend/src/pages/v2/PackageDetail.tsx
import { Breadcrumb, Card, Descriptions, List, Tag, Typography, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { usePackage, useModules } from "../../api/v2";

export function PackageDetail() {
  const { id } = useParams<{ id: string }>();
  const pkgId = decodeURIComponent(id ?? "");
  const { data: pkg, isLoading: pkgLoading } = usePackage(pkgId);
  const { data: modules, isLoading: modLoading } = useModules(pkgId);

  if (pkgLoading) return <Spin />;
  if (!pkg) return <Typography.Text type="danger">Package not found</Typography.Text>;

  return (
    <div>
      <Breadcrumb
        style={{ marginBottom: 16 }}
        items={[
          { title: <Link to="/v2/packages">Packages</Link> },
          { title: pkg.package_id },
        ]}
      />
      <Typography.Title level={3}>{pkg.name}</Typography.Title>
      <Card style={{ marginBottom: 16 }}>
        <Descriptions bordered column={2}>
          <Descriptions.Item label="Package ID">{pkg.package_id}</Descriptions.Item>
          <Descriptions.Item label="Version">{pkg.version}</Descriptions.Item>
          <Descriptions.Item label="Status">
            <Tag color={pkg.status === "merged" ? "green" : "orange"}>{pkg.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="Submitter">{pkg.submitter}</Descriptions.Item>
          <Descriptions.Item label="Submitted At">{pkg.submitted_at}</Descriptions.Item>
          <Descriptions.Item label="Description" span={2}>{pkg.description}</Descriptions.Item>
        </Descriptions>
      </Card>
      <Card title={`Modules (${modules?.length ?? 0})`} loading={modLoading}>
        <List
          dataSource={modules ?? []}
          renderItem={(m) => (
            <List.Item>
              <Link to={`/v2/modules/${encodeURIComponent(m.module_id)}`}>{m.module_id}</Link>
              <Tag style={{ marginLeft: 8 }}>{m.role}</Tag>
              <span style={{ marginLeft: 8, color: "#888" }}>
                {m.chain_ids.length} chains · {m.export_ids.length} exports
              </span>
            </List.Item>
          )}
        />
      </Card>
    </div>
  );
}
