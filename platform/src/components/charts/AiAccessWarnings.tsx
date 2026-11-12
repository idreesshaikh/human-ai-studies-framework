import { Notice } from "@/components/ui/notice";
import type { AiAccessWarning } from "@/lib/plannerApi";

/* Review warnings about how a study confirms AI use or non-use. The wording
 * comes from the protocol package over the API, so it is rendered as given and
 * never rephrased here. An empty list renders nothing. */
export function AiAccessWarnings({
  warnings,
}: {
  warnings: AiAccessWarning[];
}) {
  if (warnings.length === 0) return null;
  return (
    <section aria-label="AI access review" className="flex flex-col gap-2">
      {warnings.map((w) => (
        <Notice key={`${w.code}:${w.condition ?? ""}`}>
          <div className="flex flex-col gap-1.5">
            <p>{w.message}</p>
            {w.suggestions.length > 0 && (
              <ul className="type-note flex list-disc flex-col gap-0.5 pl-4 text-text-muted">
                {w.suggestions.map((suggestion) => (
                  <li key={suggestion}>{suggestion}</li>
                ))}
              </ul>
            )}
          </div>
        </Notice>
      ))}
    </section>
  );
}
