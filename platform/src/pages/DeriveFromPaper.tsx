import { useCallback, useEffect, useRef, useState } from "react";
import { Search, Loader2, Sparkles, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Notice } from "@/components/ui/notice";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
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
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<CorpusHit[] | null>(null);
  const [paper, setPaper] = useState<CorpusHit | null>(null);
  const [baseId, setBaseId] = useState("");
  const [derived, setDerived] = useState<DerivedTemplate | null>(null);
  const [searching, setSearching] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
    setDerived(null);
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

  /* A paper handed over from a shape's reference list. Scrolled to, because
   * this panel sits below a page of cards and filling it silently off-screen
   * looks like the click did nothing. */
  const panel = useRef<HTMLElement>(null);
  useEffect(() => {
    if (!seed) return;
    setPaper(seed.paper);
    setBaseId(seed.baseId);
    setDerived(null);
    setError(null);
    panel.current?.scrollIntoView({ behavior: "smooth", block: "center" });
  }, [seed]);

  async function derive() {
    if (!paper || !baseId) return;
    setBusy(true);
    setError(null);
    try {
      setDerived(await templatesApi.fromPaper(paper.ref, baseId));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't derive the template.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <section
      ref={panel}
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-4"
    >
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
            onChange={(e) => setQ(e.target.value)}
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

      {hits && hits.length === 0 && (
        <p className="type-caption text-text-muted">No corpus papers match that. Try other terms.</p>
      )}

      {hits && hits.length > 0 && (
        <ul className="flex max-h-56 flex-col gap-1 overflow-auto">
          {hits.map((h) => (
            <li key={h.ref}>
              <button
                onClick={() => { setPaper(h); setDerived(null); }}
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
            onValueChange={setBaseId}
            options={templates.map((t) => ({
              value: t.id,
              label: `${t.designType}: ${t.title}`,
            }))}
            placeholder="Choose an archetype…"
            className="w-auto"
          />
          <Button size="sm" onClick={derive} disabled={!baseId || busy}>
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
    </section>
  );
}
