import { apiFetch } from "./client";
import type { HyperEdge, PaginatedResponse } from "./types";

export function fetchEdge(id: number) {
  return apiFetch<HyperEdge>(`/hyperedges/${id}`);
}

export function fetchEdges(page = 1, size = 50) {
  return apiFetch<PaginatedResponse<HyperEdge>>(
    `/hyperedges?page=${page}&size=${size}`
  );
}

export function fetchContradictions() {
  return apiFetch<HyperEdge[]>("/contradictions");
}
