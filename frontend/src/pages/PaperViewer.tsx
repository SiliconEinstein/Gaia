import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { papersApi } from "../api/papers";

export function PaperViewer() {
  const [selected, setSelected] = useState<string | null>(null);
  const { data: papers, isLoading, error } = useQuery({
    queryKey: ["papers"],
    queryFn: papersApi.list,
  });

  if (isLoading) return <div>Loading papers...</div>;
  if (error) return <div>Error: {String(error)}</div>;

  return (
    <div style={{ display: "flex", gap: 16 }}>
      <div style={{ width: 220, borderRight: "1px solid #ddd", paddingRight: 12 }}>
        <h3>Papers</h3>
        {papers?.map((p) => (
          <div
            key={p.slug}
            onClick={() => setSelected(p.slug)}
            style={{
              padding: "8px 4px",
              cursor: "pointer",
              fontWeight: p.slug === selected ? 700 : 400,
              background: p.slug === selected ? "#e6f4ff" : "transparent",
            }}
          >
            {p.xml_slug ?? p.slug}
          </div>
        ))}
      </div>
      <div style={{ flex: 1 }}>
        {selected ? <PaperDetail slug={selected} /> : <p>← Select a paper</p>}
      </div>
    </div>
  );
}

function PaperDetail({ slug }: { slug: string }) {
  const xml = useQuery({ queryKey: ["paper-xml", slug], queryFn: () => papersApi.getXml(slug) });
  const yaml = useQuery({ queryKey: ["paper-yaml", slug], queryFn: () => papersApi.getYaml(slug) });

  return (
    <div>
      <h3>{slug}</h3>
      {xml.isLoading && <p>Loading XML...</p>}
      {xml.data && (
        <div>
          <strong>XML Chains: {xml.data.chains.length}</strong>
          {xml.data.chains.map((chain, i) => (
            <details key={chain.file} style={{ marginTop: 8 }}>
              <summary>{chain.file} — {chain.premises.length} premises, {chain.steps.length} steps</summary>
              <div style={{ paddingLeft: 16 }}>
                <strong>Premises:</strong>
                {chain.premises.map((p) => (
                  <div key={p.id} style={{ marginTop: 4, padding: 8, background: "#f6ffed", borderRadius: 4 }}>
                    <strong>[{p.id}] {p.title}</strong>
                    <p style={{ margin: "4px 0 0", fontSize: 13 }}>{p.content}</p>
                  </div>
                ))}
                <strong style={{ display: "block", marginTop: 8 }}>Steps:</strong>
                {chain.steps.map((s, j) => (
                  <div key={j} style={{ marginTop: 4, padding: 8, background: "#f9f0ff", borderRadius: 4 }}>
                    <strong>{s.title}</strong>
                    <p style={{ margin: "4px 0 0", fontSize: 13 }}>{s.content}</p>
                  </div>
                ))}
                {chain.conclusion && (
                  <div style={{ marginTop: 8, padding: 8, background: "#fff7e6", borderRadius: 4 }}>
                    <strong>Conclusion: {chain.conclusion.title}</strong>
                    <p style={{ margin: "4px 0 0", fontSize: 13 }}>{chain.conclusion.content}</p>
                  </div>
                )}
              </div>
            </details>
          ))}
        </div>
      )}
      {yaml.isLoading && <p>Loading YAML...</p>}
      {yaml.data && (
        <div style={{ marginTop: 16 }}>
          <strong>YAML Package</strong>
          {Object.entries(yaml.data.modules)
            .filter(([name]) => name !== "package")
            .map(([name, mod]) => {
              const knowledge = (mod as any).knowledge ?? [];
              const settings = knowledge.filter((k: any) => k.type === "setting");
              const claims = knowledge.filter((k: any) => k.type === "claim");
              const chains = knowledge.filter((k: any) => k.type === "chain_expr");
              return (
                <details key={name} style={{ marginTop: 12 }} open>
                  <summary style={{ fontWeight: 600, cursor: "pointer" }}>
                    [{(mod as any).type}] {name} — {knowledge.length} items
                  </summary>
                  <div style={{ paddingLeft: 16, marginTop: 8 }}>
                    {settings.length > 0 && (
                      <details open>
                        <summary style={{ color: "#08979c", cursor: "pointer" }}>
                          Settings ({settings.length})
                        </summary>
                        {settings.map((k: any) => (
                          <div key={k.name} style={{ margin: "6px 0", padding: 8, background: "#e6fffb", borderRadius: 4 }}>
                            <strong style={{ color: "#08979c" }}>{k.name}</strong>
                            {k.prior !== undefined && <span style={{ marginLeft: 8, fontSize: 12, color: "#888" }}>prior: {k.prior}</span>}
                            <p style={{ margin: "4px 0 0", fontSize: 13 }}>{k.content}</p>
                          </div>
                        ))}
                      </details>
                    )}
                    {claims.length > 0 && (
                      <details open>
                        <summary style={{ color: "#d46b08", cursor: "pointer" }}>
                          Claims ({claims.length})
                        </summary>
                        {claims.map((k: any) => (
                          <div key={k.name} style={{ margin: "6px 0", padding: 8, background: "#fff7e6", borderRadius: 4 }}>
                            <strong style={{ color: "#d46b08" }}>{k.name}</strong>
                            {k.prior !== undefined && <span style={{ marginLeft: 8, fontSize: 12, color: "#888" }}>prior: {k.prior}</span>}
                            {k.content && <p style={{ margin: "4px 0 0", fontSize: 13 }}>{k.content}</p>}
                          </div>
                        ))}
                      </details>
                    )}
                    {chains.length > 0 && (
                      <details>
                        <summary style={{ color: "#531dab", cursor: "pointer" }}>
                          Chains ({chains.length})
                        </summary>
                        {chains.map((k: any) => (
                          <div key={k.name} style={{ margin: "6px 0", padding: 8, background: "#f9f0ff", borderRadius: 4 }}>
                            <strong style={{ color: "#531dab" }}>{k.name}</strong>
                            <span style={{ marginLeft: 8, fontSize: 12, color: "#888" }}>{k.edge_type}</span>
                            {(k.steps ?? []).map((step: any) => (
                              <div key={step.step} style={{ fontSize: 12, marginTop: 4, paddingLeft: 8, borderLeft: "2px solid #d3adf7" }}>
                                <span style={{ color: "#888", marginRight: 6 }}>#{step.step}</span>
                                {step.ref && <span style={{ color: "#08979c" }}>ref: {step.ref}</span>}
                                {step.lambda && <span>{step.lambda}</span>}
                              </div>
                            ))}
                          </div>
                        ))}
                      </details>
                    )}
                  </div>
                </details>
              );
            })}
        </div>
      )}
    </div>
  );
}
