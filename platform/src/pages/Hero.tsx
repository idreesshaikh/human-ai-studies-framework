import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { KiteMark } from "@/components/brand/KiteMark";
import { Constellation } from "@/components/brand/Constellation";
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
    <div className="relative mx-auto flex min-h-full max-w-wide flex-col gap-12 px-6 py-16 sm:py-20">
      {/* Ambient artwork, behind everything and non-interactive. */}
      <Constellation className="pointer-events-none absolute inset-0 -z-10 h-full w-full opacity-70" />

      <header className="flex flex-col items-center gap-6 text-center">
        <div className="animate-in fade-in duration-entrance ease-out">
          <KiteMark size={40} />
        </div>

        <h1 className="type-display max-w-2xl animate-in fade-in slide-in-from-bottom-2 text-text duration-entrance ease-out">
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
        </div>
      </header>

      <section aria-label="How the design conversation works" className="mx-auto w-full max-w-2xl">
        <HeroShowcase />
      </section>
    </div>
  );
}
