import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
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
  type MergeResult,
  type CorpusHit,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { useApi, useSession } from "@/lib/session";
import { ApiError } from "@/lib/api";
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
  rare: "Rarely used, novel territory",
};

export function Templates() {
  const [entries, setEntries] = useState<RepertoireEntry[] | null>(null);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [merged, setMerged] = useState<MergeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detailId, setDetailId] = useState<string | null>(null);
  /* A paper handed over from a shape's reference list ("Use this paper").
   * Carries the paper into the derive panel with that shape pre-selected as
   * the archetype, so the researcher never re-finds a paper they were already
   * looking at. */
  const [seed, setSeed] = useState<{
    paper: CorpusHit;
    baseId: string;
  } | null>(null);

  /* The conversational alternative to checkbox-merging: describe the study in
   * plain language and the assistant works the design (and, when shapes are
   * selected, the merge) out in a design conversation. */
  const api = useApi();
  const { refresh } = useSession();
  const navigate = useNavigate();
  const [describe, setDescribe] = useState("");
  const [describeBusy, setDescribeBusy] = useState(false);
  const [describeError, setDescribeError] = useState("");

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

  async function describeStudy() {
    const text = describe.trim();
    if (!text || describeBusy) return;
    setDescribeBusy(true);
    setDescribeError("");
    try {
      // Same implicit-personal-project path as QuickStart: no naming friction,
      // the researcher lands straight in the conversation.
      const project = await api.createProject("Personal");
      const title =
        text.length > 60 ? `${text.slice(0, 57).trimEnd()}…` : text;
      // With shapes already selected, name them in the opening so the
      // assistant proposes that merge immediately instead of asking which
      // shapes the researcher means.
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
        {/* No icon beside the heading. A page title carries its own weight,
          * and an accent-tinted glyph next to it spends the screen's one
          * accent on decoration instead of on the action the researcher is
          * meant to find. */}
        <h1 className="type-title text-text">Protocol repertoire</h1>
        <p className="type-body mt-1 max-w-reading text-text-muted">
          Proven design shapes from a 15,000-paper corpus, ranked by how widely
          they're actually used. The papers behind each shape are its references;
          pick two or more and merge them into one novel protocol grounded in
          every paper it draws from. No project needed to browse.
        </p>
        {entries && (
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
        <p className="mt-1 type-caption text-text-muted">
          <Link
            to="/submissions"
            className="inline-block py-1 -my-1 underline underline-offset-2 hover:text-text"
          >
            Review template submissions
          </Link>{" "}
          — proposed shapes from researchers and the corpus miner, awaiting a
          decision before they enter the registry.
        </p>
      </div>

      {error && (
        <Notice kind="problem">{error}</Notice>
      )}

      {entries && entries.length > 0 && (
        <DeriveFromPaper templates={entries} seed={seed} />
      )}

      {/* The conversational alternative to browsing and checking boxes. A
        * researcher who can describe their problem but not name the shapes it
        * needs gets a path straight into a design conversation; shapes they
        * have already selected are handed over as an explicit merge request,
        * so the assistant proposes the pairing rather than asking them to
        * re-articulate it. */}
      {entries && entries.length > 0 && (
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
      ) : entries && entries.length === 0 ? (
        <EmptyState line="No design shapes in the registry yet." />
      ) : (
        /* A grid, not a stack. These are alternatives to choose between, and
           a column forces a reader to hold each one in memory to compare it
           with the next; side by side, the titles, design types and support
           badges line up as columns you can read across.
           `items-start` keeps each plate at its own height: with the default
           stretch, opening one card's references grew the whole grid row and
           dragged its row-mates up to match, leaving them framing several
           hundred pixels of empty plate. A shelf of closed cards still reads
           evenly, since the clamped description already holds them level. */
        <div className="grid items-start gap-3 sm:grid-cols-2 xl:grid-cols-3">
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
      )}

      {held.length > 0 && (
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

      {/* Compose bar — merging is the point of the page. */}
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
      data-agent="design-shape"
      data-agent-ref={entry.id}
      className={cn(
        "flex flex-col transition-colors duration-fast",
        selected
          ? "border-accent ring-1 ring-accent"
          : "hover:border-control-edge",
      )}
    >
      {/* Built to stack, not to span. The old row put the title, the
        * description and a shrink-0 badge column side by side, which worked
        * at full page width and collapsed the title to one word per line the
        * moment these became columns in a grid. In a card, the things that
        * vary in length go down the page and only the fixed-size marks sit
        * across it. */}
      <CardContent className="flex flex-1 flex-col gap-3 p-4">
        {/* A real label, so the title is part of the checkbox's hit area and
          * its accessible name, instead of a button wrapping a paragraph.
          * The box itself is drawn, not the OS default: every other control
          * on the plate (Button, Input, Select) is restyled to the same
          * instrument, and a bare native checkbox was the one control left
          * to render however the browser felt like — an unbordered square in
          * one engine, a solid block in another. The real input still sits
          * over the drawn box, sized to match, so focus, click and keyboard
          * toggling stay native; only its own appearance is hidden. */}
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

        {/* Clamped, so a shelf of cards stays comparable down the row: one
          * card with a five-line description and another with fifteen is a
          * ragged shelf you cannot scan across. The full text is a click
          * away in the detail panel. */}
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
          <Badge variant="outline">{entry.designType}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

/** How widely the corpus uses this shape, as a MAGNITUDE.
 *
 * "How much evidence stands behind this" is the same question the grounding
 * marks answer everywhere else in the app, so it gets the same notation
 * rather than a third vocabulary of coloured pills. It also retires three
 * token names that never existed (`grounded-soft`, `surface-sunken`,
 * `unsourced-soft` as a background), each of which had been silently
 * rendering as no background at all or as a mid-tone slab. */
const BAND_MAGNITUDE = { common: 5, established: 3, rare: 1 } as const;

function SupportBadge({ entry }: { entry: RepertoireEntry }) {
  const mag = BAND_MAGNITUDE[entry.band as keyof typeof BAND_MAGNITUDE] ?? 1;
  return (
    <span
      className="inline-flex items-center gap-1.5"
      title={`${BAND_COPY[entry.band]}: ${entry.support} corpus paper${
        entry.support === 1 ? "" : "s"
      } describe themselves with: ${entry.signature.join(", ")}`}
    >
      <span aria-hidden className="flex size-4 items-center justify-center">
        <span className={`mag mag-${mag}`} />
      </span>
      <span className="type-caption text-text-muted">
        <span className="type-quantity text-text">{entry.support}</span> paper
        {entry.support === 1 ? "" : "s"}
      </span>
    </span>
  );
}

/* One paper behind a design shape — and a way to act on it.
 *
 * These rows were display-only, sitting a few centimetres above a corpus
 * search that looked like it should reach them and did not. "Use this paper"
 * closes that gap: it carries the paper into the derive panel with this
 * shape already selected as the archetype, which is the route from "a paper
 * I recognise" to "a study I can run" the page always implied and never
 * offered. */
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
        <div className="flex items-start justify-between gap-4">
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
            <h3 className="type-label text-text">Description</h3>
            <p className="mt-2 type-body text-text">{entry.description}</p>
          </div>

          <div>
            <h3 className="type-label text-text">Design type</h3>
            <p className="mt-2 type-body text-text">{entry.designType}</p>
          </div>

          <div>
            <h3 className="type-label flex items-center gap-2 text-text">
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
                Cited but not in the corpus: {entry.unresolvedSources.join(", ")}
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

      {/* The merge is not a dead end: land it in a project as a study whose
       * protocol draft is already the merged protocol, and keep designing
       * from there in the conversation. */}
      <CreateStudyFrom
        protocol={result.protocol}
        label="Turn this into a study — the merged protocol seeds its draft"
      />
    </div>
  );
}
