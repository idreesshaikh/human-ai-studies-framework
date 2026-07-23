import { useEffect, useState } from "react";
import { Layers, FileText, BookOpen, Loader2, X } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shell/EmptyState";
import { DeriveFromPaper } from "./DeriveFromPaper";
import {
  templatesApi,
  type TemplateSummary,
  type MergeResult,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* Compose a study from published designs (FR-TPL). Each template is a citable,
 * executable archetype; selecting two or more and merging composes them into
 * one novel protocol that stays grounded in every source paper it draws from.
 * This is the "start from the literature" path alongside the design
 * conversation. */
export function Templates() {
  const [templates, setTemplates] = useState<TemplateSummary[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [merged, setMerged] = useState<MergeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    templatesApi
      .list()
      .then(setTemplates)
      .catch((e) =>
        setError(
          e instanceof OfflineError
            ? "Start the middleware to browse the template registry."
            : "Couldn't load the templates.",
        ),
      );
  }, []);

  const toggle = (id: string) => {
    setMerged(null);
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  async function merge() {
    setBusy(true);
    setError(null);
    try {
      setMerged(await templatesApi.merge([...selected]));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't merge those templates.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div>
        <h1 className="flex items-center gap-2 font-serif text-3xl font-medium tracking-tight text-text">
          <Layers className="size-6 text-accent" aria-hidden /> Templates
        </h1>
        <p className="mt-1 text-sm text-text-muted">
          Published study designs, each citable and executable. Pick two or more
          and merge them into one novel protocol — grounded in every source paper.
        </p>
      </div>

      {error && (
        <p className="rounded-input border border-border-strong bg-unsourced-soft px-3 py-2 text-sm text-text">
          {error}
        </p>
      )}

      {templates === null && !error ? (
        <p className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Loading the registry…
        </p>
      ) : templates && templates.length === 0 ? (
        <EmptyState line="No templates in the registry yet." />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2">
          {templates?.map((t) => {
            const on = selected.has(t.id);
            return (
              <Card
                key={t.id}
                className={cn(
                  "cursor-pointer transition-colors duration-fast",
                  on ? "border-accent ring-1 ring-accent" : "hover:border-accent",
                )}
                onClick={() => toggle(t.id)}
              >
                <CardContent className="flex flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium text-text">{t.title}</span>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggle(t.id)}
                      onClick={(e) => e.stopPropagation()}
                      aria-label={`Select ${t.title}`}
                      className="mt-1"
                    />
                  </div>
                  <Badge variant="outline">{t.designType}</Badge>
                  <p className="line-clamp-3 text-xs text-text-muted">{t.description}</p>
                  <p className="flex items-center gap-1 text-xs text-text-muted">
                    <BookOpen className="size-3" aria-hidden />
                    {t.source.length} source paper{t.source.length === 1 ? "" : "s"}
                  </p>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}

      {/* Compose bar */}
      {selected.size > 0 && (
        <div className="sticky bottom-4 flex items-center gap-3 rounded-card border border-border-strong bg-surface-raised p-3 shadow-brutal">
          <span className="text-sm text-text">
            {selected.size} selected
            {selected.size < 2 && (
              <span className="text-text-muted"> — pick one more to merge</span>
            )}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button variant="ghost" size="sm" onClick={() => { setSelected(new Set()); setMerged(null); }}>
              Clear
            </Button>
            <Button size="sm" disabled={selected.size < 2 || busy} onClick={merge}>
              {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Layers className="size-4" aria-hidden />}
              Merge {selected.size}
            </Button>
          </div>
        </div>
      )}

      {merged && <MergedResult result={merged} onClose={() => setMerged(null)} />}

      {templates && templates.length > 0 && <DeriveFromPaper templates={templates} />}
    </div>
  );
}

function MergedResult({ result, onClose }: { result: MergeResult; onClose: () => void }) {
  const proto = result.protocol as {
    study?: { title?: string };
    researchQuestions?: { id: string; text: string }[];
  };
  const rqs = proto.researchQuestions ?? [];
  return (
    <div className="rounded-card border border-border-strong bg-surface p-4">
      <div className="flex items-start justify-between gap-3">
        <h2 className="flex items-center gap-2 font-serif text-lg font-medium text-text">
          <FileText className="size-5 text-accent" aria-hidden /> Merged protocol
        </h2>
        <button onClick={onClose} aria-label="Close" className="text-text-muted hover:text-text">
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <p className="mt-0.5 text-sm text-text-muted">{proto.study?.title}</p>

      <div className="mt-3">
        <p className="text-xs font-medium text-text-muted">
          Research questions ({rqs.length})
        </p>
        <ul className="mt-1 flex flex-col gap-1">
          {rqs.map((rq) => (
            <li key={rq.id} className="text-sm text-text">
              <span className="font-mono text-xs text-text-muted">{rq.id}</span> {rq.text}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3">
        <p className="text-xs font-medium text-text-muted">Grounded in</p>
        <ul className="mt-1 flex flex-col gap-1">
          {result.sources.map((s) => (
            <li key={s.templateId} className="text-xs text-text-muted">
              <span className="font-mono text-text">{s.templateId}</span> → {s.papers.join(", ")}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
