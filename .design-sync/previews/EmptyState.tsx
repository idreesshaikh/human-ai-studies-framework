import { EmptyState, Button } from "platform";

// Every empty view teaches: one wry line and the single next action. Two
// realistic study-domain empties — a project with no studies yet, and a
// members list awaiting the first invite.
const stack: React.CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: 20,
  maxWidth: 460,
};

export function NoStudies() {
  return (
    <div style={stack}>
      <EmptyState
        line="No studies yet. A study starts as a conversation — describe what you want to learn and the platform proposes citable design moves."
        action={<Button size="sm">Start a design conversation</Button>}
      />
    </div>
  );
}

export function NoMembers() {
  return (
    <div style={stack}>
      <EmptyState
        line="Just you on this project so far. Invite a colleague to co-design the protocol or review the findings."
        action={
          <Button size="sm" variant="outline">
            Invite a colleague
          </Button>
        }
      />
    </div>
  );
}
