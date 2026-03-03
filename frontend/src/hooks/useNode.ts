import { useQuery } from "@tanstack/react-query";
import { fetchNode, fetchNodes } from "../api/nodes";

export function useNode(id: number | null) {
  return useQuery({
    queryKey: ["node", id],
    queryFn: () => fetchNode(id!),
    enabled: id !== null,
  });
}

export function useNodes(page: number, size: number, type?: string) {
  return useQuery({
    queryKey: ["nodes", page, size, type],
    queryFn: () => fetchNodes(page, size, type),
  });
}
