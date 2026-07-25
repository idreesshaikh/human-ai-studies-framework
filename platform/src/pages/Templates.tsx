import { useEffect, useMemo, useState } from "react";
import {
  Layers,
  FileText,
  BookOpen,
  Loader2,
  X,
  ChevronDown,
  Info,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/shell/EmptyState";
import { Confidence } from "@/components/conversation/Confidence";
import { DeriveFromPaper } from "./DeriveFromPaper";
import {
  templatesApi,
  type RepertoireEntry,
  type DesignReference,
  type MergeResult,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { cn } from "@/lib/cn";

/* The protocol repertoire (FR-TPL) — the literature read as *design shapes*
 * rather than as thirteen studies to replicate. Each shape is ranked by how
 * widely the corpus actually uses it (common → rare), the papers that used it
 * hang off it as ranked references, and picking two or more merges them into
 * one novel protocol that stays grounded in every paper it draws from. Merging
 * is the hero action, not a footnote. */

const BAND_COPY: Record<RepertoireEntry["band"], string> = {
  common: "Widely used across the corpus",
  established: "Well established in the corpus",
  rare: "Rarely used — novel territory",
};

export function Templates() {
  const [entries, setEntries] = useState<RepertoireEntry[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [merged, setMerged] = useState<MergeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    templatesApi
      .repertoire()
      .then((d) => setEntries(d.repertoire))
      .catch((e) =>
        setError(
          e instanceof OfflineError
            ? "Start the middleware to browse the repertoire."
            : "Couldn't load the repertoire.",
        ),
      );
  }, []);

  const admitted = useMemo(
    () => (entries ?? []).filter((e) => e.admitted),
    [entries],
  );
  const held = useMemo(
    () => (entries ?? []).filter((e) => !e.admitted),
    [entries],
  );

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
      setError(e instanceof Error ? e.message : "Couldn't merge those designs.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6 p-6">
      <div>
        <h1 className="flex items-center gap-2 font-serif text-3xl font-medium tracking-tight text-text">
          <Layers className="size-6 text-accent" aria-hidden /> Protocol repertoire
        </h1>
        <p className="mt-1 max-w-2xl text-sm text-text-muted">
          Proven design shapes, ranked by how widely the corpus uses them. The
          papers that used a shape are its references — pick two or more shapes
          and merge them into one novel protocol, grounded in every paper it
          draws from.
        </p>
      </div>

      {error && (
        <p className="rounded-input border border-border-strong bg-unsourced-soft px-3 py-2 text-sm text-text">
          {error}
        </p>
      )}

      {entries === null && !error ? (
        <p className="flex items-center gap-2 text-sm text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Ranking the
          repertoire against the corpus…
        </p>
      ) : entries && entries.length === 0 ? (
        <EmptyState line="No design shapes in the registry yet." />
      ) : (
        <div className="flex flex-col gap-3">
          {admitted.map((entry) => (
            <ShapeCard
              key={entry.id}
              entry={entry}
              selected={selected.has(entry.id)}
              onToggle={() => toggle(entry.id)}
            />
          ))}
        </div>
      )}

      {held.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="flex items-center gap-1.5 text-sm font-medium text-text-muted">
            <Info className="size-4" aria-hidden /> Held back
          </h2>
          <p className="text-xs text-text-muted">
            Too rare to propose without a strong source. Shown, not hidden — the
            reason is stated so you can judge it yourself.
          </p>
          {held.map((entry) => (
            <div
              key={entry.id}
              className="rounded-card border border-dashed border-border-strong p-3"
            >
              <p className="text-sm font-medium text-text">{entry.title}</p>
              <p className="mt-0.5 text-xs text-text-muted">
                {entry.admissionNote}
              </p>
            </div>
          ))}
        </section>
      )}

      {/* Compose bar — merging is the point of the page. */}
      {selected.size > 0 && (
        <div className="sticky bottom-4 flex items-center gap-3 rounded-card border border-border-strong bg-surface-raised p-3 shadow-brutal">
          <span className="text-sm text-text">
            {selected.size} shape{selected.size === 1 ? "" : "s"} selected
            {selected.size < 2 && (
              <span className="text-text-muted"> — pick one more to merge</span>
            )}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setSelected(new Set());
                setMerged(null);
              }}
            >
              Clear
            </Button>
            <Button size="sm" disabled={selected.size < 2 || busy} onClick={merge}>
              {busy ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Layers className="size-4" aria-hidden />
              )}
              Merge {selected.size}
            </Button>
          </div>
        </div>
      )}

      {merged && <MergedResult result={merged} onClose={() => setMerged(null)} />}

      {entries && entries.length > 0 && <DeriveFromPaper templates={entries} />}
    </div>
  );
}

function ShapeCard({
  entry,
  selected,
  onToggle,
}: {
  entry: RepertoireEntry;
  selected: boolean;
  onToggle: () => void;
}) {
  const [openRefs, setOpenRefs] = useState(false);
  return (
    <Card
      data-agent="design-shape"
      data-agent-ref={entry.id}
      className={cn(
        "transition-colors duration-fast",
        selected ? "border-accent ring-1 ring-accent" : "hover:border-accent",
      )}
    >
      <CardContent className="flex flex-col gap-3 p-4">
        <div className="flex items-start gap-3">
          <input
            type="checkbox"
            checked={selected}
            onChange={onToggle}
            aria-label={`Select ${entry.title} for merging`}
            className="mt-1.5"
          />
          <button
            type="button"
            onClick={onToggle}
            className="flex-1 text-left"
            aria-pressed={selected}
          >
            <span className="font-medium text-text">{entry.title}</span>
            <p className="mt-1 text-xs text-text-muted">{entry.description}</p>
          </button>
          <div className="flex shrink-0 flex-col items-end gap-1">
            <SupportBadge entry={entry} />
            <Badge variant="outline">{entry.designType}</Badge>
          </div>
        </div>

        <button
          type="button"
          onClick={() => setOpenRefs((v) => !v)}
          className="flex items-center gap-1.5 self-start text-xs text-text-muted hover:text-text"
          aria-expanded={openRefs}
        >
          <BookOpen className="size-3" aria-hidden />
          {entry.references.length} reference
          {entry.references.length === 1 ? "" : "s"}
          <ChevronDown
            className={cn(
              "size-3 transition-transform duration-fast",
              openRefs && "rotate-180",
            )}
            aria-hidden
          />
        </button>

        {openRefs && (
          <ul className="flex flex-col gap-2 border-l border-border pl-3">
            {entry.references.map((ref) => (
              <ReferenceRow key={ref.ref} reference={ref} />
            ))}
            {entry.unresolvedSources.length > 0 && (
              <li className="text-xs text-text-muted">
                Cited but not in the corpus:{" "}
                <span className="font-mono">
                  {entry.unresolvedSources.join(", ")}
                </span>
              </li>
            )}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function SupportBadge({ entry }: { entry: RepertoireEntry }) {
  return (
    <span
      className={cn(
        "rounded-chip px-2 py-0.5 text-[0.6875rem] font-medium",
        entry.band === "common"
          ? "bg-grounded-soft text-grounded"
          : entry.band === "established"
            ? "bg-surface-sunken text-text"
            : "bg-unsourced-soft text-text",
      )}
      title={`${BAND_COPY[entry.band]} — ${entry.support} corpus paper${
        entry.support === 1 ? "" : "s"
      } describe themselves with: ${entry.signature.join(", ")}`}
    >
      <span className="tabular">{entry.support}</span> paper
      {entry.support === 1 ? "" : "s"} use this
    </span>
  );
}

function ReferenceRow({ reference }: { reference: DesignReference }) {
  return (
    <li className="flex flex-col gap-0.5">
      <div className="flex items-center gap-2">
        <Confidence value={reference.confidence ?? undefined} />
        {reference.role !== "uses-this-design" && (
          <span className="text-[0.6875rem] text-text-muted">
            {reference.role.replace(/-/g, " ")}
          </span>
        )}
      </div>
      <span className="text-xs text-text">{reference.title}</span>
      <span className="text-[0.6875rem] text-text-muted">
        {reference.matchReason}
      </span>
    </li>
  );
}

function MergedResult({
  result,
  onClose,
}: {
  result: MergeResult;
  onClose: () => void;
}) {
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
        <button
          onClick={onClose}
          aria-label="Close"
          className="text-text-muted hover:text-text"
        >
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
              <span className="font-mono text-xs text-text-muted">{rq.id}</span>{" "}
              {rq.text}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3">
        <p className="text-xs font-medium text-text-muted">Grounded in</p>
        <ul className="mt-1 flex flex-col gap-1">
          {result.sources.map((s) => (
            <li key={s.templateId} className="text-xs text-text-muted">
              <span className="font-mono text-text">{s.templateId}</span> →{" "}
              {s.papers.join(", ")}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
