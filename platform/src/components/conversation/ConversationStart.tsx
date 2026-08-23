/* Empty state for a new study. It answers only the question the researcher
 * has right now; methodology, evidence, and protocol details appear when they
 * become relevant instead of arriving as a wall before the first turn. */

const OPENINGS = [
  "Does an AI assistant change how much code developers rewrite before they ship?",
  "Compare how long debugging takes with and without an AI pair.",
  "Do developers review AI-written code as carefully as code they wrote themselves?",
];

export function ConversationStart({ onUse }: { onUse: (text: string) => void }) {
  return (
    <section data-agent="conversation-start" aria-label="Start the design session" className="max-w-reading">
      <p className="type-legend text-accent">START HERE</p>
      <h2 className="mt-2 type-section text-text">What do you want to find out?</h2>
      <p className="mt-2 max-w-[52ch] type-body text-text-muted">
        Describe the study in your own words. I’ll ask one follow-up at a time and keep the protocol beside you.
      </p>

      <div className="mt-6">
        <p className="type-caption text-text-muted">Try an example</p>
        <ul className="mt-2 divide-y divide-border overflow-hidden rounded-plate border border-border bg-surface">
          {OPENINGS.map((text) => (
            <li key={text}>
              <button
                type="button"
                onClick={() => onUse(text)}
                className="type-body group flex w-full items-start gap-2.5 px-3 py-3 text-left text-text transition-colors duration-fast hover:bg-zone-9"
              >
                <span aria-hidden className="mt-2 size-1.5 shrink-0 rounded-dot bg-border-strong transition-colors duration-fast group-hover:bg-accent" />
                <span>{text}</span>
              </button>
            </li>
          ))}
        </ul>
        <p className="mt-2 type-caption text-text-muted">Examples fill the composer; nothing is sent until you press send.</p>
      </div>
    </section>
  );
}
