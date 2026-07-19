import { ConversationView } from "platform";

// The design conversation — the main surface: the thread + composer on the
// left, the compiled protocol draft rail on the right. Self-contained; it runs
// on the deterministic offline assistant with no backend and no LLM key.
export function Conversation() {
  return (
    <div style={{ height: 700, width: 1040 }}>
      <ConversationView studyId="sample-study-2026" />
    </div>
  );
}
