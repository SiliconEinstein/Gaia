import { useSearchParams } from "react-router-dom";
import { SubgraphLoader } from "../components/graph/SubgraphLoader";

export function GraphExplorer() {
  const [searchParams] = useSearchParams();
  const nodeId = searchParams.get("node");
  const hops = searchParams.get("hops");

  return (
    <div style={{ height: "calc(100vh - 112px)" }}>
      <SubgraphLoader
        initialNodeId={nodeId ? Number(nodeId) : undefined}
        initialHops={hops ? Number(hops) : 1}
      />
    </div>
  );
}
