/**
 * Renders a form field dynamically based on a JSON Schema property.
 * Handles: string, integer/number, boolean, object (JSON), array of strings,
 * array of objects (sub-forms), and anyOf unions.
 */
import { Input, InputNumber, Switch, Button, Card, Select, Space } from "antd";
import { PlusOutlined, DeleteOutlined } from "@ant-design/icons";
import type { JsonSchema } from "../../hooks/useCommitSchema";

const { TextArea } = Input;

interface Props {
  schema: JsonSchema;
  value: unknown;
  onChange: (v: unknown) => void;
  label?: string;
}

/**
 * Determine which concrete schema variant to use from an anyOf,
 * based on current value shape.
 */
function pickAnyOfVariant(anyOf: JsonSchema[], value: unknown): JsonSchema {
  // Filter out null type
  const nonNull = anyOf.filter(
    (s) => s.type !== "null" && !(s.type === undefined && !s.properties && !s.$ref)
  );
  if (nonNull.length === 1) return nonNull[0];

  // If value is a number and there's an integer type, pick that
  if (typeof value === "number") {
    const num = nonNull.find((s) => s.type === "integer" || s.type === "number");
    if (num) return num;
  }

  // If value is an object with a distinguishing field, match it
  if (value && typeof value === "object" && !Array.isArray(value)) {
    for (const variant of nonNull) {
      if (variant.properties) {
        const keys = Object.keys(variant.properties);
        const valKeys = Object.keys(value as Record<string, unknown>);
        // Check if required keys of this variant are present
        const req = variant.required ?? [];
        if (req.length > 0 && req.every((r) => valKeys.includes(r))) {
          return variant;
        }
        // Fallback: check key overlap
        if (keys.some((k) => valKeys.includes(k))) {
          return variant;
        }
      }
    }
  }

  // Default to first non-null
  return nonNull[0] ?? anyOf[0];
}

export function SchemaField({ schema, value, onChange, label }: Props) {
  // Handle anyOf (union types)
  if (schema.anyOf) {
    const nonNull = schema.anyOf.filter((s) => s.type !== "null");

    // Simple union with a selector (e.g., NewNode | NodeRef)
    if (nonNull.length > 1 && nonNull.every((s) => s.properties)) {
      return (
        <AnyOfField variants={nonNull} value={value} onChange={onChange} label={label} />
      );
    }

    // Single non-null type or simple type union
    const picked = pickAnyOfVariant(schema.anyOf, value);
    return <SchemaField schema={picked} value={value} onChange={onChange} label={label} />;
  }

  // Object with properties → render each property as a sub-field
  if (schema.type === "object" && schema.properties) {
    const obj = (value as Record<string, unknown>) ?? {};
    return (
      <Card
        size="small"
        title={label}
        style={{ marginBottom: 8 }}
      >
        {Object.entries(schema.properties).map(([key, propSchema]) => {
          // Skip the "op" field — it's auto-set
          if (key === "op") return null;
          const isRequired = schema.required?.includes(key);
          return (
            <div key={key} style={{ marginBottom: 8 }}>
              <label style={{ fontWeight: 500, fontSize: 13 }}>
                {propSchema.title ?? key}
                {isRequired && <span style={{ color: "#ff4d4f" }}> *</span>}
              </label>
              <SchemaField
                schema={propSchema}
                value={obj[key] ?? propSchema.default}
                onChange={(v) => onChange({ ...obj, [key]: v })}
              />
            </div>
          );
        })}
      </Card>
    );
  }

  // Free-form object (no properties defined) → JSON textarea
  if (schema.type === "object") {
    const strVal = typeof value === "string" ? value : JSON.stringify(value ?? {}, null, 2);
    return (
      <TextArea
        rows={3}
        value={strVal}
        onChange={(e) => {
          try {
            onChange(JSON.parse(e.target.value));
          } catch {
            // Keep as string while editing
            onChange(e.target.value);
          }
        }}
        style={{ fontFamily: "monospace", fontSize: 12 }}
        placeholder="JSON object"
      />
    );
  }

  // Array
  if (schema.type === "array" && schema.items) {
    return (
      <ArrayField
        itemSchema={schema.items}
        value={value as unknown[] | undefined}
        onChange={onChange}
        label={label}
      />
    );
  }

  // String
  if (schema.type === "string") {
    return (
      <Input
        value={(value as string) ?? ""}
        onChange={(e) => onChange(e.target.value)}
        placeholder={label}
      />
    );
  }

  // Number / Integer
  if (schema.type === "integer" || schema.type === "number") {
    return (
      <InputNumber
        value={value as number | undefined}
        onChange={(v) => onChange(v)}
        style={{ width: "100%" }}
        placeholder={label}
      />
    );
  }

  // Boolean
  if (schema.type === "boolean") {
    return <Switch checked={!!value} onChange={onChange} />;
  }

  // Fallback: JSON textarea
  const strVal = typeof value === "string" ? value : JSON.stringify(value ?? "", null, 2);
  return (
    <TextArea
      rows={2}
      value={strVal}
      onChange={(e) => {
        try {
          onChange(JSON.parse(e.target.value));
        } catch {
          onChange(e.target.value);
        }
      }}
      style={{ fontFamily: "monospace", fontSize: 12 }}
    />
  );
}

/** Renders an array of items with add/remove controls. */
function ArrayField({
  itemSchema,
  value,
  onChange,
  label,
}: {
  itemSchema: JsonSchema;
  value: unknown[] | undefined;
  onChange: (v: unknown) => void;
  label?: string;
}) {
  const items = value ?? [];

  function addItem() {
    const empty = makeDefault(itemSchema);
    onChange([...items, empty]);
  }

  function removeItem(idx: number) {
    onChange(items.filter((_, i) => i !== idx));
  }

  function updateItem(idx: number, val: unknown) {
    const next = [...items];
    next[idx] = val;
    onChange(next);
  }

  return (
    <div>
      {items.map((item, idx) => (
        <div key={idx} style={{ display: "flex", gap: 4, alignItems: 4, marginBottom: 4 }}>
          <div style={{ flex: 1 }}>
            <SchemaField
              schema={itemSchema}
              value={item}
              onChange={(v) => updateItem(idx, v)}
              label={`${label ?? "Item"} ${idx + 1}`}
            />
          </div>
          <Button
            type="text"
            danger
            icon={<DeleteOutlined />}
            onClick={() => removeItem(idx)}
            size="small"
            style={{ marginTop: 4 }}
          />
        </div>
      ))}
      <Button
        type="dashed"
        onClick={addItem}
        icon={<PlusOutlined />}
        size="small"
        block
      >
        Add {label ?? "item"}
      </Button>
    </div>
  );
}

/** Renders an anyOf union with a variant selector (e.g., NewNode | NodeRef). */
function AnyOfField({
  variants,
  value,
  onChange,
  label,
}: {
  variants: JsonSchema[];
  value: unknown;
  onChange: (v: unknown) => void;
  label?: string;
}) {
  const options = variants.map((v, i) => ({
    label: v.title ?? `Option ${i + 1}`,
    value: i,
  }));

  // Detect which variant is currently selected
  let selectedIdx = 0;
  if (value && typeof value === "object" && !Array.isArray(value)) {
    const valKeys = Object.keys(value as Record<string, unknown>);
    for (let i = 0; i < variants.length; i++) {
      const req = variants[i].required ?? [];
      if (req.length > 0 && req.every((r) => valKeys.includes(r))) {
        selectedIdx = i;
        break;
      }
    }
  }

  function switchVariant(idx: number) {
    onChange(makeDefault(variants[idx]));
  }

  return (
    <div>
      <Select
        value={selectedIdx}
        onChange={switchVariant}
        options={options}
        size="small"
        style={{ marginBottom: 4, width: "100%" }}
      />
      <SchemaField
        schema={variants[selectedIdx]}
        value={value}
        onChange={onChange}
        label={label}
      />
    </div>
  );
}

/** Create a default empty value for a schema. */
function makeDefault(schema: JsonSchema): unknown {
  if (schema.default !== undefined) return schema.default;
  if (schema.anyOf) {
    const nonNull = schema.anyOf.filter((s) => s.type !== "null");
    return makeDefault(nonNull[0] ?? schema.anyOf[0]);
  }
  if (schema.type === "object" && schema.properties) {
    const obj: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(schema.properties)) {
      if (v.const !== undefined) {
        obj[k] = v.const;
      } else if (v.default !== undefined) {
        obj[k] = v.default;
      } else if (schema.required?.includes(k)) {
        obj[k] = makeDefault(v);
      }
    }
    return obj;
  }
  if (schema.type === "object") return {};
  if (schema.type === "array") return [];
  if (schema.type === "string") return "";
  if (schema.type === "integer" || schema.type === "number") return 0;
  if (schema.type === "boolean") return false;
  return null;
}
