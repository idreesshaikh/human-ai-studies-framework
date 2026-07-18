import { Link } from "react-router-dom";
import { ArrowRight, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ConversationView } from "@/components/conversation/ConversationView";

/* The public front. It doesn't describe the product — it runs it: the
 * conversation below is live, on the offline demo script, so a visitor
 * watches design moves arrive and fills a protocol draft without an account
 * or an API key. */
export function Hero() {
  return (
    <div className="mx-auto flex min-h-full max-w-6xl flex-col gap-8 px-6 py-10">
      <header className="flex flex-col items-center gap-4 text-center">
        <span className="inline-flex items-center gap-1 rounded-chip bg-accent-soft px-3 py-1 text-xs text-accent">
          <Sparkles className="size-3.5" aria-hidden />
          Talk your study into existence
        </span>
        <h1 className="max-w-2xl font-display text-4xl leading-tight text-text">
          Design a rigorous human-AI study by describing what you want to know.
        </h1>
        <p className="max-w-xl text-text-muted">
          Describe your idea in plain words. The platform proposes design
          moves grounded in the research literature, and compiles the ones you
          accept into a citable study protocol.
        </p>
        <div className="flex flex-wrap items-center justify-center gap-3">
          <Button asChild>
            <Link to="/demo">
              Open the demo project <ArrowRight aria-hidden />
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/projects">Start your own</Link>
          </Button>
        </div>
      </header>

      <section aria-label="Live design conversation" className="flex flex-col gap-2">
        <p className="text-center text-xs text-text-muted">
          This conversation is live — try typing “junior developers over-trust
          AI code”.
        </p>
        <div className="h-[32rem] overflow-hidden rounded-card border border-border shadow-sm">
          <ConversationView />
        </div>
      </section>
    </div>
  );
}
