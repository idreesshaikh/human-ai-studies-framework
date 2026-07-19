import { RoleGate, Button, Badge } from "platform";

// RoleGate is UX-only: it shows its children when the role can do the
// capability, else the fallback. Two panels make both branches visible at
// once — an owner may manage members; a viewer sees the muted fallback.
const stack: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 16,
  maxWidth: 420,
};

const panel: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "space-between",
  gap: 12,
  padding: "12px 14px",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-card, 12px)",
};

const label: React.CSSProperties = {
  fontSize: 13,
  color: "var(--color-text-muted)",
};

const muted: React.CSSProperties = {
  fontSize: 13,
  color: "var(--color-text-muted)",
  fontStyle: "italic",
};

export function AllowedAndDenied() {
  return (
    <div style={stack}>
      <div style={panel}>
        <span style={label}>Owner · manage_members</span>
        <RoleGate role="owner" capability="manage_members">
          <Button size="sm">Invite colleague</Button>
        </RoleGate>
      </div>
      <div style={panel}>
        <span style={label}>Viewer · manage_members</span>
        <RoleGate
          role="viewer"
          capability="manage_members"
          fallback={<span style={muted}>Ask an owner</span>}
        >
          <Button size="sm">Invite colleague</Button>
        </RoleGate>
      </div>
      <div style={panel}>
        <span style={label}>Researcher · apply_draft</span>
        <RoleGate role="researcher" capability="apply_draft">
          <Badge variant="grounded">Can apply drafts</Badge>
        </RoleGate>
      </div>
    </div>
  );
}
