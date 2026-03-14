import { apiFetch } from "./client";

export interface PaperSummary {
  slug: string;
  xml_slug: string | null;
  has_xml: boolean;
  has_yaml: boolean;
}

export interface XmlPremise {
  id: string | null;
  title: string;
  content: string;
}

export interface XmlStep {
  title: string;
  content: string;
}

export interface XmlConclusion {
  title: string;
  content: string;
}

export interface XmlChain {
  file: string;
  notations: string[];
  premises: XmlPremise[];
  steps: XmlStep[];
  conclusion: XmlConclusion | null;
}

export interface PaperXml {
  slug: string;
  xml_slug: string;
  chains: XmlChain[];
}

export interface YamlKnowledge {
  type: string;
  name: string;
  content?: string;
  prior?: number;
  target?: string;
  premises?: string[];
  conclusion?: string;
  steps?: Array<{ type: string; premises?: string[]; lambda?: string; reasoning?: string; conclusion?: string }>;
}

export interface YamlModule {
  type: string;
  name: string;
  title: string;
  knowledge: YamlKnowledge[];
}

export interface PaperYaml {
  slug: string;
  modules: Record<string, YamlModule>;
}

export const papersApi = {
  list: () => apiFetch<PaperSummary[]>("/papers"),
  getXml: (slug: string) => apiFetch<PaperXml>(`/papers/${slug}/xml`),
  getYaml: (slug: string) => apiFetch<PaperYaml>(`/papers/${slug}/yaml`),
};
