import { apiFetch } from "./client";
import type { TextSearchResult } from "./types";

export function searchText(query: string, k = 50) {
  return apiFetch<TextSearchResult[]>("/search/text", {
    method: "POST",
    body: JSON.stringify({ query, k }),
  });
}
