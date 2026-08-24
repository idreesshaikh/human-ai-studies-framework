import { Plus, Check, ExternalLink } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Confidence } from "./Confidence";
import type { Recommendation } from "@/lib/types";

function sourceUrl(identifier?: string): string | null {
  if (!identifier) return null;
  if (identifier.startsWith("arXiv:")) {
    return `https://arxiv.org/abs/${identifier.slice("arXiv:".length)}`;
  }
  if (identifier.startsWith("doi:")) {
    return `https://doi.org/${identifier.slice("doi:".length)}`;
  }
  return null;
}

/* A recommended paper. Arrives with a small rise as if dealt onto the
 * table. The match reason is one sentence, always shown in full. Adding it
 * joins the paper to the study set (local-only for now). */
export function RecommendationCard({
  rec,
  added,
  onAdd,
}: {
  rec: Recommendation;
  added: boolean;
  onAdd: (ref: string) => void;
}) {
  const url = sourceUrl(rec.identifier);

  return (
    <Card
      data-agent="recommendation-card"
      data-agent-ref={rec.ref}
      className="animate-in fade-in slide-in-from-bottom-2 duration-entrance"
    >
      <CardContent className="flex flex-col gap-2 p-3">
        <div className="flex items-center justify-between gap-2">
          <div className="flex min-w-0 items-center gap-2">
            <span className="type-legend shrink-0 text-text-muted">
              {rec.matchKind === "direct" ? "Study-specific match" : "Adjacent work"}
            </span>
            <Confidence value={rec.confidence} words={false} />
            {rec.inStudy && (
              <span className="flex items-center gap-1 type-caption text-grounded">
                <Check className="size-3" aria-hidden /> in library
              </span>
            )}
          </div>
          <span className="tabular type-caption text-text-muted">{rec.year}</span>
        </div>
        <p className="font-medium text-text">{rec.title}</p>
        {(rec.authors?.length || rec.venue || rec.identifier) && (
          <p className="type-caption text-text-muted">
            {[
              rec.authors?.slice(0, 2).join(", "),
              rec.venue,
              rec.identifier,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        )}
        {rec.abstract && (
          <div className="border-t border-border pt-2">
            <p className="type-legend text-text-muted">Paper focus</p>
            <p className="mt-1 line-clamp-3 type-caption text-text">
              {rec.abstract}
            </p>
          </div>
        )}
        <div className="border-t border-border pt-2">
          <p className="type-legend text-text-muted">Why it surfaced</p>
          <p className="mt-1 type-body text-text">{rec.matchReason}</p>
        </div>
        <Button
          size="sm"
          variant={added ? "ghost" : "outline"}
          disabled={added}
          data-agent="add-paper"
          onClick={() => onAdd(rec.ref)}
          className="self-start"
        >
          <Plus aria-hidden />
          {added ? "In your paper set" : "Add to study"}
        </Button>
        {url && (
          <a
            className="inline-flex items-center gap-1.5 type-caption text-accent hover:underline"
            href={url}
            target="_blank"
            rel="noreferrer"
          >
            <ExternalLink className="size-3" aria-hidden />
            Open paper
          </a>
        )}
      </CardContent>
    </Card>
  );
}
