import { Input, Label } from "platform";

const field: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 6,
  maxWidth: 320,
};

export function Fields() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={field}>
        <Label>Study title</Label>
        <Input defaultValue="Comprehension debt under AI assistance" />
      </div>
      <div style={field}>
        <Label>Participant count</Label>
        <Input type="number" defaultValue={24} />
      </div>
    </div>
  );
}

export function States() {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
      <div style={field}>
        <Label>Condition label</Label>
        <Input placeholder="e.g. AI-assisted" />
      </div>
      <div style={field}>
        <Label>Locked protocol ID</Label>
        <Input defaultValue="sample-study-2026" disabled />
      </div>
    </div>
  );
}
