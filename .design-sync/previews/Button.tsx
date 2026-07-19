import { Button } from "platform";

// Layout glue uses inline styles on purpose: the shipped stylesheet is the
// app's compiled Tailwind, so only utility classes the app already uses are
// present. The DS styling lives inside <Button> itself (its cva classes).
const row: React.CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: 12,
  flexWrap: "wrap",
};

export function Variants() {
  return (
    <div style={row}>
      <Button variant="default">Compile &amp; validate</Button>
      <Button variant="outline">Preview protocol</Button>
      <Button variant="subtle">Add measure</Button>
      <Button variant="ghost">Dismiss</Button>
    </div>
  );
}

export function Sizes() {
  return (
    <div style={row}>
      <Button size="sm">Accept move</Button>
      <Button size="default">Accept move</Button>
      <Button size="icon" aria-label="Add">
        +
      </Button>
    </div>
  );
}

export function Disabled() {
  return (
    <div style={row}>
      <Button disabled>Compile &amp; validate</Button>
      <Button variant="outline" disabled>
        Preview protocol
      </Button>
    </div>
  );
}
