import { apiFetch } from "./client";
import type { StatsResponse, HealthResponse } from "./types";

export function fetchHealth() {
  return apiFetch<HealthResponse>("/health");
}

export function fetchStats() {
  return apiFetch<StatsResponse>("/stats");
}

export interface Commit {
  commit_id: string;
  status: string;
  message: string;
  operations: unknown[];
  check_results: Record<string, unknown> | null;
  review_results: Record<string, unknown> | null;
  merge_results: Record<string, unknown> | null;
  created_at: string | null;
  updated_at: string | null;
}

export function fetchCommits() {
  return apiFetch<Commit[]>("/commits");
}

export function fetchCommit(id: string) {
  return apiFetch<Commit>(`/commits/${id}`);
}

export function reviewCommit(id: string, depth = "standard") {
  return apiFetch<Record<string, unknown>>(`/commits/${id}/review`, {
    method: "POST",
    body: JSON.stringify({ depth }),
  });
}

export function mergeCommit(id: string, force = false) {
  return apiFetch<Record<string, unknown>>(`/commits/${id}/merge`, {
    method: "POST",
    body: JSON.stringify({ force }),
  });
}
