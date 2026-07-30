import type { Understanding } from "@/lib/types";

/* Why no design has been proposed yet (FR-CONV-10).
 *
 * The platform withholds a design shape until the study is understood, and a
 * withheld thing that isn't explained just looks like a platform that can't
 * do it. So it says what it still doesn't know, in the researcher's terms
 * ("what is compared", not "conditions[] is empty"). Once the shape can
 * honestly follow from the conversation, this disappears rather than
 * congratulating anyone. */
export function UnderstandingLine({ understanding }: { understanding?: Understanding }) {
  if (!understanding || understanding.readyForDesign) return null;
  const missing = understanding.missingLabels;
  if (missing.length === 0) return null;

  return (
    <p
      className="px-4 pb-2 text-xs text-text-muted sm:px-6"
      data-agent="understanding-line"
    >
      Still working out {missing.join(", ")}; I'll hold off on suggesting a
      design until the shape of the study follows from what you've told me.
    </p>
  );
}
