import { useEffect, useState } from "react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { Confidence } from "@/components/conversation/Confidence";

const QUESTION = "Do developers over-trust AI-written code?";
const PROPOSAL =
  "Randomise AI-authorship disclosure; measure trust calibration against the actual defect rate.";
const A11Y_LABEL =
  "A developer study setup: from the question “Do developers over-trust AI-written code?”, " +
  "Phoenix proposes a between-subjects design move, grounded in the METR 2025 and " +
  "Ziegler 2022 studies. Accepted, it lands in the protocol draft as the design section.";

const DRAFT_SLOTS = 8;

type Stage = "idle" | "thinking" | "move" | "grounded" | "compiled";

export function HeroShowcase() {
  const reduced = usePrefersReducedMotion();
  const [typed, setTyped] = useState("");
  const [stage, setStage] = useState<Stage>("idle");

  useEffect(() => {
    if (reduced) {

      setTyped(QUESTION);
      setStage("compiled");
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
        await sleep(450);
        if (cancelled) break;
        setStage("thinking");
        await sleep(900);
        if (cancelled) break;
        setStage("move");
        await sleep(1100);
        if (cancelled) break;
        setStage("grounded");
        await sleep(1500);
        if (cancelled) break;
        setStage("compiled");
        await sleep(2600);
      }
    })();

    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [reduced]);

  const showMove = stage === "move" || stage === "grounded" || stage === "compiled";
  const grounded = stage === "grounded" || stage === "compiled";
  const compiled = stage === "compiled";

  return (
    <div
      role="img"
      aria-label={A11Y_LABEL}
      className="overflow-hidden rounded-card border border-border-strong bg-surface shadow-lifted"
    >

      <div
        aria-hidden
        className="flex items-center gap-2 border-b border-border bg-surface-raised px-4 py-2.5"
      >
        <span className="size-1.5 shrink-0 animate-pulse rounded-full bg-grounded" />
        <span className="type-legend text-text-muted">
          Developer study setup
        </span>
        <span className="ml-auto type-legend text-text-muted">
          every move cited
        </span>
      </div>

      <div aria-hidden className="flex min-h-64 flex-col gap-4 p-5 sm:p-6">

        <div className="flex items-start gap-2 type-quantity">
          <span className="select-none text-accent">&gt;</span>
          <span className="text-text">
            {typed}
            {stage === "idle" && <span className="cursor-block" />}
          </span>
        </div>

        {stage === "thinking" && (
          <div className="inline-flex items-center gap-1">
            <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
            <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
            <span className="size-1.5 animate-pulse rounded-full bg-text-muted" />
          </div>
        )}

        {showMove && (
          <div className="hero-fold-in border-t border-border pt-4">
            <div className="flex items-center gap-2">
              <span className="type-legend text-text-muted">Design move</span>
              <span className="type-caption text-text-muted">between-subjects</span>
            </div>
            <p className="mt-1.5 type-body leading-relaxed text-text">{PROPOSAL}</p>

            {grounded && (
              <div className="hero-glow-in mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                <span className="inline-flex items-center gap-1.5">
                  <Confidence value={0.93} words={false} />
                  <span className="type-caption text-text-muted">
                    strongly grounded
                  </span>
                </span>
                <span className="type-caption rounded-chip border border-border px-2 py-0.5 text-text">
                  METR 2025
                </span>
                <span className="type-caption rounded-chip border border-border px-2 py-0.5 text-text">
                  Ziegler 2022
                </span>
              </div>
            )}

            <div
              className={compiled ? "mt-4 flex items-center gap-2 opacity-70" : "mt-4 flex items-center gap-2"}
            >
              {compiled ? (
                <span className="type-legend text-grounded">in draft</span>
              ) : (
                <>
                  <span className="type-control rounded-control border border-control-edge px-3 py-1 text-text">
                    Accept
                  </span>
                  <span className="type-control rounded-control border border-transparent px-3 py-1 text-text-muted">
                    Reject
                  </span>
                </>
              )}
            </div>

            {compiled && (
              <div className="hero-glow-in mt-4 flex items-center gap-2.5 border-t border-border pt-3">
                <div className="flex gap-1" aria-hidden>
                  {Array.from({ length: DRAFT_SLOTS }).map((_, i) => (
                    <span
                      key={i}
                      className={
                        i === 0
                          ? "size-2.5 rounded-chip border border-transparent bg-ink"
                          : "size-2.5 rounded-chip border border-border-strong bg-transparent"
                      }
                    />
                  ))}
                </div>
                <span className="type-caption text-text">
                  Design <span className="text-grounded">in draft</span>
                </span>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
