import { Label, Input } from "platform";

const field: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  maxWidth: 320,
};

export function WithInput() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={field}>
        <Label htmlFor="pid">Participant ID</Label>
        <Input id="pid" defaultValue="P-01" />
      </div>
      <div style={field}>
        <Label htmlFor="cond">Condition</Label>
        <Input id="cond" defaultValue="AI-assisted" />
      </div>
    </div>
  );
}

export function Standalone() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <Label>Prescribed statistic</Label>
      <Label>Effect size (Cohen's d)</Label>
      <Label>Per-cell sample size</Label>
    </div>
  );
}
