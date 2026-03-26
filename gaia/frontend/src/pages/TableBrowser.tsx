import { useState, useEffect } from 'react';
import { Menu, Table, Spin, Alert, Typography, Empty } from 'antd';
import { getTableList, getTableData } from '../api/client';

const { Title } = Typography;

export default function TableBrowser() {
  const [tables, setTables] = useState<string[]>([]);
  const [selectedTable, setSelectedTable] = useState<string | null>(null);
  const [columns, setColumns] = useState<string[]>([]);
  const [rows, setRows] = useState<Record<string, unknown>[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load table list
  useEffect(() => {
    getTableList()
      .then((data) => setTables(data.tables))
      .catch((err) => setError(err.message));
  }, []);

  // Load table data when selection changes
  useEffect(() => {
    if (!selectedTable) return;
    setLoading(true);
    setError(null);
    getTableData(selectedTable)
      .then((data) => {
        setColumns(data.columns);
        setRows(data.rows);
        setTotal(data.total);
      })
      .catch((err) => setError(err.message))
      .finally(() => setLoading(false));
  }, [selectedTable]);

  const antColumns = columns.map((col) => ({
    title: col,
    dataIndex: col,
    key: col,
    sorter: (a: Record<string, unknown>, b: Record<string, unknown>) => {
      const va = a[col];
      const vb = b[col];
      if (typeof va === 'number' && typeof vb === 'number') return va - vb;
      return String(va ?? '').localeCompare(String(vb ?? ''));
    },
    render: (value: unknown) => {
      if (value == null) return <span style={{ color: '#ccc' }}>null</span>;
      if (typeof value === 'object') return JSON.stringify(value);
      return String(value);
    },
    ellipsis: true,
  }));

  return (
    <div style={{ display: 'flex', gap: 16, height: '100%' }}>
      {/* Table list sidebar */}
      <div style={{ width: 220, flexShrink: 0, borderRight: '1px solid #f0f0f0', paddingRight: 16 }}>
        <Title level={5} style={{ marginBottom: 12 }}>LanceDB Tables</Title>
        {tables.length === 0 && !error ? (
          <Spin size="small" />
        ) : (
          <Menu
            mode="inline"
            selectedKeys={selectedTable ? [selectedTable] : []}
            items={tables.map((t) => ({ key: t, label: t }))}
            onClick={({ key }) => setSelectedTable(key)}
          />
        )}
      </div>

      {/* Table data */}
      <div style={{ flex: 1, overflow: 'auto' }}>
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
        {!selectedTable ? (
          <Empty description="Select a table from the sidebar" />
        ) : loading ? (
          <Spin size="large" style={{ display: 'block', marginTop: 64 }} />
        ) : (
          <>
            <Title level={4}>
              {selectedTable}{' '}
              <span style={{ fontSize: 14, fontWeight: 400, color: '#888' }}>
                ({total} rows)
              </span>
            </Title>
            <Table
              dataSource={rows}
              columns={antColumns}
              rowKey={(_, index) => String(index)}
              size="small"
              scroll={{ x: true }}
              pagination={{ pageSize: 50, showSizeChanger: true }}
            />
          </>
        )}
      </div>
    </div>
  );
}
