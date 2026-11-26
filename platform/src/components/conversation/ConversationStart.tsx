import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

/* Example openings: each is a question a researcher might bring, not a
 * finished brief, so the assistant's first reply shows the conversation. */
const OPENINGS = [
  ["Code rewriting", "Does an AI assistant change how much code developers rewrite before they ship?"],
  ["Debugging time", "Compare how long debugging takes with and without an AI pair."],
  ["Code review", "Do developers review AI-written code as carefully as code they wrote themselves?"],
] as const;
export function ConversationStart({
  onUse,
  onEnterManually,
  composer,
  onReviewStartingDraft,
}: {
  onUse: (text: string) => void;
  onEnterManually?: () => void;
  composer: ReactNode;
  /** Set when the study starts from a template: its protocol is already the
   *  draft, waiting to be reviewed and applied. */
  onReviewStartingDraft?: () => void;
}) {
  if (onReviewStartingDraft) {
    return (
      <section aria-label="Start from the template" className="max-w-reading">
        <h2 className="type-title text-center text-text">Your draft starts from the template</h2>
        <p className="mt-2 text-center type-note text-text-muted">
          Review it and apply it to plan, recruit and collect data. Or tell the
          assistant what to change first, in your own words.
        </p>
        <div className="mt-5 flex justify-center">
          <Button onClick={onReviewStartingDraft}>Review draft</Button>
        </div>
        <div className="mt-6">{composer}</div>
        {onEnterManually && (
          <p className="mt-5 type-note text-text-muted">
            Prefer a form?{" "}
            <button
              type="button"
              className="text-accent underline-offset-2 hover:underline"
              onClick={onEnterManually}
            >
              Edit the details directly
            </button>
          </p>
        )}
      </section>
    );
  }
  return (
    <section aria-label="Start the study design" className="max-w-reading">
      <h2 className="type-title text-center text-text">What would you like to study?</h2>
      <div className="mt-5">{composer}</div>
      <div className="mt-3 flex flex-wrap items-start justify-between gap-x-4 gap-y-1 type-note">
        <details className="text-text-muted" data-example-questions>
          <summary className="cursor-pointer rounded-control py-2 hover:text-text">Example questions</summary>
          <ul className="flex flex-wrap gap-x-4">
            {OPENINGS.map(([label, text]) => (
              <li key={label}>
                <button type="button" className="rounded-control py-2 text-accent hover:underline" onClick={(event) => {
                  event.currentTarget.closest("details")?.removeAttribute("open");
                  onUse(text);
                }}>{label}</button>
              </li>
            ))}
          </ul>
        </details>
        {onEnterManually && (
          <button
            type="button"
            className="rounded-control py-2 text-accent underline-offset-2 hover:underline"
            onClick={onEnterManually}
          >
            Enter protocol manually
          </button>
        )}
      </div>
    </section>
  );
}
