import { BookOpen } from "lucide-react";
import { RecommendationCard } from "./RecommendationCard";
import type { Recommendation } from "@/lib/types";

/* The live literature recommender (FR-LIT-9). The persistent home for papers
 * the conversation surfaces — it refreshes as the conversation grows, ranked
 * by confidence + relevance (no provenance tier). One click adds a paper to
 * the study's Library. This is the single "add a paper" affordance; the
 * inline per-turn cards are gone so there's one mental model. */
export function RecommenderRail({
  recommendations,
  addedRefs,
  onAdd,
}: {
  recommendations: Recommendation[];
  addedRefs: Set<string>;
  onAdd: (ref: string) => void;
}) {
  return (
    <aside
      data-agent="recommender-rail"
      className="flex h-full min-h-0 flex-col gap-stack bg-surface p-gutter"
    >
      <div>
        <h2 className="type-subhead flex items-center gap-2 text-text">
          <BookOpen className="size-4 text-accent" aria-hidden /> Literature
        </h2>
        <p className="text-xs text-text-muted">
          Papers the conversation surfaces, ranked by confidence. Add any to your library.
        </p>
      </div>

      {recommendations.length === 0 ? (
        <p className="rounded-input border border-dashed border-border px-3 py-6 text-center text-xs text-text-muted">
          As you describe your study, relevant papers appear here — grounded in the corpus.
        </p>
      ) : (
        <div className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto">
          {recommendations.map((r) => (
            <RecommendationCard
              key={r.ref}
              rec={r}
              added={addedRefs.has(r.ref) || Boolean(r.inStudy)}
              onAdd={onAdd}
            />
          ))}
        </div>
      )}
    </aside>
  );
}
