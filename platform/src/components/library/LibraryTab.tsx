import { useCallback, useEffect, useState } from "react";
import { Plus, Upload, X, ExternalLink, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Constellation } from "./Constellation";
import { Assistant } from "./Assistant";
import {
  studyApi,
  OfflineError,
  type Paper,
  type PaperGraph,
} from "@/lib/studyApi";
import { ingestIdForRef } from "@/lib/forceLayout";
import { cn } from "@/lib/cn";

/* The Library — the knowledge layer (FR-LIT-1/2/3/4). Live paper ingest (arXiv/DOI/PDF), the
 * citation constellation, protocol-element links, and the grounded assistant.
 * The corpus is the product's knowledge, not background reading — so this is a
 * first-class study surface, not a side panel. */
export function LibraryTab({ studyId }: { studyId: string }) {
  const [papers, setPapers] = useState<Paper[]>([]);
  const [graph, setGraph] = useState<PaperGraph | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [idInput, setIdInput] = useState("");
  const [linkDraft, setLinkDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState<string | null>(null);

  const load = useCallback(async () => {
    const [ps, g] = await Promise.all([
      studyApi.papers(studyId),
      studyApi.papersGraph(studyId),
    ]);
    setPapers(ps);
    setGraph(g);
  }, [studyId]);

  useEffect(() => {
    load();
  }, [load]);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setNote(null);
    try {
      await fn();
      await load();
    } catch (e) {
      setNote(e instanceof OfflineError ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  function ingest() {
    const raw = idInput.trim();
    if (!raw) return;
    const id = raw.toLowerCase().includes("arxiv")
      ? { arxivId: raw.replace(/.*arxiv[:/]?/i, "") }
      : /^10\./.test(raw)
        ? { doi: raw }
        : { arxivId: raw };
    run(() => studyApi.ingestPaper(studyId, id)).then(() => setIdInput(""));
  }

  function uploadPdf(ev: React.ChangeEvent<HTMLInputElement>) {
    const file = ev.target.files?.[0];
    if (file) run(() => studyApi.uploadPaperPdf(studyId, file));
  }

  function select(ref: string) {
    setSelected(ref);
    setLinkDraft((papers.find((p) => p.paperRef === ref)?.links ?? []).join(", "));
  }

  const selectedPaper = papers.find((p) => p.paperRef === selected) ?? null;
  const selectedNode = graph?.nodes.find((n) => n.paperRef === selected) ?? null;

  return (
    <div className="grid h-full min-h-0 grid-cols-1 gap-4 overflow-y-auto overflow-x-hidden p-4 lg:grid-cols-[1.6fr_1fr]">
      <section className="flex min-h-0 min-w-0 flex-col gap-4">
        {/* Ingest bar — the live-fetch moment. */}
        <div className="flex flex-wrap items-center gap-2">
          <input
            value={idInput}
            onChange={(e) => setIdInput(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && ingest()}
            placeholder="arXiv id or DOI, e.g. 2302.06590"
            aria-label="arXiv id or DOI"
            className="min-h-9 flex-1 rounded-input border border-border-strong bg-bg px-3 py-2 text-sm text-text outline-none focus-visible:border-accent"
          />
          <Button size="sm" variant="subtle" onClick={ingest} disabled={busy}>
            <Plus aria-hidden /> Add
          </Button>
          <label className="flex cursor-pointer items-center gap-1 rounded-input border border-dashed border-border-strong px-3 py-2 text-sm text-text-muted hover:border-accent">
            <Upload className="size-4" aria-hidden /> PDF
            <input type="file" accept="application/pdf" hidden onChange={uploadPdf} />
          </label>
        </div>

        {busy && (
          <p className="flex items-center gap-2 text-xs text-text-muted" role="status">
            <Loader2 className="size-3 animate-spin" aria-hidden />
            Fetching metadata and the citation neighbourhood (the citation
            service allows one request per second)…
          </p>
        )}
        {note && (
          <p className="rounded-input border border-border bg-surface p-3 text-sm text-text-muted">
            {note}
          </p>
        )}

        {/* Library list — the study's primary paper set. Papers accepted from
            the design conversation's recommendations land here too. */}
        <div className="rounded-card border border-border bg-surface">
          <div className="flex items-center justify-between border-b border-border px-4 py-2">
            <h3 className="text-sm font-medium text-text">Library</h3>
            <span className="text-xs text-text-muted">
              {papers.length} {papers.length === 1 ? "paper" : "papers"}
            </span>
          </div>
          <ul className="max-h-72 overflow-y-auto overflow-x-hidden">
            {papers.map((p) => (
              <li
                key={p.paperRef}
                className={cn(
                  "flex items-center gap-2 px-4 py-2 text-sm",
                  p.paperRef === selected && "bg-accent-soft",
                )}
              >
                <button
                  className="flex-1 truncate text-left text-text hover:text-accent"
                  onClick={() => select(p.paperRef)}
                  title={p.title || p.paperRef}
                >
                  {p.title || p.paperRef}
                </button>
                {p.year && (
                  <span className="tabular text-xs text-text-muted">{p.year}</span>
                )}
                <button
                  className="text-text-muted hover:text-status-critical"
                  aria-label={`Remove ${p.title || p.paperRef}`}
                  onClick={() => run(() => studyApi.deletePaper(studyId, p.paperRef))}
                  disabled={busy}
                >
                  <X className="size-4" aria-hidden />
                </button>
              </li>
            ))}
            {papers.length === 0 && (
              <li className="px-4 py-3 text-sm text-text-muted">
                No papers yet — add one above.
              </li>
            )}
          </ul>
        </div>

        {/* The constellation. */}
        <div className="rounded-card border border-border bg-surface p-4">
          <h3 className="mb-2 text-sm font-medium text-text">
            Citation constellation
          </h3>
          {graph && (
            <Constellation graph={graph} selected={selected} onSelect={select} />
          )}
        </div>

        {/* Selected-paper detail. */}
        {selectedNode && (
          <aside className="relative rounded-card border border-border bg-surface-raised p-4">
            <button
              className="absolute right-3 top-3 text-text-muted hover:text-text"
              onClick={() => setSelected(null)}
              aria-label="Close detail"
            >
              <X className="size-4" aria-hidden />
            </button>
            <h4 className="pr-6 font-medium text-text">
              {selectedNode.title || selected}
            </h4>
            <p className="mt-0.5 text-xs text-text-muted">
              {selected}
              {selectedNode.year ? ` · ${selectedNode.year}` : ""}
              {selectedNode.citationCount != null
                ? ` · ${selectedNode.citationCount} citations`
                : ""}
            </p>
            {selectedPaper ? (
              <>
                {selectedPaper.abstract && (
                  <p className="mt-2 text-sm leading-relaxed text-text-muted">
                    {selectedPaper.abstract}
                  </p>
                )}
                <label className="mt-3 block text-sm text-text">
                  Protocol links
                  <input
                    value={linkDraft}
                    onChange={(e) => setLinkDraft(e.target.value)}
                    placeholder="RQ-1, metric:parameter_count, recipe:…"
                    className="mt-1 w-full rounded-input border border-border-strong bg-bg px-2 py-1.5 text-sm text-text outline-none focus-visible:border-accent"
                  />
                </label>
                <div className="mt-2 flex items-center gap-2">
                  <Button
                    size="sm"
                    variant="subtle"
                    disabled={busy}
                    onClick={() =>
                      run(() =>
                        studyApi.setPaperLinks(
                          studyId,
                          selected!,
                          linkDraft.split(",").map((t) => t.trim()).filter(Boolean),
                        ),
                      )
                    }
                  >
                    Save links
                  </Button>
                  {selectedPaper.url && (
                    <a
                      href={selectedPaper.url}
                      target="_blank"
                      rel="noreferrer"
                      className="flex items-center gap-1 text-sm text-accent hover:underline"
                    >
                      <ExternalLink className="size-3" aria-hidden /> open
                    </a>
                  )}
                </div>
              </>
            ) : (
              <div className="mt-2">
                <p className="text-sm text-text-muted">
                  Suggested paper — not yet in the study.
                </p>
                <Button
                  size="sm"
                  variant="subtle"
                  className="mt-2"
                  disabled={busy}
                  onClick={() => {
                    const id = ingestIdForRef(selected!);
                    if (id) run(() => studyApi.ingestPaper(studyId, id));
                  }}
                >
                  <Plus aria-hidden /> Add to study
                </Button>
              </div>
            )}
          </aside>
        )}
      </section>

      {/* The assistant rides alongside, full height. */}
      <div className="min-h-0 min-w-0 lg:sticky lg:top-0 lg:h-[calc(100vh-9rem)]">
        <div className="hidden lg:block">
          <Assistant studyId={studyId} />
        </div>
        <details className="lg:hidden">
          <summary className="cursor-pointer rounded-input border border-border bg-surface px-4 py-2 text-sm font-medium text-text">
            Assistant
          </summary>
          <div className="mt-2">
            <Assistant studyId={studyId} />
          </div>
        </details>
      </div>
    </div>
  );
}
