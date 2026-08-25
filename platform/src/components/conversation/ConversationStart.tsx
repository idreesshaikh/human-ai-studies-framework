/* Empty state for a new developer study. The supported lane is stated before
 * anyone commits to a long conversation, so a general research idea can be
 * redirected without entering the protocol loop. */

const OPENINGS = [
  "Does an AI assistant change how much code developers rewrite before they ship?",
  "Compare how long debugging takes with and without an AI pair.",
  "Do developers review AI-written code as carefully as code they wrote themselves?",
];

export function ConversationStart({ onUse }: { onUse: (text: string) => void }) {
  return (
    <section data-agent="conversation-start" aria-label="Start the developer study setup" className="max-w-reading">
      <p className="type-legend text-accent">DEVELOPER STUDY SETUP</p>
      <h2 className="mt-2 type-section text-text">What do you want to run?</h2>
      <p className="mt-2 max-w-[52ch] type-body text-text-muted">
        PHOENIX configures task-based human–AI studies in VS Code. Give me the coding task, the AI comparison, and the outcome. I’ll turn it into a runnable protocol.
      </p>

      <p
        data-agent="study-scope"
        className="mt-4 max-w-[58ch] border-l-2 border-accent pl-3 type-caption text-text-muted"
      >
        Students are supported when they are programming. Other study types belong outside this workspace.
      </p>

      <div
        data-agent="study-overview"
        className="mt-6 grid max-w-[58ch] gap-4 rounded-card border border-border bg-surface p-4 sm:grid-cols-3"
      >
        <div>
          <p className="type-legend text-accent">1 · CONFIGURE</p>
          <p className="mt-1 type-caption text-text-muted">Describe the coding task, comparison, and outcome in whatever order is natural.</p>
        </div>
        <div>
          <p className="type-legend text-accent">2 · REVIEW</p>
          <p className="mt-1 type-caption text-text-muted">The draft shows what was extracted, what is recommended, and what remains open.</p>
        </div>
        <div>
          <p className="type-legend text-accent">3 · RUN</p>
          <p className="mt-1 type-caption text-text-muted">Optionally mint blinded VS Code links and collect the developer session data.</p>
        </div>
      </div>

      <p className="mt-4 max-w-[58ch] type-caption text-text-muted">
        Supported lane: comparative coding-task studies, such as AI-assisted versus unassisted work, using TERN-captured developer activity. Protocol design can still be used without collecting data here.
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
