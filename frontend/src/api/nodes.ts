import { apiFetch } from "./client";
import type { Node, SubgraphResponse, PaginatedResponse } from "./types";

export function fetchNode(id: number) {
  return apiFetch<Node>(`/nodes/${id}`);
}

export function fetchNodes(page = 1, size = 50, type?: string) {
  const params = new URLSearchParams({ page: String(page), size: String(size) });
  if (type) params.set("type", type);
  return apiFetch<PaginatedResponse<Node>>(`/nodes?${params}`);
}

export function fetchSubgraph(nodeId: number, hops = 1) {
  return apiFetch<SubgraphResponse>(
    `/nodes/${nodeId}/subgraph/hydrated?hops=${hops}`
  );
}
