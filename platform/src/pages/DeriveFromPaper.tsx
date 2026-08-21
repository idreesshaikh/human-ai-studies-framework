import { useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Search, Loader2, Sparkles, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Card, CardContent } from "@/components/ui/card";
import { Confidence } from "@/components/conversation/Confidence";
import {
  templatesApi,
  type TemplateSummary,
  type CorpusHit,
  type DerivedTemplate,
} from "@/lib/templatesApi";
import { OfflineError } from "@/lib/studyApi";
import { useDebouncedValue } from "@/lib/useDebouncedValue";
import { CreateStudyFrom } from "@/components/templates/CreateStudyFrom";

/* Turn any corpus paper into an executable template (FR-TPL-4). Search the
 * 15,000-paper corpus, pick a paper, pick a base archetype, and the platform
 * binds them: the paper becomes the design's primary source and the archetype
 * supplies the runnable structure. This is how the whole corpus becomes a set
 * of executable starting points, not just the hand-authored templates. */
export function DeriveFromPaper({
  templates,
  seed = null,
}: {
  templates: TemplateSummary[];
  /** A paper chosen from a design shape's own reference list, with that
   *  shape as its archetype. Fills this panel in rather than making the
   *  researcher re-find a paper they were already looking at. */
  seed?: { paper: CorpusHit; baseId: string } | null;
}) {
  /* Addressable state, same contract as the shape selection above it: what
   * the researcher has searched for, which paper they picked, and which
   * archetype they are running it through all live in the URL, so the panel
   * survives the reload that signing in performs. Its own key names, since it
   * shares an address with the repertoire's `shapes`/`merged`.
   *
   * The derived template is recomputed rather than carried — `/templates/
   * from-paper` binds a paper to an archetype at request time and writes
   * nothing, and the protocol it returns is far too large for a query
   * string. */
  const [searchParams, setSearchParams] = useSearchParams();
  const paperRef = searchParams.get("paper") ?? "";
  const baseId = searchParams.get("base") ?? "";

  const writeParams = useCallback(
    (mutate: (params: URLSearchParams) => void) => {
      setSearchParams(
        (prev) => {
          const params = new URLSearchParams(prev);
          mutate(params);
          return params;
        },
        // Replace, not push: refining a search term is one act of looking,
        // and this panel shares its address with the shape selection, whose
        // writes are replaces for the same reason.
        { replace: true },
      );
    },
    [setSearchParams],
  );

  /* The field itself stays local so typing is instant; only the settled
   * query reaches the address (see the debounce below), which is also the
   * only value worth restoring. Seeded from the URL once, on mount — with
   * every write a `replace`, there are no history entries for a back button
   * to walk, so there is nothing to sync back the other way. */
  const [q, setQ] = useState(() => searchParams.get("paperq") ?? "");
  const [hits, setHits] = useState<CorpusHit[] | null>(null);
  const [paper, setPaper] = useState<CorpusHit | null>(null);
  const [derived, setDerived] = useState<DerivedTemplate | null>(null);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const pickPaper = (hit: CorpusHit | null) => {
    setPaper(hit);
    setDerived(null);
    writeParams((params) => {
      if (hit) params.set("paper", hit.ref);
      else params.delete("paper");
      params.delete("derived");
    });
  };

  const pickBase = (id: string) => {
    setDerived(null);
    writeParams((params) => {
      if (id) params.set("base", id);
      else params.delete("base");
      params.delete("derived");
    });
  };

  /* Search as you type, one request per pause rather than per keystroke
   * (the input itself stays instant — only its effect is debounced). A
   * reply that arrives after a newer query is dropped, so results can't
   * arrive out of order. */
  const debouncedQ = useDebouncedValue(q);
  const latestQuery = useRef("");

  const search = useCallback(async (term: string) => {
    const query = term.trim();
    latestQuery.current = query;
    if (!query) {
      setHits(null);
      return;
    }
    setSearching(true);
    setError(null);
    /* Deliberately NOT clearing `derived` here. Restoring a derivation from
     * the address and re-running the stored query happen together on a cold
     * load, and the debounced search settles LAST — so clearing it inside the
     * search wiped the very card the URL had just asked to be restored. What
     * invalidates a derivation is the researcher typing a new query, which is
     * handled at the field itself. */
    try {
      const results = await templatesApi.searchCorpus(query);
      if (latestQuery.current === query) setHits(results);
    } catch (e) {
      if (latestQuery.current !== query) return;
      setError(
        e instanceof OfflineError
          ? "Start the middleware to search the corpus."
          : "Couldn't search the corpus.",
      );
    } finally {
      if (latestQuery.current === query) setSearching(false);
    }
  }, []);

  useEffect(() => {
    void search(debouncedQ);
  }, [debouncedQ, search]);

  /* The settled query, published to the address. Writing per keystroke would
   * churn the URL for every letter; this fires on the same pause the search
   * itself does. Re-running after the write is harmless — the value now
   * matches and it returns. */
  useEffect(() => {
    const term = debouncedQ.trim();
    if (term === (searchParams.get("paperq") ?? "")) return;
    writeParams((params) => {
      if (term) params.set("paperq", term);
      else params.delete("paperq");
    });
  }, [debouncedQ, searchParams, writeParams]);

  /* Adopt the paper the address names, once the search that contains it comes
   * back. The URL can only carry the ref; the row that says "Run <title>
   * through" needs the whole hit, and re-running the stored query is what
   * produces it. */
  useEffect(() => {
    if (!paperRef || paper?.ref === paperRef) return;
    const found = hits?.find((h) => h.ref === paperRef);
    if (found) setPaper(found);
  }, [hits, paperRef, paper]);

  /* A paper handed over from a shape's reference list. Scrolled to, because
   * this panel sits below a page of cards and filling it silently off-screen
   * looks like the click did nothing. */
  const panel = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!seed) return;
    setPaper(seed.paper);
    setDerived(null);
    setError(null);
    writeParams((params) => {
      params.set("paper", seed.paper.ref);
      params.set("base", seed.baseId);
      params.delete("derived");
    });
    panel.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [seed, writeParams]);

  const derive = useCallback(
    async (ref: string, base: string) => {
      if (!ref || !base) return;
      setBusy(true);
      setError(null);
      try {
        const result = await templatesApi.fromPaper(ref, base);
        setDerived(result);
        // A paper reached by a seeded hand-off, or restored from a cold URL,
        // may never have appeared in a search on this visit — the derived
        // payload carries enough to name it in the row above.
        setPaper((current) =>
          current?.ref === result.paper.ref
            ? current
            : {
                ref: result.paper.ref,
                title: result.paper.title,
                confidence: result.paper.confidence,
                year: null,
                venue: "",
                matchReason: "",
              },
        );
        writeParams((params) => params.set("derived", "1"));
      } catch (e) {
        setError(e instanceof Error ? e.message : "Couldn't derive the template.");
      } finally {
        setBusy(false);
      }
    },
    [writeParams],
  );

  /* Restore a derivation the address says was showing. Keyed on the exact
   * pair, so a failure is reported once instead of retried every render, and
   * choosing a different archetype is still allowed to try. */
  const restoredRef = useRef<string | null>(null);
  useEffect(() => {
    if (searchParams.get("derived") !== "1") return;
    if (!paperRef || !baseId) return;
    const key = `${paperRef}|${baseId}`;
    if (restoredRef.current === key) return;
    restoredRef.current = key;
    void derive(paperRef, baseId);
  }, [searchParams, paperRef, baseId, derive]);

  return (
    <Card ref={panel} className="border-strong bg-surface-raised">
      <CardContent className="flex flex-col gap-3 p-4">
        <div>
          <h2 className="type-subhead flex items-center gap-2 text-text">
            Start from a paper
          </h2>
          <p className="mt-1 type-caption text-text-muted">
            Search the corpus, pick a paper, and run it through an archetype: the
            paper becomes your design's primary citation.
          </p>
        </div>

      <div className="flex gap-2">
        <div className="relative flex-1">
          <Search
            className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-text-muted"
            aria-hidden
          />
          <Input
            value={q}
            onChange={(e) => {
              setQ(e.target.value);
              // A new question makes the previous answer stale.
              setDerived(null);
            }}
            onKeyDown={(e) => e.key === "Enter" && void search(q)}
            placeholder="e.g. trust in AI-generated code"
            aria-label="Search the corpus"
            className="pl-9"
          />
        </div>
        <Button
          size="sm"
          variant="subtle"
          onClick={() => void search(q)}
          disabled={searching || !q.trim()}
        >
          {searching ? <Loader2 className="size-4 animate-spin" aria-hidden /> : "Search"}
        </Button>
      </div>

      {error && <Notice kind="problem">{error}</Notice>}

      {/* No "waiting to be searched" box. This panel already says what it is
        * for in its own description, and the field says it again in its
        * placeholder; a dashed rectangle underneath repeating "search the
        * corpus by keywords, author, or topic" was the third statement of one
        * instruction inside a hundred and fifty pixels, and it reserved a
        * results-shaped hole for results nobody had asked for yet. An empty
        * region that has not been asked a question is correctly empty. */}

      {q.trim() && hits && hits.length === 0 && (
        <div className="rounded-input border border-border bg-bg p-3">
          <p className="type-body text-text-muted">No corpus papers match "{q}".</p>
          <p className="mt-1 type-caption text-text-muted">
            Try different keywords or browse proven designs on the repertoire page.
          </p>
        </div>
      )}

      {hits && hits.length > 0 && (
        <ul className="flex max-h-56 flex-col gap-1 overflow-auto">
          {hits.map((h) => (
            <li key={h.ref}>
              <button
                onClick={() => pickPaper(h)}
                className={
                  "flex w-full items-center gap-2 rounded-input border px-2 py-1.5 text-left type-body transition-colors duration-fast " +
                  (paper?.ref === h.ref
                    ? "border-accent bg-zone-9"
                    : "border-transparent hover:bg-zone-9")
                }
              >
                <Confidence value={h.confidence ?? undefined} />
                <span className="min-w-0 flex-1 truncate text-text">{h.title}</span>
                {h.year && <span className="tabular type-caption text-text-muted">{h.year}</span>}
              </button>
            </li>
          ))}
        </ul>
      )}

      {paper && (
        <div className="flex flex-wrap items-center gap-2 border-t border-border pt-3">
          <span className="type-caption text-text-muted">Run</span>
          <span className="max-w-56 truncate type-caption font-medium text-text">{paper.title}</span>
          <span className="type-caption text-text-muted">through</span>
          <Select
            value={baseId}
            onValueChange={pickBase}
            options={templates.map((t) => ({
              value: t.id,
              label: `${t.designType}: ${t.title}`,
            }))}
            placeholder="Choose an archetype…"
            className="w-auto"
          />
          <Button
            size="sm"
            onClick={() => void derive(paper.ref, baseId)}
            disabled={!baseId || busy}
          >
            {busy ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Sparkles className="size-4" aria-hidden />}
            Derive template
          </Button>
        </div>
      )}

      {derived && (
        <div className="rounded-input border border-border-strong bg-surface-raised p-3">
          <p className="font-medium text-text">{derived.template.title}</p>
          <div className="mt-1 flex items-center gap-2">
            <Badge variant="outline">{derived.template.designType}</Badge>
            <Confidence value={derived.paper.confidence ?? undefined} />
          </div>
          <p className="mt-2 type-caption text-text-muted">{derived.template.description}</p>
          <p className="mt-2 flex items-center gap-1 type-caption text-text-muted">
            <BookOpen className="size-3" aria-hidden /> Primary source:{" "}
            <span className="font-mono text-text">{derived.template.source[0]?.paperRef}</span>
          </p>

          {/* The point of deriving. Without this the panel produced a card
            * describing a design and no way to use it, which is exactly the
            * dead end a reviewer walked into. */}
          <CreateStudyFrom
            protocol={derived.protocol}
            label="Turn this into a study — this design seeds its draft, citing the paper"
          />
        </div>
      )}
      </CardContent>
    </Card>
  );
}
