import { TierBadge } from "platform";

// Provenance badge shown wherever a paper appears: Tier A seed (filled dot),
// Tier B harvest (ring), and study (star). All three side by side.
export function AllTiers() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <TierBadge tier="A" />
      <TierBadge tier="B" />
      <TierBadge tier="study" />
    </div>
  );
}
