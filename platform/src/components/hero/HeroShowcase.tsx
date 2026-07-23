import { useEffect, useState } from "react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

/* The hero's thesis, running by itself: the platform's core loop played out as
 * a deterministic, no-LLM showcase. A researcher's question types itself, a
 * grounded design-move card folds in, and its citation chips light — the exact
 * gesture the real design conversation makes, but scripted, so it never breaks
 * (the old hero embedded a live demo endpoint that did). Everything visible is
 * fixed copy — real corpus references, not a live retrieval — so nothing here
 * makes a network call.
 *
 * Motion is JS-timed, so it opts out of animation under reduced motion by
 * rendering its final resting frame (see usePrefersReducedMotion). The whole
 * thing is one `role="img"` with a plain-language label, so assistive tech gets
 * a single clear description instead of the animating fragments. */

const QUESTION = "Do developers over-trust AI-written code?";
const PROPOSAL =
  "Randomise AI-authorship disclosure; measure trust calibration against the actual defect rate.";
const A11Y_LABEL =
  "A design session: from the question “Do developers over-trust AI-written code?”, " +
  "Phoenix proposes a between-subjects design move, grounded in the METR 2025 and " +
  "Ziegler 2022 studies.";

type Stage = "idle" | "thinking" | "move" | "grounded";

export function HeroShowcase() {
  const reduced = usePrefersReducedMotion();
  const [typed, setTyped] = useState("");
  const [stage, setStage] = useState<Stage>("idle");

  useEffect(() => {
    if (reduced) {
      // Reduced motion: skip straight to the settled final frame.
      setTyped(QUESTION);
      setStage("grounded");
      return;
    }
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const sleep = (ms: number) =>
      new Promise<void>((resolve) => {
        timer = setTimeout(resolve, ms);
      });

    void (async () => {
      while (!cancelled) {
        setTyped("");
        setStage("idle");
        await sleep(700);
        if (cancelled) break;
        for (let i = 1; i <= QUESTION.length; i++) {
          if (cancelled) break;
          setTyped(QUESTION.slice(0, i));
          await sleep(42);
        }
        if (cancelled) break;
        await sleep(500);
        if (cancelled) break;
        setStage("thinking");
        await sleep(950);
        if (cancelled) break;
        setStage("move");
        await sleep(1500);
        if (cancelled) break;
        setStage("grounded");
        await sleep(3400);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [reduced]);

  const showMove = stage === "move" || stage === "grounded";

  return (
    <div
      role="img"
      aria-label={A11Y_LABEL}
      className="overflow-hidden rounded-card border border-border-strong bg-surface shadow-brutal-lg"
    >
      {/* Label strip — a live design session, not a disclaimer. */}
      <div
        aria-hidden
        className="flex items-center gap-2 border-b border-border bg-surface-raised px-4 py-2.5"
      >
        <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-grounded" />
        <span className="font-mono text-xs font-medium tracking-wide text-text-muted">
          Design session
        </span>
        <span className="ml-auto font-mono text-[0.6875rem] text-text-muted">
          grounded in 1,000+ papers
        </span>
      </div>

      <div aria-hidden className="flex min-h-64 flex-col gap-4 p-5 sm:p-6">
        {/* The researcher's question, typing itself. */}
        <div className="flex items-start gap-2 font-mono text-sm">
          <span className="select-none text-accent">&gt;</span>
          <span className="text-text">
            {typed}
            {stage === "idle" && <span className="cursor-block" />}
          </span>
        </div>

        {/* Platform thinking. */}
        {stage === "thinking" && (
          <div className="inline-flex items-center gap-1">
            <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
            <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
            <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
          </div>
        )}

        {/* The proposed design move, folding into place. */}
        {showMove && (
          <div className="hero-fold-in rounded-card border border-border-strong bg-surface-raised p-4 shadow-brutal">
            <div className="flex items-center gap-2">
              <span className="rounded-chip bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent">
                between-subjects
              </span>
              <span className="font-mono text-xs text-text-muted">design move</span>
            </div>
            <p className="mt-2 text-sm leading-relaxed text-text">{PROPOSAL}</p>

            {/* Grounding lights once the move has landed. */}
            {stage === "grounded" && (
              <div className="hero-glow-in mt-3 flex flex-wrap items-center gap-2">
                <span className="inline-flex items-center gap-1 text-xs font-medium text-grounded">
                  <span className="size-1.5 rounded-full bg-grounded" />
                  grounded
                </span>
                <span className="rounded-chip bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent">
                  METR 2025
                </span>
                <span className="rounded-chip bg-accent-soft px-2 py-0.5 font-mono text-xs text-accent">
                  Ziegler 2022
                </span>
                <span className="text-xs text-text-muted">
                  cited into the corpus, never invented
                </span>
              </div>
            )}

            {/* The researcher's call — accept or reject (illustrative). */}
            <div className="mt-4 flex gap-2">
              <span className="rounded-input border border-grounded px-2.5 py-0.5 text-xs font-medium text-grounded">
                Accept
              </span>
              <span className="rounded-input border border-border px-2.5 py-0.5 text-xs text-text-muted">
                Reject
              </span>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
