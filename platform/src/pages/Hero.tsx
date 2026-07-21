import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConversationView } from "@/components/conversation/ConversationView";

/* The public front. It doesn't describe the product — it runs it: the
 * conversation below is a scripted preview (deliberately deterministic, no
 * account needed), so a visitor watches design moves arrive and fills a
 * protocol draft with nothing to sign up for. A real, connected study talks
 * to whichever LLM the researcher configures (FR-CONV-1.4) — the preview
 * intentionally doesn't oversell that with a fake "AI" flourish here. */
export function Hero() {
  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col items-center gap-5 text-center">
        <h1 className="max-w-3xl font-serif text-4xl font-medium leading-[1.08] tracking-tight text-text sm:text-6xl">
          Talk your <span className="italic text-accent">study</span> into
          existence
        </h1>

        <p className="max-w-xl text-lg leading-relaxed text-text-muted">
          Describe the study you have in mind, in plain language. As you talk,
          the platform suggests design moves drawn from the research literature.
          Keep the ones that fit, and it writes them up as a protocol you can
          cite.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button asChild>
            <Link to="/demo">
              <ArrowRight aria-hidden /> See a finished study
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/projects">Start your own</Link>
          </Button>
        </div>
      </header>

      <section aria-label="Design conversation" className="flex flex-col gap-2">
        <div className="overflow-hidden rounded-card border border-border-strong bg-surface shadow-brutal-lg">
          {/* Panel header — a quiet label strip. */}
          <div className="border-b border-border bg-surface-raised px-4 py-2.5">
            <span className="font-mono text-xs font-medium tracking-wide text-text-muted">
              Design session
            </span>
          </div>
          <p className="border-b border-border bg-surface px-4 py-2.5 text-center text-sm text-text-muted">
            No account needed to try this — it's a scripted preview below.
            Start your own study and the conversation runs live, guided by
            whichever LLM you connect. Try typing something like{" "}
            <span className="font-medium text-accent">
              “junior developers over-trust AI code”
            </span>
          </p>
          <div className="h-[50vh] min-h-[20rem] max-h-[32rem]">
            <ConversationView stubOnly />
          </div>
        </div>
      </section>
    </div>
  );
}
