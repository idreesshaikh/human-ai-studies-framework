import { FeedbackAffordance } from "platform";

// Marking a turn as platform feedback — a subtle affordance under a
// researcher's turn. Detection may *offer* the marking (a soft nudge); marking
// is always the researcher's confirm. Three states shown separately.
const noop = () => {};

export function Default() {
  return (
    <div style={{ display: "flex" }}>
      <FeedbackAffordance suggested={false} marked={false} onMark={noop} />
    </div>
  );
}

export function SuggestedNudge() {
  return (
    <div style={{ display: "flex" }}>
      <FeedbackAffordance suggested={true} marked={false} onMark={noop} />
    </div>
  );
}

export function Marked() {
  return (
    <div style={{ display: "flex" }}>
      <FeedbackAffordance suggested={false} marked={true} onMark={noop} />
    </div>
  );
}
