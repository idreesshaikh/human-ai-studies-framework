import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import {
  Layers,
  BookOpen,
  Loader2,
  X,
  Check,
  Info,
  MessageSquareText,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Notice } from "@/components/ui/notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { EmptyState } from "@/components/shell/EmptyState";
import { Confidence } from "@/components/conversation/Confidence";
import { DeriveFromPaper } from "./DeriveFromPaper";
import { CreateStudyFrom } from "@/components/templates/CreateStudyFrom";
import {
  templatesApi,
  type RepertoireEntry,
  type CorpusStatus,
  type MergeResult,
  type CorpusHit,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { useApi, useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { signInHref } from "@/lib/returnTo";
import { publicPaperReference } from "@/lib/paperReference";

const MAX_SHAPES = 12;

function parseShapes(raw: string | null): string[] {
  return [
    ...new Set(
      (raw ?? "")
        .split(",")
        .map((id) => id.trim())
        .filter(Boolean),
    ),
  ].slice(0, MAX_SHAPES);
}

const BAND_COPY: Record<RepertoireEntry["band"], string> = {
  common: "Widely used across the corpus",
  established: "Well established in the corpus",
  rare: "Rarely used, novel territory",
};

function humanizeDesignType(value: string): string {
  return value
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

export function Templates() {
  const [entries, setEntries] = useState<RepertoireEntry[] | null>(null);
  const [corpus, setCorpus] = useState<CorpusStatus | null>(null);

  const [searchParams, setSearchParams] = useSearchParams();

  const selected = useMemo(
    () => new Set(parseShapes(searchParams.get("shapes"))),
    [searchParams],
  );

  const [merged, setMerged] = useState<MergeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);

  const [seed, setSeed] = useState<{
    paper: CorpusHit;
    baseId: string;
  } | null>(null);

  const api = useApi();
  const { refresh } = useSession();
  const { hasCredential } = useAuth();

  const signedOut = !hasCredential;
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
  const [describe, setDescribe] = useState("");
  const [describeBusy, setDescribeBusy] = useState(false);
  const [describeError, setDescribeError] = useState("");

  useEffect(() => {
    let active = true;
    let timer: number | undefined;
    const load = () => {
      templatesApi
        .repertoire()
        .then((d) => {
          if (!active) return;
          setEntries(d.repertoire);
          setCorpus(d.corpus);
          if (d.corpus.state === "loading" || d.corpus.state === "partial") {
            timer = window.setTimeout(load, 1200);
          }
        })
        .catch((e) => {
          if (!active) return;
          setError(
            e instanceof OfflineError
              ? "Start the middleware to browse the repertoire."
              : "Couldn't load the repertoire.",
          );
        });
    };
    load();
    return () => {
      active = false;
      if (timer !== undefined) window.clearTimeout(timer);
    };
  }, []);

  const admitted = useMemo(
    () => (entries ?? []).filter((e) => e.admitted),
    [entries],
  );
  const held = useMemo(
    () => (entries ?? []).filter((e) => !e.admitted),
    [entries],
  );
  const corpusReady = corpus?.state === "ready";

  const updateSelection = useCallback(
    (
      update: (current: string[]) => string[],
      opts: { merged?: boolean } = {},
    ) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);

          const ids = update(parseShapes(params.get("shapes"))).slice(
            0,
            MAX_SHAPES,
          );
          if (ids.length > 0) params.set("shapes", ids.join(","));
          else params.delete("shapes");
          if (opts.merged) params.set("merged", "1");
          else params.delete("merged");
          return params;
        },
        { replace: true },
      );
    },
    [setSearchParams],
  );

  const toggle = (id: string) => {
    setMerged(null);
    updateSelection((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : [...current, id],
    );
  };

  const clearSelection = () => {
    setMerged(null);
    updateSelection(() => []);
  };

  const merge = useCallback(
    async (ids: string[]) => {
      setBusy(true);
      setError(null);
      try {
        const result = await templatesApi.merge(ids);
        setMerged(result);

        updateSelection(() => ids, { merged: true });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't merge those designs.");
      } finally {
        setBusy(false);
      }
    },
    [updateSelection],
  );

  const restoredRef = useRef<string | null>(null);
  useEffect(() => {
    if (searchParams.get("merged") !== "1") return;
    if (selected.size < 2) return;
    const key = [...selected].sort().join(",");
    if (restoredRef.current === key) return;
    restoredRef.current = key;
    void merge([...selected]);
  }, [searchParams, selected, merge]);

  async function describeStudy() {
    const text = describe.trim();
    if (!text || describeBusy) return;
    setDescribeBusy(true);
    setDescribeError("");
    try {

      const project = await api.createProject("Personal");
      const title =
        text.length > 60 ? `${text.slice(0, 57).trimEnd()}…` : text;

      const opening =
        selected.size >= 2
          ? `Merge these design shapes: ${[...selected].join(", ")}. ${text}`
          : text;
      const study = await api.createStudy(project.slug, title);
      await refresh();
      navigate(`/p/${project.slug}/studies/${study.id}`, { state: { opening } });
    } catch (e) {
      setDescribeError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Couldn't start the conversation. Try again in a moment.",
      );
    } finally {
      setDescribeBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <div>

        <h1 className="type-title text-text">Protocol repertoire</h1>
        <p className="type-body mt-1 max-w-reading text-text-muted">
          Proven design shapes from a 15,000-paper corpus, ranked by how widely
          they're actually used. The papers behind each shape are its references;
          pick two or more and merge them into one novel protocol grounded in
          every paper it draws from. No project needed to browse.
        </p>
        {entries && corpusReady && (
          <p className="mt-2 type-caption text-text-muted">
            <span className="type-quantity text-text">{admitted.length}</span> design shape
            {admitted.length === 1 ? "" : "s"} ready to use
            {held.length > 0 && (
              <>
                {" "}
                · <span className="type-quantity text-text-muted">{held.length}</span> held back (too rare)
              </>
            )}
          </p>
        )}
      </div>

      {error && (
        <Notice kind="problem">{error}</Notice>
      )}

      {corpus && corpus.state !== "ready" && (
        <Notice kind={corpus.state === "error" ? "problem" : "note"}>
          {corpus.state === "error"
            ? `The literature index could not finish loading. ${corpus.error}`
            : `Loading the literature index (${corpus.papers.toLocaleString()} of ${corpus.expected.toLocaleString()} papers). Design evidence will appear as soon as it is ready.`}
        </Notice>
      )}

      {entries && entries.length > 0 && corpusReady && (
        <DeriveFromPaper templates={entries} seed={seed} />
      )}

      {entries && entries.length > 0 && corpusReady && (
        <section className="flex flex-col gap-2 rounded-card border border-border bg-surface p-4">
          <h2 className="type-subhead flex items-center gap-2 text-text">
            <MessageSquareText className="size-4" aria-hidden />
            Describe your study instead
          </h2>
          <p className="type-caption text-text-muted">
            {selected.size >= 2
              ? `The ${selected.size} shapes you selected will be proposed as a merge in a design conversation.`
              : "Not sure which shapes fit? Describe the study in plain language and the assistant works the design out with you."}
          </p>
          <div className="flex flex-wrap gap-2">
            <Input
              value={describe}
              onChange={(e) => setDescribe(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && void describeStudy()}
              placeholder="e.g. Does AI pair programming change debugging time, comparing telemetry with self-report?"
              aria-label="Describe your study"
              className="min-w-0 flex-1 basis-56"
            />

            {signedOut ? (
              <Button asChild size="sm">
                <Link to={signInHref(pathname + search)}>Sign in to start</Link>
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => void describeStudy()}
                disabled={!describe.trim() || describeBusy}
              >
                {describeBusy ? (
                  <Loader2 className="size-4 animate-spin" aria-hidden />
                ) : (
                  "Start conversation"
                )}
              </Button>
            )}
          </div>
          {describeError && (
            <p role="alert" className="type-caption text-critical">
              {describeError}
            </p>
          )}
        </section>
      )}

      {entries === null && !error ? (
        <p className="flex items-center gap-2 type-body text-text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Ranking the
          repertoire against the corpus…
        </p>
      ) : entries && !corpusReady ? null : entries && entries.length === 0 ? (
        <EmptyState line="No design shapes in the registry yet." />
      ) : (

        <section className="flex flex-col gap-2">

          <h2 className="type-subhead text-text">Design shapes</h2>
          <p className="type-caption text-text-muted">
            Tick two or more to merge them into one protocol grounded in every
            paper they draw from. Open a card for its full description and its
            references.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {admitted.map((entry) => (
              <ShapeCard
                key={entry.id}
                entry={entry}
                selected={selected.has(entry.id)}
                onToggle={() => toggle(entry.id)}
                onDetail={() => setDetailId(entry.id)}
              />
            ))}
          </div>
        </section>
      )}

      {corpusReady && held.length > 0 && (
        <section className="flex flex-col gap-2">
          <h2 className="type-subhead flex items-center gap-1.5 text-text-muted">
            <Info className="size-4" aria-hidden /> Held back
          </h2>
          <p className="type-caption text-text-muted">
            Too rare to propose without a strong source. Shown, not hidden: the
            reason is stated so you can judge it yourself.
          </p>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {held.map((entry) => (
              <div
                key={entry.id}
                className="rounded-plate border border-dashed border-unsourced p-3"
              >
                <p className="type-label font-semibold text-text">{entry.title}</p>
                <p className="type-caption mt-0.5 text-text-muted">
                  {entry.admissionNote}
                </p>
              </div>
            ))}
          </div>
        </section>
      )}

      {selected.size > 0 && (
        <div className="sticky bottom-4 flex items-center gap-3 rounded-card border border-border-strong bg-surface-raised p-3 shadow-sheet">
          <span className="type-body text-text">
            {selected.size} shape{selected.size === 1 ? "" : "s"} selected
            {selected.size < 2 && (
              <span className="text-text-muted"> (pick one more to merge)</span>
            )}
          </span>
          <div className="ml-auto flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={clearSelection}
            >
              Clear
            </Button>
            <Button
              size="sm"
              disabled={selected.size < 2 || busy}
              onClick={() => void merge([...selected])}
            >
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

      {merged && (
        <MergedResult
          result={merged}
          onClose={() => {
            setMerged(null);
            restoredRef.current = null;
            updateSelection((current) => current);
          }}
        />
      )}

      {detailId && entries && (
        <ShapeDetailPanel
          entry={entries.find((e) => e.id === detailId)!}
          selected={selected.has(detailId)}
          onToggle={() => toggle(detailId)}
          onClose={() => setDetailId(null)}
          onUsePaper={(paper, baseId) => {
            setDetailId(null);
            setSeed({ paper, baseId });
          }}
        />
      )}
    </div>
  );
}

function ShapeCard({
  entry,
  selected,
  onToggle,
  onDetail,
}: {
  entry: RepertoireEntry;
  selected: boolean;
  onToggle: () => void;
  onDetail: () => void;
}) {
  return (
    <Card
      className={cn(
        "flex flex-col transition-colors duration-fast",
        selected
          ? "border-accent ring-1 ring-accent"
          : "hover:border-control-edge",
      )}
    >

      <CardContent className="flex flex-1 flex-col gap-3 p-4">

        <label className="flex cursor-pointer items-start gap-2.5">
          <span className="relative mt-0.5 flex size-4 shrink-0">
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggle}
              className="absolute inset-0 size-full cursor-pointer opacity-0"
            />
            <span
              aria-hidden
              className={cn(
                "pointer-events-none flex size-4 items-center justify-center rounded-control-inner border transition-colors duration-fast",
                selected
                  ? "border-accent bg-accent"
                  : "border-control-edge bg-surface",
              )}
            >
              {selected && (
                <Check className="size-3 text-accent-contrast" strokeWidth={3} />
              )}
            </span>
          </span>
          <span className="type-subhead min-w-0 flex-1 text-text">
            {entry.title}
          </span>
        </label>

        <button
          type="button"
          onClick={onDetail}
          className="text-left transition-colors duration-fast hover:text-accent"
          aria-label={`View details for ${entry.title}`}
        >
          <p className="type-caption line-clamp-4 text-text-muted hover:text-text-muted">
            {entry.description}
          </p>
        </button>

        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
          <SupportBadge entry={entry} />
          <Badge variant="outline">{humanizeDesignType(entry.designType)}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function SupportBadge({ entry }: { entry: RepertoireEntry }) {
  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={`${BAND_COPY[entry.band]}: ${entry.support} corpus paper${
        entry.support === 1 ? "" : "s"
      } describe themselves with: ${entry.signature.join(", ")}`}
    >
      <span className="type-caption text-text-muted">
        <span className="type-quantity text-text">{entry.support}</span> paper
        {entry.support === 1 ? "" : "s"}
      </span>
    </span>
  );
}

function ShapeDetailPanel({
  entry,
  selected,
  onToggle,
  onClose,
  onUsePaper,
}: {
  entry: RepertoireEntry;
  selected: boolean;
  onToggle: () => void;
  onClose: () => void;
  onUsePaper: (paper: CorpusHit, baseId: string) => void;
}) {
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-w-work max-h-[80vh] flex flex-col">

        <div className="flex items-start justify-between gap-4 pr-9">
          <div className="flex-1">
            <DialogTitle className="type-display">{entry.title}</DialogTitle>
            <p className="mt-2 type-caption text-text-muted">{BAND_COPY[entry.band]}</p>
          </div>
          <label className="flex cursor-pointer items-center gap-2">
            <input
              type="checkbox"
              checked={selected}
              onChange={onToggle}
              className="cursor-pointer"
            />
            <span className="type-caption text-text-muted">Include in merge</span>
          </label>
        </div>

        <div className="flex-1 overflow-y-auto space-y-4">
          <div>
            <h3 className="type-label font-semibold text-text">Description</h3>
            <p className="mt-2 type-body text-text">{entry.description}</p>
          </div>

          <div>
            <h3 className="type-label font-semibold text-text">Design type</h3>
            <p className="mt-2 type-body text-text">{humanizeDesignType(entry.designType)}</p>
          </div>

          <div>
            <h3 className="type-label flex items-center gap-2 font-semibold text-text">
              <BookOpen className="size-4" aria-hidden />
              References ({entry.references.length})
            </h3>
            <ul className="mt-2 space-y-2">
              {entry.references.map((ref) => (
                <li key={ref.ref} className="rounded-control border border-border p-2">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex min-w-0 flex-col gap-1">
                      <div className="flex items-center gap-2">
                        <Confidence value={ref.confidence ?? undefined} />
                        {ref.role !== "uses-this-design" && (
                          <span className="type-caption text-text-muted">
                            {ref.role.replace(/-/g, " ")}
                          </span>
                        )}
                      </div>
                      <p className="type-caption text-text">{ref.title}</p>
                      <p className="type-caption text-text-muted">{ref.matchReason}</p>
                    </div>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() =>
                        onUsePaper(
                          {
                            ref: ref.ref,
                            title: ref.title,
                            year: ref.year,
                            venue: ref.venue,
                            confidence: ref.confidence,
                            matchReason: ref.matchReason,
                          },
                          entry.id,
                        )
                      }
                    >
                      Use this paper
                    </Button>
                  </div>
                </li>
              ))}
            </ul>
            {entry.unresolvedSources.length > 0 && (
              <p className="mt-2 type-caption text-text-muted">
                Additional source: {entry.unresolvedSources
                  .map((source) => publicPaperReference(source) ?? "Source record")
                  .join(", ")}
              </p>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
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
        <h2 className="type-subhead flex items-center gap-2 text-text">
          Merged protocol
        </h2>
        <button
          onClick={onClose}
          aria-label="Close"
          className="text-text-muted hover:text-text"
        >
          <X className="size-4" aria-hidden />
        </button>
      </div>
      <p className="mt-0.5 type-body text-text-muted">{proto.study?.title}</p>

      <div className="mt-3">
        <p className="type-legend text-text-muted">
          Research questions ({rqs.length})
        </p>
        <ul className="mt-1 flex flex-col gap-1">
          {rqs.map((rq) => (
            <li key={rq.id} className="type-body text-text">
              <span className="type-quantity text-text-muted">{rq.id}</span>{" "}
              {rq.text}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-3">
        <p className="type-legend text-text-muted">Grounded in</p>
        <ul className="mt-1 flex flex-col gap-1">
          {result.sources.map((s) => (
            <li key={s.templateId} className="type-caption text-text-muted">
              <span className="font-mono text-text">{s.templateId}</span> →{" "}
              {s.papers.join(", ")}
            </li>
          ))}
        </ul>
      </div>

      <CreateStudyFrom
        protocol={result.protocol}
        label="Turn this into a study  -  the merged protocol seeds its draft"
      />
    </div>
  );
}
