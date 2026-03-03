/**
 * Fetch the OpenAPI spec and extract operation schemas for CommitRequest.
 * When backend models change, the form automatically adapts.
 */
import { useQuery } from "@tanstack/react-query";

export interface JsonSchema {
  type?: string;
  const?: unknown;
  title?: string;
  properties?: Record<string, JsonSchema>;
  required?: string[];
  items?: JsonSchema;
  anyOf?: JsonSchema[];
  $ref?: string;
  default?: unknown;
}

export interface OpSchema {
  name: string;       // e.g. "AddEdgeOp"
  opValue: string;    // e.g. "add_edge"
  schema: JsonSchema; // resolved, no $refs
}

interface CommitSchema {
  /** All operation type schemas, resolved */
  opSchemas: OpSchema[];
  /** Full resolved schema map for lookups */
  allSchemas: Record<string, JsonSchema>;
}

/** Resolve all $ref in a schema recursively */
function resolveRefs(
  schema: JsonSchema,
  defs: Record<string, JsonSchema>,
  seen = new Set<string>()
): JsonSchema {
  if (schema.$ref) {
    const refName = schema.$ref.replace("#/components/schemas/", "");
    if (seen.has(refName)) return { type: "object", title: refName };
    seen.add(refName);
    const resolved = defs[refName];
    if (resolved) return resolveRefs(resolved, defs, seen);
    return schema;
  }

  const out: JsonSchema = { ...schema };

  if (out.properties) {
    out.properties = {};
    for (const [k, v] of Object.entries(schema.properties!)) {
      out.properties[k] = resolveRefs(v, defs, new Set(seen));
    }
  }

  if (out.items) {
    out.items = resolveRefs(out.items, defs, new Set(seen));
  }

  if (out.anyOf) {
    out.anyOf = out.anyOf.map((s) => resolveRefs(s, defs, new Set(seen)));
  }

  return out;
}

async function fetchCommitSchema(): Promise<CommitSchema> {
  const res = await fetch("/api/openapi.json");
  if (!res.ok) throw new Error(`Failed to fetch OpenAPI spec: ${res.status}`);
  const spec = await res.json();

  const defs: Record<string, JsonSchema> = spec.components?.schemas ?? {};

  // Find CommitRequest.operations → list of anyOf $refs → those are the op types
  const commitReq = defs["CommitRequest"];
  if (!commitReq?.properties?.operations?.items) {
    throw new Error("CommitRequest.operations schema not found");
  }

  const opsItems = commitReq.properties.operations.items;
  const opRefs = opsItems.anyOf ?? (opsItems.$ref ? [opsItems] : []);

  const opSchemas: OpSchema[] = [];
  const allSchemas: Record<string, JsonSchema> = {};

  for (const ref of opRefs) {
    const refName = ref.$ref?.replace("#/components/schemas/", "");
    if (!refName || !defs[refName]) continue;

    const resolved = resolveRefs(defs[refName], defs);
    allSchemas[refName] = resolved;

    // Extract the `op` const value (e.g. "add_edge")
    const opValue =
      resolved.properties?.op?.const ??
      resolved.properties?.op?.default ??
      refName;

    opSchemas.push({
      name: refName,
      opValue: String(opValue),
      schema: resolved,
    });
  }

  return { opSchemas, allSchemas };
}

export function useCommitSchema() {
  return useQuery({
    queryKey: ["openapi-commit-schema"],
    queryFn: fetchCommitSchema,
    staleTime: 5 * 60 * 1000, // cache 5 min
  });
}
