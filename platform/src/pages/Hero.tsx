import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConversationView } from "@/components/conversation/ConversationView";
import { KiteMark } from "@/components/brand/KiteMark";

/* The public front. It doesn't describe the product, it runs it: the
 * conversation below is the real design assistant (the rate-limited,
 * stateless /demo endpoint, FR-CONV-1.4) — a visitor types a real idea and
 * gets a real, corpus-grounded reply with no account. Nothing they type is
 * stored. If the demo endpoint is unreachable it falls back to the scripted
 * assistant, so the page always runs.
 *
 * The header gets one staged entrance (mark, then headline, then the CTA) —
 * the only motion this page spends; the panel below just runs. "Grounded" in
 * the subhead borrows the app's own accent for cited moves (tokens.css),
 * so the color already means something before a researcher has seen it. */
export function Hero() {
  return (
    <div className="mx-auto flex min-h-full max-w-5xl flex-col gap-12 px-6 py-16 sm:py-20">
      <header className="flex flex-col items-center gap-6 text-center">
        <div className="animate-in fade-in duration-entrance ease-out">
          <KiteMark size={40} />
        </div>

        <h1 className="max-w-2xl animate-in fade-in slide-in-from-bottom-2 font-serif text-5xl font-medium leading-[1.05] tracking-tight text-text duration-entrance ease-out sm:text-6xl">
          Talk your <span className="italic text-accent">study</span> into
          existence
        </h1>

        <p className="max-w-lg animate-in fade-in text-lg leading-relaxed text-text-muted delay-100 duration-entrance ease-out">
          Describe a research idea, in plain language. Phoenix proposes
          design moves{" "}
          <span className="font-medium text-grounded">grounded</span> in a
          1,000+ paper corpus, cited, never invented, and compiles what you
          keep into a protocol.
        </p>

        <div className="flex animate-in flex-col items-center gap-2 fade-in delay-150 duration-entrance ease-out">
          <Button asChild>
            <Link to="/home">
              Start a project <ArrowRight aria-hidden />
            </Link>
          </Button>
          <p className="text-xs text-text-muted">
            Free to try below. No account needed.
          </p>
        </div>
      </header>

      <section aria-label="Design conversation" className="flex flex-col gap-2">
        <div className="overflow-hidden rounded-card border border-border-strong bg-surface shadow-brutal-lg">
          {/* Panel header — a quiet label strip, live dot instead of a
              disclaimer paragraph; the opening turn below already invites a
              real example, so the copy up here doesn't repeat it. */}
          <div className="flex items-center gap-2 border-b border-border bg-surface-raised px-4 py-2.5">
            <span
              className="size-1.5 shrink-0 animate-pulse rounded-full bg-grounded"
              aria-hidden
            />
            <span className="font-mono text-xs font-medium tracking-wide text-text-muted">
              Design session
            </span>
            <span className="ml-auto hidden font-mono text-[0.6875rem] text-text-muted sm:inline">
              live, no account needed
            </span>
          </div>
          <div className="h-[55vh] min-h-[22rem] max-h-[34rem]">
            <ConversationView demo />
          </div>
        </div>
      </section>
    </div>
  );
}
