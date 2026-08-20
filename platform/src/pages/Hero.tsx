import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { ObservatoryField } from "@/components/brand/ObservatoryField";
import { HeroShowcase } from "@/components/hero/HeroShowcase";

/* The public front. It doesn't run a live model any more (the old embedded
 * demo endpoint was unreliable); it *shows* the product. Behind the headline, a
 * quiet "living literature constellation" drifts — the platform's own metaphor
 * — and below it a deterministic, self-running showcase plays the core loop:
 * a question types itself, a grounded design-move card folds in, its citation
 * chips light. No account, no network, nothing to break.
 *
 * The header gets one staged entrance (mark → headline → CTA); the constellation
 * and showcase carry their own motion, both frozen under reduced motion. */
export function Hero() {
  return (
    <div className="relative mx-auto flex min-h-full max-w-wide flex-col gap-14 px-6 py-16 sm:py-24">
      {/* Ambient artwork, behind everything and non-interactive. */}
      <ObservatoryField className="pointer-events-none absolute inset-0 -z-10 h-full w-full" />

      <header className="flex flex-col items-center gap-7 text-center">
        <div className="flex animate-in items-center gap-2.5 fade-in duration-entrance ease-out">
          <PhoenixMark size={34} />
          <span className="type-section text-text">Phoenix</span>
        </div>

        <h1 className="type-display max-w-[18ch] animate-in fade-in slide-in-from-bottom-2 text-text duration-entrance ease-out">
          Talk your <span className="italic">study</span> into existence
        </h1>

        <p className="type-body-lg max-w-[52ch] animate-in fade-in text-text-muted delay-100 duration-entrance ease-out">
          Describe a research idea, in plain language. Phoenix proposes
          design moves{" "}
          <span className="font-semibold text-text">grounded</span> in the
          published literature, each one cited or plainly marked unsourced, and
          compiles the ones you keep into a protocol.
        </p>

        <div className="flex animate-in flex-col items-center gap-2 fade-in delay-150 duration-entrance ease-out sm:flex-row">
          <Button asChild>
            <Link to="/home">
              Start a project <ArrowRight aria-hidden />
            </Link>
          </Button>
          {/* The repertoire is the other way in: a researcher who already
           * knows the shape they want (or wants to see what the corpus
           * actually supports) starts from proven designs instead of a blank
           * conversation. */}
          <Button variant="outline" asChild>
            <Link to="/repertoire">
              Browse proven designs <ArrowRight aria-hidden />
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
