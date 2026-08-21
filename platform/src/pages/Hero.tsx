import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { HeroShowcase } from "@/components/hero/HeroShowcase";

/* The public front. It doesn't run a live model any more (the old embedded
 * demo endpoint was unreliable); it *shows* the product: a deterministic,
 * self-running showcase plays the core loop — a question types itself, a
 * grounded design-move card folds in, its citation chips light. No account,
 * no network, nothing to break.
 *
 * The header gets one staged entrance (mark → headline → CTA); the showcase
 * carries its own motion, frozen under reduced motion. */
export function Hero() {
  return (
    <div className="relative mx-auto flex min-h-full max-w-wide flex-col gap-14 px-6 py-16 sm:py-24">
      {/* The way back in. This page offered exactly one door — "Start a
        * project" — so a researcher who already had an account had nothing to
        * click: signing in meant guessing a URL, being bounced to the gate,
        * and arriving at the sign-in card by accident.
        *
        * Deliberately not fills. The accent on this page means "start a
        * project", and a second filled control in the same region would make
        * neither of them the next step.
        *
        * The repertoire sits here too now that its route is actually public:
        * it is the one thing a visitor can do in full without an account, and
        * burying the corpus behind a sign-up was the front page's biggest
        * omission — 15,000 papers of ranked design shapes, browsable, and
        * nothing said so. */}
      <div className="absolute right-6 top-6 z-10 flex items-center gap-1">
        <Button asChild variant="ghost" size="sm">
          <Link to="/repertoire">Browse the repertoire</Link>
        </Button>
        <Button asChild variant="ghost" size="sm">
          <Link to="/signin">Sign in</Link>
        </Button>
      </div>

      <header className="flex flex-col items-center gap-7 text-center">
        <div className="flex animate-in items-center gap-2.5 fade-in duration-entrance ease-out">
          <PhoenixMark size={34} />
          <span className="type-section text-text">Phoenix</span>
        </div>

        <h1 className="type-display max-w-[18ch] animate-in fade-in slide-in-from-bottom-2 text-text duration-entrance ease-out">
          Talk your <span className="italic">study</span> into existence
        </h1>

        {/* `text-balance`: centred and left to wrap, this set four lines with
          * a hard-ragged right edge and the single word "protocol." alone on
          * the last one — an orphan under a display headline is the one
          * typographic slip a reader registers as sloppiness without being
          * able to name it. Balanced, the four lines come out even and
          * nothing is stranded. */}
        <p className="type-body-lg max-w-[52ch] animate-in text-balance fade-in text-text-muted delay-100 duration-entrance ease-out">
          Describe a research idea, in plain language. Phoenix proposes
          design moves{" "}
          <span className="font-semibold text-text">grounded</span> in the
          published literature, each one cited or plainly marked unsourced, and
          compiles the ones you keep into a protocol.
        </p>

        <div className="flex animate-in flex-col items-center gap-2 fade-in delay-150 duration-entrance ease-out sm:flex-row">
          <Button asChild>
            <Link to="/start">
              Start a project <ArrowRight aria-hidden />
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
    </div>
  );
}
