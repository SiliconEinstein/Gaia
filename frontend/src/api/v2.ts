// frontend/src/api/v2.ts
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "./client";
import type {
  V2Package, V2Knowledge, V2Module, V2Chain,
  V2ProbabilityRecord, V2BeliefSnapshot,
  V2Paginated, UnifiedGraphData,
} from "./v2-types";

// ── Fetch functions ──

export const fetchPackages = (page = 1, pageSize = 20) =>
  apiFetch<V2Paginated<V2Package>>(`/packages?page=${page}&page_size=${pageSize}`);

export const fetchPackage = (id: string) =>
  apiFetch<V2Package>(`/packages/${encodeURIComponent(id)}`);

export const fetchKnowledgeList = (page = 1, pageSize = 20, typeFilter?: string) => {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
  if (typeFilter) params.set("type_filter", typeFilter);
  return apiFetch<V2Paginated<V2Knowledge>>(`/knowledge?${params}`);
};

export const fetchKnowledge = (id: string, version?: number) => {
  const path = version
    ? `/knowledge/${encodeURIComponent(id)}?version=${version}`
    : `/knowledge/${encodeURIComponent(id)}`;
  return apiFetch<V2Knowledge>(path);
};

export const fetchKnowledgeVersions = (id: string) =>
  apiFetch<V2Knowledge[]>(`/knowledge/${encodeURIComponent(id)}/versions`);

export const fetchKnowledgeBeliefs = (id: string) =>
  apiFetch<V2BeliefSnapshot[]>(`/knowledge/${encodeURIComponent(id)}/beliefs`);

export const fetchModules = (packageId?: string) => {
  const params = packageId ? `?package_id=${encodeURIComponent(packageId)}` : "";
  return apiFetch<V2Module[]>(`/modules${params}`);
};

export const fetchModule = (id: string) =>
  apiFetch<V2Module>(`/modules/${encodeURIComponent(id)}`);

export const fetchModuleChains = (moduleId: string) =>
  apiFetch<V2Chain[]>(`/modules/${encodeURIComponent(moduleId)}/chains`);

export const fetchChain = (id: string) =>
  apiFetch<V2Chain>(`/chains/${encodeURIComponent(id)}`);

export const fetchChainProbabilities = (id: string) =>
  apiFetch<V2ProbabilityRecord[]>(`/chains/${encodeURIComponent(id)}/probabilities`);

export const fetchUnifiedGraph = (packageId?: string) => {
  const params = packageId ? `?package_id=${encodeURIComponent(packageId)}` : "";
  return apiFetch<UnifiedGraphData>(`/graph${params}`);
};

// ── React Query hooks ──

export const usePackages = (page = 1, pageSize = 20) =>
  useQuery({ queryKey: ["v2", "packages", page, pageSize], queryFn: () => fetchPackages(page, pageSize) });

export const usePackage = (id: string) =>
  useQuery({ queryKey: ["v2", "package", id], queryFn: () => fetchPackage(id), enabled: !!id });

export const useKnowledgeList = (page = 1, pageSize = 20, typeFilter?: string) =>
  useQuery({
    queryKey: ["v2", "knowledge", page, pageSize, typeFilter],
    queryFn: () => fetchKnowledgeList(page, pageSize, typeFilter),
  });

export const useKnowledge = (id: string) =>
  useQuery({ queryKey: ["v2", "knowledge", id], queryFn: () => fetchKnowledge(id), enabled: !!id });

export const useKnowledgeVersions = (id: string) =>
  useQuery({ queryKey: ["v2", "knowledge-versions", id], queryFn: () => fetchKnowledgeVersions(id), enabled: !!id });

export const useKnowledgeBeliefs = (id: string) =>
  useQuery({ queryKey: ["v2", "knowledge-beliefs", id], queryFn: () => fetchKnowledgeBeliefs(id), enabled: !!id });

export const useModules = (packageId?: string) =>
  useQuery({ queryKey: ["v2", "modules", packageId], queryFn: () => fetchModules(packageId) });

export const useModule = (id: string) =>
  useQuery({ queryKey: ["v2", "module", id], queryFn: () => fetchModule(id), enabled: !!id });

export const useModuleChains = (moduleId: string) =>
  useQuery({ queryKey: ["v2", "module-chains", moduleId], queryFn: () => fetchModuleChains(moduleId), enabled: !!moduleId });

export const useChain = (id: string) =>
  useQuery({ queryKey: ["v2", "chain", id], queryFn: () => fetchChain(id), enabled: !!id });

export const useChainProbabilities = (id: string) =>
  useQuery({ queryKey: ["v2", "chain-probs", id], queryFn: () => fetchChainProbabilities(id), enabled: !!id });

export const useUnifiedGraph = (packageId?: string) =>
  useQuery({ queryKey: ["v2", "unified-graph", packageId], queryFn: () => fetchUnifiedGraph(packageId) });
