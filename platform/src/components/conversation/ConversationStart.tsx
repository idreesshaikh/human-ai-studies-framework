import { Confidence } from "./Confidence";

/* The blank plate.
 *
 * A study workspace opened for the first time is a plate with nothing marked
 * on it: correct, honest, and — left bare — silent about what the researcher
 * is supposed to do next. This is what is printed on the blank plate. It
 * states the mechanism in the order it actually runs (say the idea → rule on
 * what comes back → compile it), shows the two marks the researcher will be
 * reading before they have ever seen one on a real card, and hands over three
 * openings that load straight into the composer.
 *
 * It is written ON the plate rather than in a panel laid on top of it: the
 * steps hang off one rule, with no container of their own. A first-run
 * explainer boxed inside the conversation, which is itself boxed inside the
 * workspace, was three nested frames deep before a single word was read.
 *
 * It is the record's own voice, not a tutorial overlay: no modal, no
 * dismissal, no progress. It stops being drawn the moment the conversation
 * has anything of its own to show. */

/** Openings a researcher can take as their own — loaded into the composer to
 * edit, never sent for them. Deliberately none of them is the example the
 * platform's greeting already prints a few lines above: on a phone the two sat
 * within one screen and read as the same sentence stuttering. */
const OPENINGS = [
  "Does an AI assistant change how much code developers rewrite before they ship?",
  "Compare how long debugging takes with and without an AI pair.",
  "Do developers review AI-written code as carefully as code they wrote themselves?",
];

/** The mechanism, in the order it runs. The sequence is the information here,
 * which is why these are numbered and nothing else in the app is. */
const STEPS = [
  {
    lead: "Describe the idea",
    rest: " in plain language, in the box below. The platform asks the follow-up questions a methodologist would ask.",
  },
  {
    lead: "Rule on what it proposes.",
    rest: " Each design move arrives cited into the paper corpus, or plainly labelled unsourced. Accept or reject them one at a time.",
    key: true,
  },
  {
    lead: "Compile the protocol.",
    rest: " Everything you accept is folded into the protocol draft by the compiler, not by the model. Say “finish” when you want to review the diff and apply it.",
  },
];

export function ConversationStart({ onUse }: { onUse: (text: string) => void }) {
  return (
    <section
      data-agent="conversation-start"
      aria-label="How the design conversation works"
      className="flex flex-col gap-6"
    >
      <div>
        <h2 className="type-legend mb-3 text-text-muted">
          How this record gets written
        </h2>

        {/* One rule down the left edge, and the steps hang off it. */}
        <ol className="flex flex-col gap-4 border-l border-border pl-5">
          {STEPS.map((step, i) => (
            <li key={step.lead} className="relative">
              <span
                aria-hidden
                className="type-caption tabular absolute -left-5 top-0 -translate-x-1/2 bg-bg py-0.5 font-semibold text-text-muted"
              >
                {i + 1}
              </span>
              <p className="type-body text-text">
                <span className="font-semibold">{step.lead}</span>
                {step.rest}
              </p>

              {/* The two states the researcher meets first, shown where they
                * are explained rather than keyed at the foot of an empty
                * field. Grounded uses the same framed mark and score a real
                * citation chip renders (GroundingChip); unsourced uses the
                * same dashed ring MoveCard's UnsourcedLabel renders — each
                * example is the exact notation it teaches, not a stand-in. */}
              {step.key && (
                <div className="mt-2 flex flex-wrap items-center gap-x-5 gap-y-1.5">
                  <span className="flex items-center gap-1.5">
                    <Confidence value={0.86} words={false} />
                    <span className="type-caption text-text-muted">
                      a bigger dot in the same frame — stronger grounding in
                      the corpus
                    </span>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span aria-hidden className="mark-unsourced" />
                    <span className="type-caption text-text-muted">
                      unsourced — use your own judgment
                    </span>
                  </span>
                </div>
              )}
            </li>
          ))}
        </ol>
      </div>

      <div>
        <h2 className="type-legend mb-2 text-text-muted">
          Or start from one of these
        </h2>
        {/* One plate holding three ruled rows, not three plates. Each row is
          * the full hit area; the rule between them is what separates them. */}
        <ul className="divide-y divide-border overflow-hidden rounded-plate border border-border bg-surface">
          {OPENINGS.map((text) => (
            <li key={text}>
              <button
                type="button"
                onClick={() => onUse(text)}
                className="type-body group flex w-full items-start gap-2.5 px-3 py-2.5 text-left text-text transition-colors duration-fast hover:bg-zone-9"
              >
                <span
                  aria-hidden
                  className="mt-1.5 size-1.5 shrink-0 rounded-dot bg-border-strong transition-colors duration-fast group-hover:bg-accent"
                />
                {text}
              </button>
            </li>
          ))}
        </ul>
        <p className="type-caption mt-2 text-text-muted">
          Picking one fills the box. Nothing is sent until you send it.
        </p>
      </div>
    </section>
  );
}
