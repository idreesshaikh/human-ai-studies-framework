import { Link } from "react-router-dom";
import { ArrowRight, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConversationView } from "@/components/conversation/ConversationView";

/* The public front. It doesn't describe the product — it runs it: the
 * conversation below is live, on the offline demo script, so a visitor
 * watches design moves arrive and fills a protocol draft without an account
 * or an API key. Dressed as a powered-on research terminal. */
export function Hero() {
  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col items-center gap-5 text-center">
        <span className="inline-flex items-center gap-2 rounded-chip border-2 border-border-strong bg-accent-soft px-3 py-1 font-display text-xs font-bold uppercase tracking-widest text-accent shadow-brutal-sm">
          <Terminal className="size-3.5" aria-hidden />
          Research Terminal · no LLM key required
        </span>

        <h1 className="max-w-3xl font-display text-4xl font-bold uppercase leading-[1.05] tracking-tight text-text sm:text-5xl">
          Talk your <span className="text-accent">study</span>
          <br />
          into existence
          <span className="cursor-block ml-1 text-accent" aria-hidden />
        </h1>

        <p className="max-w-xl font-sans text-base leading-relaxed text-text-muted">
          Describe a rigorous human-AI study in plain words. The platform
          proposes design moves grounded in the research literature — accept the
          ones you want, and it compiles them into a citable protocol.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button asChild>
            <Link to="/demo">
              <ArrowRight aria-hidden /> Open the demo project
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/projects">Start your own</Link>
          </Button>
        </div>
      </header>

      <section aria-label="Live design conversation" className="flex flex-col gap-2">
        <div className="overflow-hidden rounded-card border-2 border-border-strong bg-surface shadow-brutal-lg">
          {/* Console title bar — window chrome, boxy traffic lights. */}
          <div className="flex items-center justify-between gap-3 border-b-2 border-border-strong bg-bg px-3 py-2">
            <span className="font-display text-xs font-bold uppercase tracking-wider text-text-muted">
              design.session — live
            </span>
            <span className="flex items-center gap-1.5" aria-hidden>
              <span className="size-3 rounded-chip border-2 border-border-strong bg-accent" />
              <span className="size-3 rounded-chip border-2 border-border-strong bg-unsourced" />
              <span className="size-3 rounded-chip border-2 border-border-strong bg-grounded" />
            </span>
          </div>
          <p className="border-b-2 border-border bg-surface px-4 py-2 text-center font-mono text-xs text-text-muted">
            &gt; this conversation is live — try typing{" "}
            <span className="text-accent">“junior developers over-trust AI code”</span>
          </p>
          <div className="crt-scanlines h-[32rem]">
            <ConversationView />
          </div>
        </div>
      </section>
    </div>
  );
}
