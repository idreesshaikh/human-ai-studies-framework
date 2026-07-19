import { VersionChip } from "platform";

// A monospace revision chip so two revisions are distinguishable at a glance —
// rendered beside sessions, dataset rows, and in the amendment history. Takes
// a single numeric version. Shown as a from → to progression.
export function Versions() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
      <VersionChip version={1} />
      <span aria-hidden style={{ color: "var(--color-text-muted)" }}>
        →
      </span>
      <VersionChip version={2} />
      <span aria-hidden style={{ color: "var(--color-text-muted)" }}>
        →
      </span>
      <VersionChip version={4} />
    </div>
  );
}
