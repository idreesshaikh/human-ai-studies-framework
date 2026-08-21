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
  type MergeResult,
  type CorpusHit,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { useApi, useSession } from "@/lib/session";
import { useAuth } from "@/lib/auth.tsx";
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { signInHref } from "@/lib/returnTo";

/* The protocol repertoire (FR-TPL) — the literature read as *design shapes*
 * rather than as thirteen studies to replicate. Each shape is ranked by how
 * widely the corpus actually uses it (common → rare), the papers that used it
 * hang off it as ranked references, and picking two or more merges them into
 * one novel protocol that stays grounded in every paper it draws from. Merging
 * is the hero action, not a footnote. */

/** How many shapes one URL may select. A merge is a comparison a person
 * makes, not a batch job, and an unbounded list from a hand-edited address
 * would be posted to the merge endpoint verbatim. */
const MAX_SHAPES = 12;

/** The `shapes` parameter as a list of ids: trimmed, de-duplicated, capped.
 * One reader for the address, used by both the component that renders the
 * selection and the updater that writes it, so the two can never disagree
 * about what the URL currently says. */
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

export function Templates() {
  const [entries, setEntries] = useState<RepertoireEntry[] | null>(null);
  /* The selection lives in the URL, not in component state.
   *
   * It is genuinely addressable information — which design shapes a
   * researcher is holding side by side — and treating it as component state
   * meant it could not survive the one thing this page routinely does to it:
   * sending someone to sign in. Signing in ends in `location.reload()`, so a
   * visitor who merged two shapes, was told to sign in to keep the result,
   * and did, came back to an empty page and had to find and re-tick both
   * shapes from memory.
   *
   * In the query string it survives that reload for free (the return-to
   * `next` carries `pathname + search`, so it is already being handed back),
   * and it becomes shareable and back-buttonable as a side effect: a merge
   * is now a link you can paste to a collaborator. */
  const [searchParams, setSearchParams] = useSearchParams();

  const selected = useMemo(
    () => new Set(parseShapes(searchParams.get("shapes"))),
    [searchParams],
  );

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
  const { hasCredential } = useAuth();
  /* The repertoire is public to READ. Everything on this page that writes —
   * starting a conversation, turning a shape into a study — still needs an
   * identity, and says so where it is. */
  const signedOut = !hasCredential;
  const navigate = useNavigate();
  const { pathname, search } = useLocation();
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

  /* Writing the selection back to the address.
   *
   * `replace`, not push: ticking eight boxes is one act of choosing, and
   * pushing each one would bury the page the researcher arrived from under
   * eight history entries they have to click back through.
   *
   * Changing the selection always drops `merged` — a merged protocol names
   * the exact shapes it came from, so leaving the flag set while the
   * selection moves under it would restore a result for a different set than
   * the one now ticked. */
  const updateSelection = useCallback(
    (
      update: (current: string[]) => string[],
      opts: { merged?: boolean } = {},
    ) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          /* The next selection is derived from `prev` INSIDE the updater, not
           * from the `selected` this render closed over. Two toggles in one
           * tick — a double click, a keyboard repeat, a test driving two
           * checkboxes back to back — both read the same stale render and the
           * second silently discarded the first: ticking two shapes left one
           * in the address. */
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
        // Record in the address that a merge is showing, so a reload (a
        // sign-in, a shared link) restores the result and not just the ticks.
        updateSelection(() => ids, { merged: true });
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't merge those designs.");
      } finally {
        setBusy(false);
      }
    },
    [updateSelection],
  );

  /* Restore a merge the address says was showing.
   *
   * The merge endpoint composes templates at request time and writes nothing,
   * so recomputing it on arrival is safe and is the only way to bring the
   * result back — the protocol itself is far too large to carry in a URL.
   *
   * `restoredRef` keys the attempt on the exact selection, so a failure is
   * reported once rather than retried on every render, and re-ticking a
   * different pair is still allowed to try. */
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
            {/* Starting a conversation creates a project and a study, so this
              * is the one control in the panel that needs an identity. The
              * field stays usable either way — a visitor can still frame the
              * question they came with — but the button says what it will
              * actually do rather than failing after the click. */}
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
      ) : entries && entries.length === 0 ? (
        <EmptyState line="No design shapes in the registry yet." />
      ) : (
        /* A grid, not a stack. These are alternatives to choose between, and
           a column forces a reader to hold each one in memory to compare it
           with the next; side by side, the titles, design types and support
           badges line up as columns you can read across.
           
           Cards STRETCH to their row. `items-start` used to be right: a card
           expanded in place to show its references, and stretching dragged its
           row-mates up to match, leaving them framing empty plate. That is no
           longer how details open — they are a dialog now — so nothing ever
           grows in place, and all `items-start` still did was let every card
           sit at its own height. It does not hold them level the way the old
           comment claimed: a one-line title next to a two-line one differs by
           21px, so each row ended on a ragged edge and the shelf read as
           broken rather than as a set of alternatives. */
        <section className="flex flex-col gap-2">
          {/* The page's primary shelf had no heading at all, while the lesser
            * "Held back" shelf below it did — so the grid simply began, and
            * the tick box on every card was an affordance whose purpose was
            * explained only in a paragraph three panels up. The heading names
            * the shelf and says what selecting is for, where the selecting
            * happens. */}
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

      {/* Dismissing has to clear the flag too, or the next reload would
          dutifully restore the very card the researcher just closed. */}
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

/** How widely the corpus uses this shape.
 *
 * "How much evidence stands behind this" is the same question grounding
 * answers everywhere else in the app, so it is answered the same way: the
 * count is PRINTED, in the machine face, and the dot that used to sit beside
 * it is gone. The dot was a second encoding of a number already on the line —
 * and a size ramp nobody could rank without the two marks side by side (see
 * DESIGN.md, The Printed-Magnitude Rule). The band's own words stay in the
 * title, where they explain what the count means. */
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
        {/* `pr-9` reserves the corner the Close button occupies. `DialogContent`
          * positions it `absolute right-4 top-4`, so it floats OVER whatever
          * the header puts there — and this header ends in an interactive
          * label, which overlapped it by 12px: the right end of "Include in
          * merge" was painted under the X, and clicking those pixels hit the
          * close button instead of the checkbox they appeared to belong to. */}
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
