import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  Layers,
  BookOpen,
  Loader2,
  X,
  ChevronDown,
  Check,
  Info,
  Plus,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Notice } from "@/components/ui/notice";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { EmptyState } from "@/components/shell/EmptyState";
import { Confidence } from "@/components/conversation/Confidence";
import { DeriveFromPaper } from "./DeriveFromPaper";
import { useApi, useSession } from "@/lib/session";
import {
  templatesApi,
  type RepertoireEntry,
  type DesignReference,
  type MergeResult,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { ApiError } from "@/lib/api.ts";
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
    <div className="mx-auto flex max-w-work flex-col gap-section p-gutter">
      <div>
        {/* No icon beside the heading. A page title carries its own weight,
          * and an accent-tinted glyph next to it spends the screen's one
          * accent on decoration instead of on the action the researcher is
          * meant to find. */}
        <h1 className="type-title text-text">Protocol repertoire</h1>
        <p className="type-body mt-1 max-w-reading text-text-muted">
          Proven design shapes, ranked by how widely the corpus uses them. The
          papers that used a shape are its references; pick two or more shapes
          and merge them into one novel protocol, grounded in every paper it
          draws from. No project needed to browse — a merge can become a study
          in any of your projects.
        </p>
      </div>

      {error && (
        <Notice kind="problem">{error}</Notice>
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
          <span className="type-subhead min-w-0 flex-1 text-balance text-text">
            {entry.title}
          </span>
        </label>

        {/* Clamped, so a shelf of cards stays comparable down the row: one
          * card with a five-line description and another with fifteen is a
          * ragged shelf you cannot scan across. The full text is a click
          * away in the study itself. */}
        <p className="type-caption line-clamp-4 text-text-muted">
          {entry.description}
        </p>

        <div className="mt-auto flex flex-wrap items-center gap-x-3 gap-y-2 pt-1">
          <SupportBadge entry={entry} />
          <Badge variant="outline">{entry.designType}</Badge>
        </div>

        <button
          type="button"
          onClick={() => setOpenRefs((v) => !v)}
          className="type-caption flex items-center gap-1.5 self-start rounded-control text-text-muted transition-colors duration-fast hover:text-text"
          aria-expanded={openRefs}
        >
          <BookOpen className="size-3" aria-hidden />
          {entry.references.length} reference
          {entry.references.length === 1 ? "" : "s"}
          <ChevronDown
            className={cn(
              "size-3 transition-transform duration-standard",
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
              <li className="type-caption text-text-muted">
                Cited but not in the corpus:{" "}
                <span className="type-quantity identifier">
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

function ReferenceRow({ reference }: { reference: DesignReference }) {
  return (
    <li className="flex flex-col gap-0.5">
      <div className="flex items-center gap-2">
        <Confidence value={reference.confidence ?? undefined} />
        {reference.role !== "uses-this-design" && (
          <span className="type-legend text-text-muted">
            {reference.role.replace(/-/g, " ")}
          </span>
        )}
      </div>
      <span className="type-caption text-text">{reference.title}</span>
      <span className="type-legend text-text-muted">
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
  const api = useApi();
  const { refresh } = useSession();
  const navigate = useNavigate();
  const [projects, setProjects] = useState<{ slug: string; name: string }[] | null>(null);
  const [slug, setSlug] = useState("");
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [createError, setCreateError] = useState("");

  useEffect(() => {
    api
      .listProjects()
      .then((ps) => {
        setProjects(ps.map((p) => ({ slug: p.slug, name: p.name })));
        setSlug((cur) => cur || ps[0]?.slug || "");
      })
      .catch(() => setProjects([]));
  }, [api]);

  const create = async () => {
    if (!slug || !name.trim() || creating) return;
    setCreating(true);
    setCreateError("");
    try {
      const study = await api.createStudy(slug, name.trim(), result.protocol);
      // Refresh `me` so the new study's membership resolves immediately.
      await refresh();
      navigate(`/p/${slug}/studies/${study.id}`);
    } catch (e) {
      setCreateError(
        e instanceof ApiError && e.fromServer
          ? e.message
          : "Couldn't create the study. Check the connection and try again.",
      );
      setCreating(false);
    }
  };

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
      <div className="mt-4 border-t border-border pt-3">
        <p className="type-legend text-text-muted">
          Turn this into a study — the merged protocol seeds its draft
        </p>
        {projects === null ? (
          <p className="mt-2 flex items-center gap-2 type-caption text-text-muted">
            <Loader2 className="size-4 animate-spin" aria-hidden /> Loading
            your projects…
          </p>
        ) : projects.length === 0 ? (
          <p className="mt-2 type-caption text-text-muted">
            No project to put it in yet — create one first.
          </p>
        ) : (
          <div className="mt-2 flex flex-wrap gap-2">
            <label className="sr-only" htmlFor="merge-project">
              Project
            </label>
            <Select
              id="merge-project"
              value={slug}
              onChange={(e) => setSlug(e.target.value)}
              className="w-auto min-w-40"
            >
              {projects.map((p) => (
                <option key={p.slug} value={p.slug}>
                  {p.name}
                </option>
              ))}
            </Select>
            <Input
              className="min-w-0 flex-1 basis-48"
              placeholder="Name the study…"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") create();
                if (e.key === "Escape") setName("");
              }}
              aria-label="New study name"
            />
            <Button
              size="sm"
              disabled={!slug || !name.trim() || creating}
              onClick={create}
            >
              {creating ? (
                <Loader2 className="size-4 animate-spin" aria-hidden />
              ) : (
                <Plus className="size-4" aria-hidden />
              )}
              Create study
            </Button>
          </div>
        )}
        {createError && (
          <p role="alert" className="mt-2 type-caption text-critical">
            {createError}
          </p>
        )}
      </div>
    </div>
  );
}
