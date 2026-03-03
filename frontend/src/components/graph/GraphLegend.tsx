import { NODE_STYLES, FACTOR_STYLES } from "../../lib/node-styles";

function Swatch({ bg, border }: { bg: string; border: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        width: 14,
        height: 14,
        borderRadius: 3,
        background: bg,
        border: `2px solid ${border}`,
        marginRight: 6,
        verticalAlign: "middle",
      }}
    />
  );
}

export function GraphLegend() {
  return (
    <div
      style={{
        display: "flex",
        gap: 24,
        flexWrap: "wrap",
        padding: "8px 0",
        fontSize: 12,
        color: "#666",
      }}
    >
      <div>
        <strong style={{ marginRight: 8 }}>Nodes:</strong>
        {Object.entries(NODE_STYLES).map(([type, s]) => (
          <span key={type} style={{ marginRight: 12 }}>
            <Swatch bg={s.color.background} border={s.color.border} />
            {type}
          </span>
        ))}
      </div>
      <div>
        <strong style={{ marginRight: 8 }}>Edges:</strong>
        {Object.entries(FACTOR_STYLES).map(([type, s]) => (
          <span key={type} style={{ marginRight: 12 }}>
            <Swatch bg={s.color.background} border={s.color.border} />
            {type}
          </span>
        ))}
      </div>
    </div>
  );
}
