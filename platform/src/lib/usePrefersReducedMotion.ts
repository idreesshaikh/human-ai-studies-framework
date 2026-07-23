import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

/* Tracks the OS "reduce motion" setting for JS-driven sequences. The design
 * system already collapses *CSS* animation under prefers-reduced-motion
 * (tokens.css), but a timer-driven loop (the hero showcase) has to opt out in
 * JS too — it renders its final resting frame instead of stepping through the
 * beats. Kept tiny and dependency-free, matching the platform's no-extra-lib
 * posture. */
export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () =>
      typeof window !== "undefined" &&
      typeof window.matchMedia === "function" &&
      window.matchMedia(QUERY).matches,
  );

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(QUERY);
    const onChange = () => setReduced(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  return reduced;
}
