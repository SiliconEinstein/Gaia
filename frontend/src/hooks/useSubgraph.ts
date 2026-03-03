import { useQuery } from "@tanstack/react-query";
import { fetchSubgraph } from "../api/nodes";

export function useSubgraph(nodeId: number | null, hops = 1) {
  return useQuery({
    queryKey: ["subgraph", nodeId, hops],
    queryFn: () => fetchSubgraph(nodeId!, hops),
    enabled: nodeId !== null,
  });
}
