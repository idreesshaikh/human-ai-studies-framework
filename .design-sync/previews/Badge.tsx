import { Badge } from "platform";

const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  flexWrap: "wrap",
};

export function Variants() {
  return (
    <div style={row}>
      <Badge variant="default">AI-assisted</Badge>
      <Badge variant="grounded">grounded · 4 citations</Badge>
      <Badge variant="unsourced">unsourced</Badge>
      <Badge variant="outline">Control</Badge>
    </div>
  );
}

export function MoveProvenance() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={row}>
        <span style={{ fontSize: 13 }}>Counterbalance task order</span>
        <Badge variant="grounded">grounded</Badge>
      </div>
      <div style={row}>
        <span style={{ fontSize: 13 }}>Add think-aloud protocol</span>
        <Badge variant="unsourced">unsourced</Badge>
      </div>
    </div>
  );
}

export function SessionStatus() {
  return (
    <div style={row}>
      <Badge variant="grounded">complete</Badge>
      <Badge variant="outline">in progress</Badge>
      <Badge variant="unsourced">consent pending</Badge>
    </div>
  );
}
