import { useState } from "react";
import { Input, Button, message, Card, Select, Space, Divider, Alert, Spin } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";
import { useCommitSchema } from "../../hooks/useCommitSchema";
import type { OpSchema } from "../../hooks/useCommitSchema";
import { SchemaField } from "./SchemaField";

interface OpEntry {
  /** Which opSchema this operation uses */
  schemaIdx: number;
  /** The actual data */
  data: Record<string, unknown>;
}

export function CommitForm() {
  const [commitMessage, setCommitMessage] = useState("");
  const [operations, setOperations] = useState<OpEntry[]>([]);
  const queryClient = useQueryClient();

  const { data: commitSchema, isLoading: schemaLoading, error: schemaError } = useCommitSchema();

  const submitMutation = useMutation({
    mutationFn: () => {
      const ops = operations.map((entry) => {
        const opSchema = commitSchema!.opSchemas[entry.schemaIdx];
        return { ...entry.data, op: opSchema.opValue };
      });
      return apiFetch("/commits", {
        method: "POST",
        body: JSON.stringify({ message: commitMessage, operations: ops }),
      });
    },
    onSuccess: () => {
      message.success("Commit submitted");
      setCommitMessage("");
      setOperations([]);
      queryClient.invalidateQueries({ queryKey: ["commits"] });
    },
    onError: (e) => message.error(String(e)),
  });

  function addOperation(schemaIdx: number) {
    const opSchema = commitSchema!.opSchemas[schemaIdx];
    // Build initial data from schema defaults, injecting "op"
    const initial: Record<string, unknown> = { op: opSchema.opValue };
    const props = opSchema.schema.properties ?? {};
    for (const [key, propSchema] of Object.entries(props)) {
      if (key === "op") continue;
      if (propSchema.default !== undefined) {
        initial[key] = propSchema.default;
      } else if (propSchema.type === "array") {
        initial[key] = [];
      } else if (propSchema.type === "object") {
        initial[key] = {};
      }
    }
    setOperations([...operations, { schemaIdx, data: initial }]);
  }

  function removeOperation(idx: number) {
    setOperations(operations.filter((_, i) => i !== idx));
  }

  function updateOperation(idx: number, data: Record<string, unknown>) {
    const next = [...operations];
    next[idx] = { ...next[idx], data };
    setOperations(next);
  }

  if (schemaLoading) {
    return <Card title="Submit Commit" style={{ marginBottom: 16 }}><Spin /></Card>;
  }

  if (schemaError || !commitSchema) {
    return (
      <Card title="Submit Commit" style={{ marginBottom: 16 }}>
        <Alert type="error" message={`Failed to load schema: ${schemaError}`} />
      </Card>
    );
  }

  const opOptions = commitSchema.opSchemas.map((s: OpSchema, i: number) => ({
    label: s.name.replace(/Op$/, "").replace(/([a-z])([A-Z])/g, "$1 $2"),
    value: i,
  }));

  return (
    <Card title="Submit Commit" style={{ marginBottom: 16 }}>
      <Input
        placeholder="Commit message"
        value={commitMessage}
        onChange={(e) => setCommitMessage(e.target.value)}
        style={{ marginBottom: 12 }}
      />

      {operations.map((entry, idx) => {
        const opSchema = commitSchema.opSchemas[entry.schemaIdx];
        return (
          <Card
            key={idx}
            type="inner"
            size="small"
            title={
              <span>
                Operation {idx + 1}: <strong>{opSchema.name.replace(/Op$/, "").replace(/([a-z])([A-Z])/g, "$1 $2")}</strong>
              </span>
            }
            extra={
              <Button
                type="text"
                danger
                icon={<DeleteOutlined />}
                onClick={() => removeOperation(idx)}
                size="small"
              />
            }
            style={{ marginBottom: 8 }}
          >
            {Object.entries(opSchema.schema.properties ?? {}).map(([key, propSchema]) => {
              if (key === "op") return null;
              const isRequired = opSchema.schema.required?.includes(key);
              return (
                <div key={key} style={{ marginBottom: 8 }}>
                  <label style={{ fontWeight: 500, fontSize: 13 }}>
                    {propSchema.title ?? key}
                    {isRequired && <span style={{ color: "#ff4d4f" }}> *</span>}
                  </label>
                  <SchemaField
                    schema={propSchema}
                    value={entry.data[key]}
                    onChange={(v) =>
                      updateOperation(idx, { ...entry.data, [key]: v })
                    }
                    label={propSchema.title ?? key}
                  />
                </div>
              );
            })}
          </Card>
        );
      })}

      <Divider dashed style={{ margin: "12px 0" }} />

      <Space style={{ marginBottom: 12 }}>
        <Select
          placeholder="Add operation..."
          options={opOptions}
          onSelect={(idx: number) => addOperation(idx)}
          value={null as unknown as number}
          style={{ width: 200 }}
          suffixIcon={<PlusOutlined />}
        />
      </Space>

      <div>
        <Button
          type="primary"
          onClick={() => submitMutation.mutate()}
          loading={submitMutation.isPending}
          disabled={!commitMessage.trim() || operations.length === 0}
        >
          Submit ({operations.length} operation{operations.length !== 1 ? "s" : ""})
        </Button>
      </div>
    </Card>
  );
}
