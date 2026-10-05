import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { useRouteTitle } from "@/lib/useDocumentTitle";
import { HeroShowcase } from "@/components/hero/HeroShowcase";

/* The public front. It doesn't run a live model any more (the old embedded
 * demo endpoint was unreliable); it *shows* the product: a deterministic,
 * self-running showcase plays the core loop  -  a question types itself, a
 * grounded design-move card folds in, its citation chips light. No account,
 * no network, nothing to break.
 *
 * The header gets one staged entrance (mark → headline → CTA); the showcase
 * carries its own motion, frozen under reduced motion. */
export function Hero() {
  useRouteTitle();
  return (
    <div className="relative mx-auto min-h-full max-w-wide px-6 pb-12 pt-4 sm:pb-16 sm:pt-6">
      {/* The way back in. This page offered exactly one door  -  "Start a
        * project"  -  so a researcher who already had an account had nothing to
        * click: signing in meant guessing a URL, being bounced to the gate,
        * and arriving at the sign-in card by accident.
        *
        * Deliberately not fills. The accent on this page means "start a
        * project", and a second filled control in the same region would make
        * neither of them the next step.
        *
        * Templates sit here too now that their route is actually public:
        * they are the one thing a visitor can do in full without an account, and
        * burying the corpus behind a sign-up was the front page's biggest
        * omission  -  15,000 papers of ranked design shapes, browsable, and
        * nothing said so. */}
      {/* One row: wordmark left, nav right (wrapping cleanly when the two do
        * not fit side by side). */}
      <header className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1">
        <div className="flex animate-in items-center gap-2.5 fade-in duration-entrance ease-out">
          <PhoenixMark size={28} />
          <span className="type-section text-text">Phoenix</span>
        </div>
        <nav aria-label="Public navigation" className="flex items-center gap-1">
          <Button asChild variant="ghost">
            <Link to="/repertoire">Browse templates</Link>
          </Button>
          <Button asChild variant="ghost">
            <Link to="/signin">Sign in</Link>
          </Button>
        </nav>
      </header>

      <main className="mt-10 flex flex-col gap-10 sm:mt-14">
        <header className="flex flex-col items-center gap-7 text-center">

          <h1 className="type-display max-w-[18ch] animate-in fade-in slide-in-from-bottom-2 text-text duration-entrance ease-out">
            Run a <span className="italic">defensible</span> developer study
          </h1>

        {/* `text-balance`: centred and left to wrap, this set four lines with
          * a hard-ragged right edge and the single word "protocol." alone on
          * the last one  -  an orphan under a display headline is the one
          * typographic slip a reader registers as sloppiness without being
          * able to name it. Balanced, the four lines come out even and
          * nothing is stranded. */}
          <p className="type-body-lg max-w-[52ch] animate-in text-balance fade-in text-text-muted delay-100 duration-entrance ease-out">
            Phoenix configures task-based <span className="whitespace-nowrap">human–AI</span> studies in VS Code. Describe
            the coding task, comparison, and outcome, then review a protocol
            before optionally collecting the developer session data.
          </p>

          <div className="flex animate-in flex-col items-center gap-2 fade-in delay-150 duration-entrance ease-out sm:flex-row">
            <Button asChild>
              <Link to="/start">
                Configure a developer study <ArrowRight aria-hidden />
              </Link>
            </Button>
          </div>
        </header>

      {/* Continues the header's own staged reveal (mark, then headline, then
        * subhead, then the CTA row) one beat further, so the showcase arrives
        * as the cascade's own next step rather than being pre-rendered before
        * the header has finished settling. One entrance, once, on mount; the
        * showcase's internal loop then carries its own motion indefinitely. */}
        <section
          aria-label="How the design conversation works"
          className="mx-auto w-full max-w-3xl animate-in fade-in slide-in-from-bottom-2 delay-200 duration-entrance ease-out"
        >
          <HeroShowcase />
        </section>
      </main>
    </div>
  );
}
