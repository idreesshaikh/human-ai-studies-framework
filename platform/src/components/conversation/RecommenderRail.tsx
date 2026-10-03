import { RecommendationCard } from "./RecommendationCard";
import { EmptyState } from "@/components/shell/EmptyState";
import type { Recommendation } from "@/lib/types";

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
      className="flex h-full min-h-0 flex-col gap-stack bg-surface p-gutter"
    >
      <div>
        <h2 className="type-subhead flex items-center gap-2 text-text">
          Literature
        </h2>
        <p className="type-caption text-text-muted">
          Study-specific matches appear first. A paper is evidence for a design move only when its relevance is clear.
        </p>
      </div>

      {recommendations.length === 0 ? (
        <EmptyState line="No close study-specific matches yet. Describe the participants, task, comparison, or outcome and the corpus will look for papers with that vocabulary." />
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
