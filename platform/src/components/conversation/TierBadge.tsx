import { Badge } from "@/components/ui/badge";
import type { Tier } from "@/lib/types";

/* Shows a paper's provenance wherever it appears: A = filled dot,
 * B = ring, study = star. */
const GLYPH: Record<Tier, string> = { A: "●", B: "◌", study: "★" };
const LABEL: Record<Tier, string> = {
  A: "Tier A seed",
  B: "Tier B harvest",
  study: "In this study",
};

export function TierBadge({ tier }: { tier: Tier }) {
  return (
    <Badge variant="outline" aria-label={LABEL[tier]}>
      <span aria-hidden>{GLYPH[tier]}</span>
      {tier === "study" ? "study" : `Tier ${tier}`}
    </Badge>
  );
}
