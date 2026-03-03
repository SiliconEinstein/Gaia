import { useQuery } from "@tanstack/react-query";
import { searchText } from "../api/search";

export function useTextSearch(query: string, k = 50) {
  return useQuery({
    queryKey: ["search-text", query, k],
    queryFn: () => searchText(query, k),
    enabled: query.length >= 2,
  });
}
