import { UnsourcedLabel } from "platform";

// Marks a design move that carries no citation — dashed amber, "your call",
// not "wrong". Takes no props.
export function Unsourced() {
  return (
    <div style={{ display: "flex" }}>
      <UnsourcedLabel />
    </div>
  );
}
