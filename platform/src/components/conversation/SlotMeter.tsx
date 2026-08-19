import { MANDATORY_SLOTS, SLOT_LABELS, type ProtocolDraft } from "@/lib/types";
import { cn } from "@/lib/cn";

/* Protocol completeness, as the *protocol* sees it.
 *
 * The dots are the eight conversation sections — how a researcher talks — and
 * they still light as those fill. Readiness is a different question, and this
 * component used to answer it from the dots: fill all eight and it announced
 * "ready to compile & validate", which was untrue. The eight sections are not
 * the schema's requirements. `measures` has no protocol field at all, while a
 * sample size, a session length and a study title are required and are not
 * sections. A draft could show eight lit dots and still refuse to compile.
 *
 * So readiness comes from the server's compile, which names what is missing in
 * the researcher's own words (`compiler.PROTOCOL_SLOTS`). The dots stay as a
 * sense of momentum; the sentence beneath them is the truth. */
export function SlotMeter({
  draft,
  unresolved,
}: {
  draft: ProtocolDraft;
  /** Outstanding protocol slots from the last server compile, already
   *  phrased for a reader. `undefined` = no compile has come back yet. */
  unresolved?: string[];
}) {
  const filled = MANDATORY_SLOTS.filter((s) => draft[s].length > 0);
  const bare = MANDATORY_SLOTS.filter((s) => draft[s].length === 0);

  return (
    <div className="flex flex-col gap-2">
      <div className="flex items-center gap-2">
        <div
          className="flex gap-1"
          role="img"
          aria-label={`${filled.length} of ${MANDATORY_SLOTS.length} conversation sections covered`}
        >
          {MANDATORY_SLOTS.map((s) => (
            <span
              key={s}
              className={cn(
                "size-2.5 rounded-chip border transition-colors duration-standard",
                draft[s].length > 0
                  ? "border-transparent bg-ink"
                  : "border-border-strong bg-transparent",
              )}
            />
          ))}
        </div>
        <span className="tabular type-caption text-text-muted">
          {filled.length}/{MANDATORY_SLOTS.length}
        </span>
      </div>
      {unresolved === undefined ? (
        bare.length > 0 ? (
          <p className="type-caption text-text-muted">
            Not covered yet: {bare.map((s) => SLOT_LABELS[s]).join(", ")}.
          </p>
        ) : null
      ) : unresolved.length === 0 ? (
        <p className="type-caption text-text">
          The protocol has everything it needs: ready to compile.
        </p>
      ) : (
        <p className="type-caption text-text-muted">
          {/* The server names these slots in its own schema vocabulary
            * ("statisticalPlan", "researchQuestions"). A camelCase identifier
            * in a sentence a researcher reads is the code leaking through the
            * product, so each one is mapped to the label the rest of the app
            * already uses and anything unmapped falls back to itself. */}
          The protocol still needs:{" "}
          {unresolved
            .map((slot) => SLOT_LABELS[slot as keyof typeof SLOT_LABELS] ?? slot)
            .join(", ")}
          .
        </p>
      )}
    </div>
  );
}
