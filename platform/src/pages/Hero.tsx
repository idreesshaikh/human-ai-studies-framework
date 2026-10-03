import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PhoenixMark } from "@/components/brand/PhoenixMark";
import { HeroShowcase } from "@/components/hero/HeroShowcase";

export function Hero() {
  return (
    <div className="relative mx-auto min-h-full max-w-wide px-6 py-16 sm:py-24">

      <nav
        aria-label="Public navigation"
        className="absolute right-6 top-6 z-10 flex items-center gap-1"
      >
        <Button asChild variant="ghost">
          <Link to="/repertoire">Browse the repertoire</Link>
        </Button>
        <Button asChild variant="ghost">
          <Link to="/signin">Sign in</Link>
        </Button>
      </nav>

      <main className="flex flex-col gap-14">
        <header className="flex flex-col items-center gap-7 text-center">
          <div className="flex animate-in items-center gap-2.5 fade-in duration-entrance ease-out">
            <PhoenixMark size={34} />
            <span className="type-section text-text">Phoenix</span>
          </div>

          <h1 className="type-display max-w-[18ch] animate-in fade-in slide-in-from-bottom-2 text-text duration-entrance ease-out">
            Run a <span className="italic">defensible</span> developer study
          </h1>

          <p className="type-body-lg max-w-[52ch] animate-in text-balance fade-in text-text-muted delay-100 duration-entrance ease-out">
            Phoenix configures task-based human–AI studies in VS Code. Describe
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
