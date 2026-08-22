import { MANDATORY_SLOTS, SLOT_LABELS, type ProtocolDraft, type Understanding } from "@/lib/types";
import { buildProtocolPath, type PathStep } from "@/lib/protocolPath";
import { cn } from "@/lib/cn";

/* Protocol completeness, as the *protocol* sees it.
 *
 * This was a row of eight dots. The dots were honest about how far along the
 * draft was and silent about everything else: what the order is, what is
 * being asked next, and how much is left. Two reviewers said the same thing
 * from opposite directions  -  one wanted the steps walked "in a more guided
 * fashion... so that all the information needed for the protocol is asked
 * for in a more systematic way", the other wanted "an overview somewhere
 * (like a chatlist) of what the user needs to provide" to make it "easier to
 * estimate how long the chat will be". A meter answers neither; a path
 * answers both, and the conversation was already walking one.
 *
 * Readiness is still a separate question, and still the server's to answer.
 * The steps below are what the CONVERSATION works through; the sentence at
 * the foot is what the COMPILE says, in the researcher's own words
 * (`compiler.PROTOCOL_SLOTS`). Those are different lists  -  `measures` has no
 * protocol field at all, while a sample size and a study title are required
 * and are not sections  -  which is why filling every step has never been the
 * same claim as "ready to compile", and why this component must not make it.
 */
export function SlotMeter({
  draft,
  unresolved,
  understanding,
}: {
  draft: ProtocolDraft;
  /** Outstanding protocol slots from the last server compile, already
   *  phrased for a reader. `undefined` = no compile has come back yet. */
  unresolved?: string[];
  /** What the conversation still needs to know before a design shape can
   *  honestly follow from it. Absent until the first turn returns, in which
   *  case the path is only its second half. */
  understanding?: Understanding;
}) {
  const path = buildProtocolPath(draft, understanding);
  const bare = MANDATORY_SLOTS.filter((s) => draft[s].length === 0);
  const current = path.phases
    .flatMap((p) => p.steps)
    .find((s) => s.status === "current");

  return (
    <div className="flex flex-col gap-2 px-gutter pb-3" data-agent="slot-meter">
      <div className="flex items-baseline justify-between gap-2">
        <span className="type-caption text-text-muted">Conversation progress</span>
        <span className="tabular type-caption text-text-muted">
          <span className="type-quantity text-text">{path.done}</span>/{path.total} covered
        </span>
      </div>

      {/* The full phase-by-phase checklist is real, load-bearing information
        *  -  nothing here is invented  -  but at 13 rows it was also the tallest
        * thing in the rail, pushing the compiled protocol itself (the
        * document of record, per the product's own first principle) below a
        * scroll on every study past its first few moves. Collapsed by
        * default, same `<details>` pattern "View raw YAML" already uses
        * below: the current step stays visible either way, so a glance still
        * answers "where am I", and the full walk is one click away rather
        * than gone. */}
      {current && (
        <p
          className="rounded-input bg-accent-wash px-3 py-2 type-caption text-text"
          data-agent="protocol-path-current"
        >
          <span className="type-legend text-accent">Now</span>{" "}{current.label}
        </p>
      )}
      <details className="group" data-agent="protocol-path">
        <summary className="type-caption cursor-pointer text-text-muted select-none">
          Show conversation path
        </summary>
        <div className="mt-2 flex flex-col gap-2">
          {path.phases.map((phase) => (
            <div key={phase.title} className="flex flex-col gap-1.5">
              <p className="type-legend text-text-muted">{phase.title}</p>
              {/* One rule down the left edge with the steps hanging off it  -
                * the same figure ConversationStart uses for the mechanism, so
                * a sequence looks like a sequence in both places. */}
                <ul className="flex flex-col border-l border-border pl-3">
                {phase.steps.map((step) => (
                  <Step key={step.id} step={step} />
                ))}
              </ul>
            </div>
          ))}
        </div>
      </details>

      {/* What is actually being asked right now. The path says where the
        * researcher is; this says what would move them. */}
      {path.upNext && (
        <p className="type-caption text-text-muted" data-agent="path-up-next">
          <span className="text-text">Next question:</span> {path.upNext}
        </p>
      )}

      {unresolved === undefined ? (
        bare.length > 0 ? (
          <details className="group">
            <summary className="type-caption cursor-pointer text-text-muted select-none">
              Still needed ({bare.length})
            </summary>
            <p className="mt-1 type-caption text-text-muted">
              {bare.map((s) => SLOT_LABELS[s]).join(", ")}.
            </p>
          </details>
        ) : null
      ) : unresolved.length === 0 ? (
        <p className="type-caption text-text" data-agent="protocol-readiness">
          The protocol has everything it needs: ready to compile.
        </p>
      ) : (
        <details className="group">
          <summary className="type-caption cursor-pointer text-text-muted select-none">
            Still needed ({unresolved.length})
          </summary>
          <p className="mt-1 type-caption text-text-muted">
            {unresolved
              .map((slot) => SLOT_LABELS[slot as keyof typeof SLOT_LABELS] ?? slot)
              .join(", ")}
            .
          </p>
        </details>
      )}
    </div>
  );
}

/* One step. The mark carries the state, not colour alone: a filled dot is
 * settled, a ruled dot is where the conversation is now, an outlined dot is
 * still ahead. Deliberately NOT the `mark-unsourced` ring  -  that notation
 * means "no source for this", and a step nobody has reached yet is not an
 * unsourced claim. One mark, one meaning. */
function Step({ step }: { step: PathStep }) {
  const current = step.status === "current";
  return (
    <li
      className={cn(
        "type-caption flex items-center gap-2 py-0.5",
        current ? "text-text" : "text-text-muted",
      )}
      aria-current={current ? "step" : undefined}
    >
      <span
        aria-hidden
        className={cn(
          "size-2 shrink-0 rounded-chip border transition-colors duration-standard",
          step.status === "done" && "border-transparent bg-ink",
          current && "border-accent bg-accent",
          step.status === "todo" && "border-border-strong bg-transparent",
        )}
      />
      <span className={cn("min-w-0 flex-1 truncate", current && "font-medium")}>
        {step.label}
      </span>
      {/* Said in words as well as in the mark: a researcher reading with a
        * screen reader, or in a theme where the accent is hard to pick out,
        * still learns which step is live. */}
      {current && <span className="type-legend shrink-0 text-accent">now</span>}
    </li>
  );
}
